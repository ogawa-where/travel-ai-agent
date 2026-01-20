"""
セッション管理サービス

CLAUDE.md セクション5.1の短期記憶ルールを実装:
- 直近3ターンを生ログで保持
- それ以前はsession_summaryとして保持
- 各ターン完了後、履歴が3ターンを超えたら最古の1ターンを要約に吸収
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import Message, Session, SessionSummary

logger = logging.getLogger(__name__)

MAX_RAW_TURNS = 3  # 直近3ターンを生ログで保持


class SessionManager:
    """セッション管理サービス"""

    async def create_session(
        self,
        db: AsyncSession,
        user_id: str,
        mode: str = "preference_learning",
    ) -> Session:
        """新規セッションを作成"""
        session = Session(user_id=user_id, mode=mode)
        db.add(session)
        await db.flush()

        # 空の要約を作成
        summary = SessionSummary(session_id=session.id, content="")
        db.add(summary)
        await db.commit()

        return session

    async def get_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> Session | None:
        """セッションを取得"""
        result = await db.execute(
            select(Session)
            .options(
                selectinload(Session.messages),
                selectinload(Session.summary),
            )
            .where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_session(
        self,
        db: AsyncSession,
        user_id: str,
        mode: str = "preference_learning",
    ) -> Session | None:
        """ユーザーのアクティブなセッションを取得"""
        result = await db.execute(
            select(Session)
            .options(
                selectinload(Session.messages),
                selectinload(Session.summary),
            )
            .where(
                Session.user_id == user_id,
                Session.mode == mode,
                Session.is_active == True,  # noqa: E712
            )
            .order_by(Session.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def add_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
    ) -> Message:
        """メッセージを追加"""
        # 現在の最大ターンインデックスを取得
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.turn_index.desc())
            .limit(1)
        )
        last_message = result.scalar_one_or_none()

        if role == "user":
            # ユーザー発言は新しいターンの開始
            turn_index = (last_message.turn_index + 1) if last_message else 1
        else:
            # アシスタント発言は同じターン
            turn_index = last_message.turn_index if last_message else 1

        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            turn_index=turn_index,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)

        return message

    async def get_context_for_llm(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> dict[str, Any]:
        """
        LLM呼び出し用のコンテキストを取得

        Returns:
            {
                "session_summary": str,  # 古い文脈の圧縮
                "last_3_turns_raw": list[dict],  # 直近3ターンの生ログ
            }
        """
        session = await self.get_session(db, session_id)
        if not session:
            return {"session_summary": "", "last_3_turns_raw": []}

        # 要約を取得
        session_summary = session.summary.content if session.summary else ""

        # 直近3ターンの未要約メッセージを取得
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.is_summarized == False,  # noqa: E712
            )
            .order_by(Message.turn_index.desc(), Message.created_at.desc())
        )
        messages = list(result.scalars().all())

        # ターンでグループ化して直近3ターンを取得
        turns: dict[int, list[Message]] = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        # 直近3ターンのみ
        recent_turn_indices = sorted(turns.keys(), reverse=True)[:MAX_RAW_TURNS]

        # 時系列順に並べ替え
        last_3_turns_raw = []
        for turn_idx in sorted(recent_turn_indices):
            for msg in sorted(turns[turn_idx], key=lambda m: m.created_at):
                last_3_turns_raw.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                    }
                )

        return {
            "session_summary": session_summary,
            "last_3_turns_raw": last_3_turns_raw,
        }

    async def get_turns_to_summarize(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> list[Message]:
        """
        要約すべきメッセージを取得

        直近3ターンより古い未要約メッセージを返す
        """
        # 全ての未要約メッセージを取得
        result = await db.execute(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.is_summarized == False,  # noqa: E712
            )
            .order_by(Message.turn_index.asc(), Message.created_at.asc())
        )
        messages = list(result.scalars().all())

        # ターンでグループ化
        turns: dict[int, list[Message]] = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        # 4ターン以上ある場合、古いターンを返す
        turn_indices = sorted(turns.keys())
        if len(turn_indices) <= MAX_RAW_TURNS:
            return []

        # 要約すべきターン（直近3ターン以外）
        turns_to_summarize_indices = turn_indices[:-MAX_RAW_TURNS]
        messages_to_summarize = []
        for turn_idx in turns_to_summarize_indices:
            messages_to_summarize.extend(turns[turn_idx])

        return messages_to_summarize

    async def mark_messages_as_summarized(
        self,
        db: AsyncSession,
        messages: list[Message],
    ) -> None:
        """メッセージを要約済みとしてマーク"""
        for msg in messages:
            msg.is_summarized = True
        await db.commit()

    async def update_session_summary(
        self,
        db: AsyncSession,
        session_id: str,
        new_summary: str,
        last_summarized_turn: int,
    ) -> None:
        """セッション要約を更新"""
        result = await db.execute(
            select(SessionSummary).where(SessionSummary.session_id == session_id)
        )
        summary = result.scalar_one_or_none()

        if summary:
            summary.content = new_summary
            summary.last_summarized_turn = last_summarized_turn
        else:
            summary = SessionSummary(
                session_id=session_id,
                content=new_summary,
                last_summarized_turn=last_summarized_turn,
            )
            db.add(summary)

        await db.commit()

    async def close_session(
        self,
        db: AsyncSession,
        session_id: str,
    ) -> None:
        """セッションを終了"""
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
            await db.commit()


# Singleton instance
session_manager = SessionManager()
