"""統合チャットAPIルーター

モード切替を廃止し、自然な会話の中で自動的に
嗜好学習と旅行企画を行う統合チャットシステム。
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.preference_learner import preference_learner
from app.agents.summarizer import summarizer_agent
from app.database import get_db
from app.domain.models import PreferenceSignal, TravelPlan, TravelPlanRequest, User
from app.orchestrator.travel_planning import travel_orchestrator
from app.schemas.travel_planning import TravelPlanResponse
from app.schemas.unified_chat import (
    ChatIntent,
    LearnedPreference,
    UnifiedChatRequest,
    UnifiedChatResponse,
)
from app.services.intent_classifier import intent_classifier
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["unified-chat"])


@router.post("/start", response_model=UnifiedChatResponse)
async def start_chat(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UnifiedChatResponse:
    """統合チャットを開始"""
    # ユーザーを確認
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 新しいセッションを作成（モードは"unified"）
    session = await session_manager.create_session(db, user_id, mode="unified")

    greeting = """こんにちは！Travel AIです。

旅行の相談から、あなたの好みを学習しながら最適なプランをご提案します。

どこか行きたい場所はありますか？
または、まずはあなたの旅行の好みを教えてください！

例えば：
- 「来月、京都に2泊3日で行きたい」
- 「温泉が好きで、静かな場所が好みです」
- 「美味しい海鮮料理を食べたい」

