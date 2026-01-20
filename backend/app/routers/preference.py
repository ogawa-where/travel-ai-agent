import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.preference_learner import preference_learner
from app.database import get_db
from app.domain.models import PreferenceSignal, User, UserProfile
from app.schemas.preference import (
    ChatRequest,
    ChatResponse,
    PreferenceSignalResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preference", tags=["preference"])

# In-memory conversation history (for MVP; should be moved to DB later)
conversation_histories: dict[str, list[dict[str, str]]] = {}


@router.post("/users", response_model=UserResponse)
async def create_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """新規ユーザーを作成"""
    user = User()
    db.add(user)
    await db.flush()  # Flush to get user.id assigned

    profile = UserProfile(user_id=user.id, summary="")
    db.add(profile)
    await db.commit()

    # Load relationships
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

    # Initialize conversation history
    conversation_histories[user_id] = []

    # Generate initial greeting
    greeting = await preference_learner.get_initial_greeting()

    # Add to history
    conversation_histories[user_id].append({
        "role": "assistant",
        "content": greeting,
    })

    return ChatResponse(
        user_id=user_id,
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

    # Check user exists and load profile
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Initialize history if not exists
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    # Add user message to history
    conversation_histories[user_id].append({
        "role": "user",
        "content": user_message,
    })

    # Get context (last assistant message as question context)
    context = ""
    for msg in reversed(conversation_histories[user_id]):
        if msg["role"] == "assistant":
            context = msg["content"]
            break

    # Extract signals from user message
    extraction_result = await preference_learner.extract_signals(
        user_message=user_message,
        context=context,
    )

    # Save new signals to database
    new_signals = []
    for signal_data in extraction_result.get("signals", []):
        signal = PreferenceSignal(
            user_id=user_id,
            category=signal_data["category"],
            tag=signal_data["tag"],
            weight=signal_data["weight"],
            evidence=signal_data["evidence"],
        )
        db.add(signal)
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
        # Generate next question
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
            conversation_history=conversation_histories[user_id],
        )

    # Add assistant response to history
    conversation_histories[user_id].append({
        "role": "assistant",
        "content": assistant_response,
    })

    return ChatResponse(
        user_id=user_id,
        assistant_message=assistant_response,
        updated_signals=[
            PreferenceSignalResponse.model_validate(s) for s in new_signals
        ],
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
