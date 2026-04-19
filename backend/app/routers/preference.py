import json
import logging
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.preference_learner import preference_learner
from app.services.llm_gateway import llm_gateway, ModelTier
from app.agents.summarizer import summarizer_agent
from app.database import get_db
from app.domain.models import PreferenceSignal, User, UserProfile
from app.schemas.preference import (
    ChatRequest,
    ChatResponse,
    LearningCompletionRequest,
    LearningCompletionResponse,
    MemoryConsolidationResponse,
    PreferenceSignalResponse,
    UserResponse,
)
from app.services.long_term_memory import long_term_memory
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preference", tags=["preference"])


@router.post("/users", response_model=UserResponse)
async def create_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """新規ユーザーを作成"""
    user = User()
    db.add(user)
    await db.flush()

    profile = UserProfile(user_id=user.id, summary="")
    db.add(profile)
    await db.commit()

    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user.id)
    )
    return result.scalar_one()


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """ユーザー情報を取得"""
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/chat/start", response_model=ChatResponse)
async def start_chat(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    """嗜好学習チャットを開始（初回挨拶）"""
    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get or create active session
    session = await session_manager.get_active_session(
        db, user_id, mode="preference_learning"
    )
    if not session:
        session = await session_manager.create_session(
            db, user_id, mode="preference_learning"
        )

    # Generate initial greeting
    greeting = await preference_learner.get_initial_greeting()

    # Save assistant message to session (turn_index=1 for first assistant message)
    await session_manager.add_message(
        db, session.id, role="assistant", content=greeting
    )

    return ChatResponse(
        user_id=user_id,
        session_id=session.id,
        assistant_message=greeting,
        updated_signals=[],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatResponse:
    """嗜好学習チャット"""
    user_id = request.user_id
    user_message = request.message
    session_id = request.session_id

    # Check user exists and load profile
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get session
    if session_id:
        session = await session_manager.get_session(db, session_id)
    else:
        session = await session_manager.get_active_session(
            db, user_id, mode="preference_learning"
        )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add user message to session
    await session_manager.add_message(db, session.id, role="user", content=user_message)

    # Get context for LLM (session_summary + last_3_turns_raw)
    context_data = await session_manager.get_context_for_llm(db, session.id)
    conversation_history = context_data["last_3_turns_raw"]

    # Get last assistant message as question context
    question_context = ""
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            question_context = msg["content"]
            break

    # Get existing signals for deduplication
    existing_signals = [
        {"tag": s.tag, "category": s.category} for s in user.preference_signals
    ]

    # Extract signals from user message
    extraction_result = await preference_learner.extract_signals(
        user_message=user_message,
        context=question_context,
        existing_signals=existing_signals,
    )

    # Save new signals to database (with deduplication)
    new_signals = []
    for signal_data in extraction_result.get("signals", []):
        signal = await long_term_memory.add_signal(
            db,
            user_id=user_id,
            category=signal_data["category"],
            tag=signal_data["tag"],
            weight=signal_data["weight"],
            evidence=signal_data["evidence"],
        )
        new_signals.append(signal)

    # Update profile summary if we got new signals
    if new_signals:
        new_summary = await preference_learner.update_profile_summary(
            current_summary=user.profile.summary if user.profile else "",
            new_signals=extraction_result.get("signals", []),
        )
        if user.profile:
            user.profile.summary = new_summary
        else:
            profile = UserProfile(user_id=user_id, summary=new_summary)
            db.add(profile)

    await db.commit()

    # Refresh signals to get IDs
    for signal in new_signals:
        await db.refresh(signal)

    # Generate response or next question
    assistant_response = extraction_result.get("response", "")
    if not assistant_response:
        # Generate next question using context
        known_signals = [
            {
                "category": s.category,
                "tag": s.tag,
                "weight": s.weight,
            }
            for s in (user.preference_signals or []) + new_signals
        ]
        assistant_response = await preference_learner.generate_question(
            profile_summary=user.profile.summary if user.profile else "",
            known_signals=known_signals,
            conversation_history=conversation_history,
        )

    # Add assistant response to session
    await session_manager.add_message(
        db, session.id, role="assistant", content=assistant_response
    )

    # Check if summarization is needed (more than 3 turns)
    messages_to_summarize = await session_manager.get_turns_to_summarize(db, session.id)
    if messages_to_summarize:
        logger.info(
            f"Summarizing {len(messages_to_summarize)} messages for session {session.id}"
        )
        # Get current summary
        current_summary = context_data["session_summary"]

        # Generate new summary
        new_summary = await summarizer_agent.summarize_messages(
            existing_summary=current_summary,
            messages=messages_to_summarize,
        )

        # Update summary in database
        max_turn = max(m.turn_index for m in messages_to_summarize)
        await session_manager.update_session_summary(
            db, session.id, new_summary, max_turn
        )

        # Mark messages as summarized
        await session_manager.mark_messages_as_summarized(db, messages_to_summarize)

    return ChatResponse(
        user_id=user_id,
        session_id=session.id,
        assistant_message=assistant_response,
        updated_signals=[
            PreferenceSignalResponse.model_validate(s) for s in new_signals
        ],
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    嗜好学習チャット（ストリーミング）

    Server-Sent Events形式でレスポンスを返す。
    各チャンクは以下の形式:
    - data: {"type": "chunk", "content": "テキスト"}
    - data: {"type": "signals", "signals": [...]}
    - data: {"type": "done", "session_id": "..."}
    """
    user_id = request.user_id
    user_message = request.message
    session_id = request.session_id

    # Check user exists and load profile
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get session
    if session_id:
        session = await session_manager.get_session(db, session_id)
    else:
        session = await session_manager.get_active_session(
            db, user_id, mode="preference_learning"
        )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add user message to session
    await session_manager.add_message(db, session.id, role="user", content=user_message)

    # Get context for LLM
    context_data = await session_manager.get_context_for_llm(db, session.id)
    conversation_history = context_data["last_3_turns_raw"]

    # Get last assistant message as question context
    question_context = ""
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            question_context = msg["content"]
            break

    # Get existing signals for deduplication
    existing_signals = [
        {"tag": s.tag, "category": s.category} for s in user.preference_signals
    ]

    async def generate_stream() -> AsyncGenerator[str, None]:
        """SSE形式でストリームを生成"""
        full_response = ""

        try:
            # まず嗜好シグナルを抽出（非ストリーミング）
            extraction_result = await preference_learner.extract_signals(
                user_message=user_message,
                context=question_context,
                existing_signals=existing_signals,
            )

            # シグナルを保存（重複チェック付き）
            new_signals = []
            for signal_data in extraction_result.get("signals", []):
                signal = await long_term_memory.add_signal(
                    db,
                    user_id=user_id,
                    category=signal_data["category"],
                    tag=signal_data["tag"],
                    weight=signal_data["weight"],
                    evidence=signal_data["evidence"],
                )
                new_signals.append(signal)

            # シグナルがあればプロフィール更新→commit→SSE送信
            if new_signals:
                # プロフィール要約を先に更新
                new_summary = await preference_learner.update_profile_summary(
                    current_summary=user.profile.summary if user.profile else "",
                    new_signals=extraction_result.get("signals", []),
                )
                if user.profile:
                    user.profile.summary = new_summary

                # プロフィール更新をcommit（シグナルはadd_signal内でflush済み）
                await db.commit()

                signals_data = [
                    {
                        "id": str(signal.id),
                        "category": signal.category,
                        "tag": signal.tag,
                        "weight": signal.weight,
                    }
                    for signal in new_signals
                ]
                yield f"data: {json.dumps({'type': 'signals', 'signals': signals_data}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'profile_updated'}, ensure_ascii=False)}\n\n"

            # レスポンスをストリーミングで生成
            known_signals = [
                {"category": s.category, "tag": s.tag, "weight": s.weight}
                for s in (user.preference_signals or []) + new_signals
            ]

            # システムプロンプトを構築
            system_prompt = f"""あなたは旅行嗜好を学習するAIアシスタントです。
ユーザーの回答から興味・好みを理解し、さらに深掘りする質問をしてください。

ユーザープロフィール:
{user.profile.summary if user.profile else "まだ情報がありません"}

既知の嗜好:
{json.dumps(known_signals, ensure_ascii=False) if known_signals else "まだ情報がありません"}

会話履歴:
{json.dumps(conversation_history, ensure_ascii=False)}

ユーザーの回答に対して、自然に会話を続けてください。"""

            # ストリーミングでレスポンス生成
            async for chunk in llm_gateway.generate_stream(
                prompt=user_message,
                tier=ModelTier.LIGHT,
                system_prompt=system_prompt,
                agent_name="preference_learner",
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"

            # アシスタントメッセージをセッションに保存
            await session_manager.add_message(
                db, session.id, role="assistant", content=full_response
            )

            # 要約が必要か確認
            messages_to_summarize = await session_manager.get_turns_to_summarize(db, session.id)
            if messages_to_summarize:
                current_summary = context_data["session_summary"]
                new_summary = await summarizer_agent.summarize_messages(
                    existing_summary=current_summary,
                    messages=messages_to_summarize,
                )
                max_turn = max(m.turn_index for m in messages_to_summarize)
                await session_manager.update_session_summary(
                    db, session.id, new_summary, max_turn
                )
                await session_manager.mark_messages_as_summarized(db, messages_to_summarize)

            await db.commit()

            # 完了イベントを送信
            yield f"data: {json.dumps({'type': 'done', 'session_id': str(session.id)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/users/{user_id}/signals", response_model=list[PreferenceSignalResponse])
async def get_user_signals(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PreferenceSignal]:
    """ユーザーの嗜好シグナル一覧を取得"""
    result = await db.execute(
        select(PreferenceSignal).where(PreferenceSignal.user_id == user_id)
    )
    return list(result.scalars().all())


@router.post("/learning/complete", response_model=LearningCompletionResponse)
async def complete_learning(
    request: LearningCompletionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LearningCompletionResponse:
    """
    嗜好学習セッションを完了し、長期記憶を統合・整理する

    - セッションを非アクティブに
    - プロフィール要約を更新
    - 嗜好シグナルを統合・重複排除
    - 低重みシグナルを削除
    """
    user_id = request.user_id
    session_id = request.session_id

    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Complete learning session and consolidate memory
    consolidation_result = await long_term_memory.complete_learning_session(
        db, user_id, session_id
    )

    return LearningCompletionResponse(
        user_id=user_id,
        session_id=session_id,
        profile_summary=consolidation_result["profile_summary"],
        total_signals=len(consolidation_result["consolidated_signals"]),
        consolidated_signals=len(consolidation_result["consolidated_signals"]),
        removed_signals=consolidation_result.get("removed_signals", []),
    )


@router.post("/memory/consolidate", response_model=MemoryConsolidationResponse)
async def consolidate_memory(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MemoryConsolidationResponse:
    """
    長期記憶を手動で統合・整理する

    嗜好学習モード完了時以外にも、手動で統合を実行できる
    """
    # Check user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get active session if any
    session = await session_manager.get_active_session(
        db, user_id, mode="preference_learning"
    )
    session_id = session.id if session else None

    # Consolidate memory
    consolidation_result = await long_term_memory.consolidate_memory(
        db, user_id, session_id
    )

    # Cleanup and enforce limits
    cleaned = await long_term_memory.cleanup_low_weight_signals(db, user_id)
    limited = await long_term_memory.enforce_signal_limit(db, user_id)

    await db.commit()

    # Get final signal count
    memory = await long_term_memory.get_user_profile(db, user_id)

    return MemoryConsolidationResponse(
        user_id=user_id,
        profile_summary=consolidation_result["profile_summary"],
        signals_count=len(memory["signals"]),
        cleaned_signals=cleaned,
        limited_signals=limited,
    )