なんでもお気軽にどうぞ！"""

    await session_manager.add_message(
        db, session.id, role="assistant", content=greeting
    )

    return UnifiedChatResponse(
        user_id=user_id,
        session_id=session.id,
        assistant_message=greeting,
        intent=ChatIntent.GENERAL_CHAT,
        learned_preferences=[],
        plan=None,
        plan_status=None,
    )


@router.post("", response_model=UnifiedChatResponse)
async def chat(
    request: UnifiedChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UnifiedChatResponse:
    """
    統合チャット

    自然な会話の中で：
    1. 常に嗜好を抽出・学習（トースト通知用）
    2. 意図を判定（旅行相談 or 一般会話）
    3. 適切なハンドラーにルーティング
    """
    user_id = request.user_id
    user_message = request.message
    session_id = request.session_id

    # ユーザーを取得
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # セッションを取得または作成
    if session_id:
        session = await session_manager.get_session(db, session_id)
    else:
        session = await session_manager.get_active_session(db, user_id, mode="unified")

    if not session:
        session = await session_manager.create_session(db, user_id, mode="unified")

    # ユーザーメッセージを保存
    await session_manager.add_message(db, session.id, role="user", content=user_message)

    # コンテキストを取得
    context_data = await session_manager.get_context_for_llm(db, session.id)
    conversation_history = context_data["last_3_turns_raw"]

    # 1. 常に嗜好を抽出（トースト通知用）
    learned_preferences = await _extract_preferences(
        db, user, user_message, conversation_history
    )

    # 2. 意図を分類
    classification = intent_classifier.classify(
        message=user_message,
        conversation_context=conversation_history,
    )

    # 3. 意図に応じた処理
    if classification.intent == ChatIntent.TRAVEL_PLANNING:
        response = await _handle_travel_planning(
            db=db,
            user=user,
            user_message=user_message,
            session=session,
            context_data=context_data,
            learned_preferences=learned_preferences,
        )
    else:
        response = await _handle_general_chat(
            db=db,
            user=user,
            user_message=user_message,
            session=session,
            context_data=context_data,
            learned_preferences=learned_preferences,
        )

    # 4. 要約が必要か確認
    await _check_and_summarize(db, session.id, context_data)

    return response


async def _extract_preferences(
    db: AsyncSession,
    user: User,
    user_message: str,
    conversation_history: list[dict],
) -> list[LearnedPreference]:
    """
    ユーザーメッセージから嗜好を抽出し、DBに保存

    Returns:
        学習した嗜好のリスト（トースト通知用）
    """
    # 直前のアシスタントメッセージを取得（コンテキスト用）
    question_context = ""
    for msg in reversed(conversation_history):
        if msg["role"] == "assistant":
            question_context = msg["content"]
            break

    # 既存シグナルを取得（重複回避用）
    existing_signals = [
        {"tag": s.tag, "category": s.category} for s in (user.preference_signals or [])
    ]

    # 嗜好を抽出
    extraction_result = await preference_learner.extract_signals(
        user_message=user_message,
        context=question_context,
        existing_signals=existing_signals,
    )

    learned_preferences = []
    new_signals = []

    for signal_data in extraction_result.get("signals", []):
        # 既存シグナルとの重複チェック
        existing_signal = None
        for s in user.preference_signals or []:
            if s.tag == signal_data["tag"] and s.category == signal_data["category"]:
                existing_signal = s
                break

        if existing_signal:
            # 重みを更新（上書きではなく平均）
            new_weight = (existing_signal.weight + signal_data["weight"]) / 2
            existing_signal.weight = min(new_weight, 1.0)
            existing_signal.evidence = signal_data["evidence"]

            learned_preferences.append(
                LearnedPreference(
                    category=signal_data["category"],
                    tag=signal_data["tag"],
                    weight=existing_signal.weight,
                    is_new=False,
                )
            )
        else:
            # 新規シグナルを作成
            signal = PreferenceSignal(
                user_id=user.id,
                category=signal_data["category"],
                tag=signal_data["tag"],
                weight=signal_data["weight"],
                evidence=signal_data["evidence"],
            )
            db.add(signal)
            new_signals.append(signal)

            learned_preferences.append(
                LearnedPreference(
                    category=signal_data["category"],
                    tag=signal_data["tag"],
                    weight=signal_data["weight"],
                    is_new=True,
                )
            )

    # プロフィール要約を更新
    if learned_preferences:
        new_summary = await preference_learner.update_profile_summary(
            current_summary=user.profile.summary if user.profile else "",
            new_signals=extraction_result.get("signals", []),
        )
        if user.profile:
            user.profile.summary = new_summary

    await db.commit()

    # 新規シグナルのIDを取得
    for signal in new_signals:
        await db.refresh(signal)

    return learned_preferences


async def _handle_travel_planning(
    db: AsyncSession,
    user: User,
    user_message: str,
    session,
    context_data: dict,
    learned_preferences: list[LearnedPreference],
) -> UnifiedChatResponse:
    """旅行企画意図の処理"""

    # プラン生成が明示的に要求されているか確認
    should_generate = intent_classifier.should_generate_plan(user_message)

    if should_generate:
        return await _generate_travel_plan(
            db=db,
            user=user,
            user_message=user_message,
            session=session,
            learned_preferences=learned_preferences,
        )
    else:
        # 要件収集フェーズ
        assistant_message = await _generate_travel_response(
            user_message=user_message,
            context=context_data,
            user=user,
        )

        await session_manager.add_message(
            db, session.id, role="assistant", content=assistant_message
        )

        return UnifiedChatResponse(
            user_id=user.id,
            session_id=session.id,
            assistant_message=assistant_message,
            intent=ChatIntent.TRAVEL_PLANNING,
            learned_preferences=learned_preferences,
            plan=None,
            plan_status="chatting",
        )


async def _generate_travel_plan(
    db: AsyncSession,
    user: User,
    user_message: str,
    session,
    learned_preferences: list[LearnedPreference],
) -> UnifiedChatResponse:
    """旅行プランを生成"""
    plan_request = TravelPlanRequest(
        session_id=session.id,
        user_id=user.id,
        raw_request=user_message,
        status="pending",
    )
    db.add(plan_request)
    await db.flush()

    profile_summary = user.profile.summary if user.profile else ""
    preference_signals = [
        {
            "category": s.category,
            "tag": s.tag,
            "weight": s.weight,
        }
        for s in (user.preference_signals or [])
    ]

    try:
        travel_plan = await travel_orchestrator.execute(
            db=db,
            request=plan_request,
            user_profile_summary=profile_summary,
            preference_signals=preference_signals,
        )

        assistant_message = _format_plan_summary(travel_plan)

        await session_manager.add_message(
            db, session.id, role="assistant", content=assistant_message
        )

        return UnifiedChatResponse(
            user_id=user.id,
            session_id=session.id,
            assistant_message=assistant_message,
            intent=ChatIntent.TRAVEL_PLANNING,
            learned_preferences=learned_preferences,
            plan=TravelPlanResponse.model_validate(travel_plan),
            plan_status="completed",
        )
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        error_message = "申し訳ありません。プランの生成中にエラーが発生しました。もう一度お試しください。"

        await session_manager.add_message(
            db, session.id, role="assistant", content=error_message
        )

        return UnifiedChatResponse(
            user_id=user.id,
            session_id=session.id,
            assistant_message=error_message,
            intent=ChatIntent.TRAVEL_PLANNING,
            learned_preferences=learned_preferences,
            plan=None,
            plan_status="chatting",
        )


async def _generate_travel_response(
    user_message: str,
    context: dict,
    user: User,
) -> str:
    """旅行相談への応答を生成"""
    # TODO: LLMで生成（現在は簡易的な応答）
    return """ありがとうございます！旅行プランを作成する準備ができました。

