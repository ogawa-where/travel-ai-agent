"""旅行企画モードAPIルーター"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.domain.models import TravelPlan, TravelPlanRequest, User
from app.orchestrator.travel_planning import travel_orchestrator
from app.schemas.travel_planning import (
    TravelChatRequest,
    TravelChatResponse,
    TravelPlanFeedbackRequest,
    TravelPlanFeedbackResponse,
    TravelPlanRequestCreate,
    TravelPlanRequestResponse,
    TravelPlanResponse,
)
from app.services.long_term_memory import long_term_memory
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/travel", tags=["travel-planning"])


@router.post("/plan", response_model=TravelPlanResponse)
async def create_travel_plan(
    request: TravelPlanRequestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TravelPlan:
    """
    旅行プランを生成

    ユーザーの自然言語入力から旅程を生成します。
    """
    # ユーザーを取得
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile), selectinload(User.preference_signals))
        .where(User.id == request.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # セッションを取得または作成
    if request.session_id:
        session = await session_manager.get_session(db, request.session_id)
    else:
        session = await session_manager.get_active_session(
            db, request.user_id, mode="travel_planning"
        )

    if not session:
        session = await session_manager.create_session(
            db, request.user_id, mode="travel_planning"
        )

    # TravelPlanRequestを作成
    plan_request = TravelPlanRequest(
        session_id=session.id,
        user_id=request.user_id,
        raw_request=request.raw_request,
        status="pending",
    )
    db.add(plan_request)
    await db.flush()

    # プロフィール情報を準備
    profile_summary = user.profile.summary if user.profile else ""
    preference_signals = [
        {
            "category": s.category,
            "tag": s.tag,
            "weight": s.weight,
            "evidence": s.evidence,
        }
        for s in (user.preference_signals or [])
    ]

    try:
        # Orchestratorで旅行プランを生成
        travel_plan = await travel_orchestrator.execute(
            db=db,
            request=plan_request,
            user_profile_summary=profile_summary,
            preference_signals=preference_signals,
        )
        return travel_plan
    except Exception as e:
        logger.error(f"Failed to create travel plan: {e}")
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {str(e)}")


@router.get("/plan/{plan_id}", response_model=TravelPlanResponse)
async def get_travel_plan(
    plan_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TravelPlan:
    """旅行プランを取得"""
    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("/requests/{user_id}", response_model=list[TravelPlanRequestResponse])
async def get_user_requests(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TravelPlanRequest]:
    """ユーザーの旅行企画リクエスト一覧を取得"""
    result = await db.execute(
        select(TravelPlanRequest)
        .where(TravelPlanRequest.user_id == user_id)
        .order_by(TravelPlanRequest.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/chat", response_model=TravelChatResponse)
async def travel_chat(
    request: TravelChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TravelChatResponse:
    """
    旅行企画チャット

    ユーザーとの対話を通じて旅行プランを作成します。
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
        session = await session_manager.get_active_session(
            db, user_id, mode="travel_planning"
        )

    if not session:
        session = await session_manager.create_session(
            db, user_id, mode="travel_planning"
        )

    # ユーザーメッセージを保存
    await session_manager.add_message(db, session.id, role="user", content=user_message)

    # メッセージを分析して旅行プラン生成が必要か判断
    # （簡易的な実装：「プランを作って」などのキーワードで判断）
    should_generate_plan = _should_generate_plan(user_message)

    if should_generate_plan:
        # プランを生成
        plan_request = TravelPlanRequest(
            session_id=session.id,
            user_id=user_id,
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

            assistant_message = _format_plan_response(travel_plan)

            await session_manager.add_message(
                db, session.id, role="assistant", content=assistant_message
            )

            return TravelChatResponse(
                user_id=user_id,
                session_id=session.id,
                assistant_message=assistant_message,
                plan_request_id=plan_request.id,
                plan=TravelPlanResponse.model_validate(travel_plan),
                status="completed",
            )
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            error_message = "申し訳ありません。プランの生成中にエラーが発生しました。もう一度お試しください。"
            await session_manager.add_message(
                db, session.id, role="assistant", content=error_message
            )
            return TravelChatResponse(
                user_id=user_id,
                session_id=session.id,
                assistant_message=error_message,
                status="chatting",
            )
    else:
        # 通常の応答（要件収集フェーズ）
        assistant_message = _generate_clarification_response(user_message)

        await session_manager.add_message(
            db, session.id, role="assistant", content=assistant_message
        )

        return TravelChatResponse(
            user_id=user_id,
            session_id=session.id,
            assistant_message=assistant_message,
            status="chatting",
        )


@router.post("/chat/start", response_model=TravelChatResponse)
async def start_travel_chat(
    user_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TravelChatResponse:
    """旅行企画チャットを開始"""
    # ユーザーを確認
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # セッションを作成
    session = await session_manager.create_session(db, user_id, mode="travel_planning")

    greeting = """こんにちは！旅行企画モードへようこそ。

あなたの理想の旅行プランを一緒に作りましょう！
まずは、以下のような情報を教えてください：

- どこに行きたいですか？（目的地）
- いつ、何日間の旅行ですか？
- 予算はどのくらいですか？
- 何人で行きますか？
- どんなことをしたいですか？（観光、グルメ、体験など）

例：「来月、2泊3日で京都に一人旅したい。予算は5万円くらいで、神社仏閣巡りと美味しい和食を楽しみたい」
"""

    await session_manager.add_message(
        db, session.id, role="assistant", content=greeting
    )

    return TravelChatResponse(
        user_id=user_id,
        session_id=session.id,
        assistant_message=greeting,
        status="chatting",
    )


def _should_generate_plan(message: str) -> bool:
    """プラン生成が必要か判断"""
    keywords = [
        "プランを作",
        "旅程を作",
        "計画を立て",
        "スケジュールを作",
        "作って",
        "考えて",
        "お願い",
    ]
    return any(keyword in message for keyword in keywords)


def _generate_clarification_response(message: str) -> str:
    """要件収集フェーズの応答を生成"""
    # 簡易的な応答（本来はLLMで生成）
    return """ありがとうございます！

もう少し詳しく教えていただけますか？

- 目的地はどこですか？
- 日程（いつから何日間）は決まっていますか？
- 予算はどのくらいですか？
- 特にやりたいことや食べたいものはありますか？

情報が揃ったら「プランを作って」とおっしゃってください！"""


def _format_plan_response(plan: TravelPlan) -> str:
    """プランを読みやすい形式にフォーマット"""
    itinerary = plan.itinerary
    lines = [
        f"## {itinerary.get('title', '旅程')}\n",
        itinerary.get("summary", ""),
        "",
    ]

    for day in itinerary.get("days", []):
        lines.append(f"\n### {day.get('day_number', '')}日目: {day.get('theme', '')}")

        for item in day.get("items", []):
            poi = item.get("poi", {})
            time_range = f"{item.get('time_start', '')}-{item.get('time_end', '')}"
            lines.append(f"- {time_range} **{poi.get('name', '')}**")
            if item.get("notes"):
                lines.append(f"  {item['notes']}")

        if day.get("accommodation"):
            acc = day["accommodation"]
            lines.append(f"- 【宿泊】{acc.get('name', '')}")

    if plan.rationale:
        lines.append(f"\n---\n{plan.rationale}")

    return "\n".join(lines)


@router.post("/feedback", response_model=TravelPlanFeedbackResponse)
async def submit_feedback(
    request: TravelPlanFeedbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TravelPlanFeedbackResponse:
    """
    旅行プランへのフィードバックを送信し、長期記憶に反映

    ユーザーのフィードバックから嗜好を学習し、プロフィールを更新します。
    """
    user_id = request.user_id
    plan_id = request.plan_id
    feedback = request.feedback

    # ユーザーを確認
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # プランを取得
    result = await db.execute(select(TravelPlan).where(TravelPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # プランの概要を作成
    itinerary = plan.itinerary
    plan_summary = f"""
目的地: {itinerary.get('title', '不明')}
概要: {itinerary.get('summary', '')}
ハイライト: {', '.join(itinerary.get('highlights', []))}
"""

    # フィードバックを長期記憶に反映
    feedback_result = await long_term_memory.integrate_feedback(
        db=db,
        user_id=user_id,
        plan_summary=plan_summary,
        feedback=feedback,
    )

    return TravelPlanFeedbackResponse(
        user_id=user_id,
        plan_id=plan_id,
        updated_signals_count=len(feedback_result.get("updated_signals", [])),
        profile_updated=bool(feedback_result.get("profile_update")),
    )