もう少し詳しく教えていただけますか？
- 目的地はどこですか？
- 日程（いつから何日間）は決まっていますか？
- 予算はどのくらいですか？
- 特にやりたいことや食べたいものはありますか？

情報が揃ったら「プランを作って」とおっしゃってください！"""


async def _handle_general_chat(
    db: AsyncSession,
    user: User,
    user_message: str,
    session,
    context_data: dict,
    learned_preferences: list[LearnedPreference],
) -> UnifiedChatResponse:
    """一般会話（嗜好学習含む）の処理"""

    # 次の質問を生成
    known_signals = [
        {
            "category": s.category,
            "tag": s.tag,
            "weight": s.weight,
        }
        for s in (user.preference_signals or [])
    ]

    assistant_response = await preference_learner.generate_question(
        profile_summary=user.profile.summary if user.profile else "",
        known_signals=known_signals,
        conversation_history=context_data["last_3_turns_raw"],
    )

    await session_manager.add_message(
        db, session.id, role="assistant", content=assistant_response
    )

    return UnifiedChatResponse(
        user_id=user.id,
        session_id=session.id,
        assistant_message=assistant_response,
        intent=ChatIntent.GENERAL_CHAT,
        learned_preferences=learned_preferences,
        plan=None,
        plan_status=None,
    )


async def _check_and_summarize(
    db: AsyncSession,
    session_id: str,
    context_data: dict,
) -> None:
    """必要に応じてメッセージを要約"""
    messages_to_summarize = await session_manager.get_turns_to_summarize(db, session_id)

    if messages_to_summarize:
        logger.info(
            f"Summarizing {len(messages_to_summarize)} messages for session {session_id}"
        )
        current_summary = context_data["session_summary"]

        new_summary = await summarizer_agent.summarize_messages(
            existing_summary=current_summary,
            messages=messages_to_summarize,
        )

        max_turn = max(m.turn_index for m in messages_to_summarize)
        await session_manager.update_session_summary(db, session_id, new_summary, max_turn)
        await session_manager.mark_messages_as_summarized(db, messages_to_summarize)


def _format_plan_summary(plan: TravelPlan) -> str:
    """プランの短い要約を生成（詳細はカードで表示）"""
    itinerary = plan.itinerary
    title = itinerary.get("title", "旅程")
    summary = itinerary.get("summary", "")
    days = len(itinerary.get("days", []))

    return f"""旅行プランを作成しました！

**{title}**
{days}日間の旅程をご用意しました。

{summary}

下のカードで詳細をご確認ください。
ご意見やご要望があればお聞かせください！"""
