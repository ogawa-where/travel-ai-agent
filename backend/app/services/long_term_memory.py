"""
Long-term Memory Service

CLAUDE.md セクション5.2に基づく長期記憶管理サービス。

長期記憶は2層構造:
1) 人間可読のプロフィール要約（文章）
2) 構造化された嗜好シグナル（JSON）

責務:
- プロフィール要約の読み書き
- 嗜好シグナルの管理（追加・更新・削除・統合）
- 重複排除と優先度管理（肥大化防止）
"""

import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.profile_updater import profile_updater
from app.domain.models import PreferenceSignal, Session, SessionSummary, UserProfile

logger = logging.getLogger(__name__)

# 最大シグナル数（肥大化防止）
MAX_SIGNALS_PER_USER = 30
# 低重みシグナルの閾値
LOW_WEIGHT_THRESHOLD = 0.2


class LongTermMemoryService:
    """長期記憶管理サービス"""

    async def get_user_profile(self, db: AsyncSession, user_id: str) -> dict[str, Any]:
        """
        ユーザーの長期記憶を取得

        Returns:
            {
                "profile_summary": str,
                "signals": list[dict]
            }
        """
        # Get profile
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        # Get signals
        result = await db.execute(
            select(PreferenceSignal)
            .where(PreferenceSignal.user_id == user_id)
            .order_by(PreferenceSignal.weight.desc())
        )
        signals = list(result.scalars().all())

        return {
            "profile_summary": profile.summary if profile else "",
            "signals": [
                {
                    "id": s.id,
                    "category": s.category,
                    "tag": s.tag,
                    "weight": s.weight,
                    "evidence": s.evidence,
                    "extra_data": s.extra_data,
                }
                for s in signals
            ],
        }

    async def consolidate_memory(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        長期記憶を統合・整理（嗜好学習モード完了時に呼び出し）

        Args:
            db: データベースセッション
            user_id: ユーザーID
            session_id: セッションID（セッション要約を使用する場合）

        Returns:
            統合結果
        """
        # Get current profile and signals
        current_memory = await self.get_user_profile(db, user_id)

        # Get session summary if provided
        session_summary = ""
        if session_id:
            result = await db.execute(
                select(SessionSummary).where(SessionSummary.session_id == session_id)
            )
            summary = result.scalar_one_or_none()
            if summary:
                session_summary = summary.content

        # Call Profile Updater Agent to consolidate
        consolidation_result = await profile_updater.consolidate_profile(
            current_summary=current_memory["profile_summary"],
            signals=current_memory["signals"],
            session_summary=session_summary,
        )

        # Apply consolidation result to database
        await self._apply_consolidation(
            db,
            user_id,
            consolidation_result,
        )

        logger.info(
            f"Memory consolidated for user {user_id}: "
            f"signals={len(consolidation_result['consolidated_signals'])}, "
            f"removed={len(consolidation_result['removed_signals'])}"
        )

        return consolidation_result

    async def add_signal(
        self,
        db: AsyncSession,
        user_id: str,
        category: str,
        tag: str,
        weight: float,
        evidence: str,
        extra_data: dict | None = None,
    ) -> PreferenceSignal:
        """
        嗜好シグナルを追加（重複チェック付き）

        既存の同じカテゴリ・タグがあれば更新、なければ新規作成
        """
        # Check for existing signal with same category and tag
        result = await db.execute(
            select(PreferenceSignal).where(
                PreferenceSignal.user_id == user_id,
                PreferenceSignal.category == category,
                PreferenceSignal.tag == tag,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing signal (average weights)
            new_weight = (existing.weight + weight) / 2
            existing.weight = min(1.0, new_weight)
            existing.evidence = evidence  # Use latest evidence
            if extra_data:
                existing.extra_data = {**existing.extra_data, **extra_data}
            await db.flush()
            return existing
        else:
            # Create new signal
            signal = PreferenceSignal(
                user_id=user_id,
                category=category,
                tag=tag,
                weight=weight,
                evidence=evidence,
                extra_data=extra_data or {},
            )
            db.add(signal)
            await db.flush()
            return signal

    async def update_signal(
        self,
        db: AsyncSession,
        signal_id: str,
        weight: float | None = None,
        evidence: str | None = None,
    ) -> bool:
        """嗜好シグナルを更新"""
        updates = {}
        if weight is not None:
            updates["weight"] = min(1.0, max(0.0, weight))
        if evidence is not None:
            updates["evidence"] = evidence

        if not updates:
            return False

        result = await db.execute(
            update(PreferenceSignal)
            .where(PreferenceSignal.id == signal_id)
            .values(**updates)
        )
        return result.rowcount > 0

    async def remove_signal(self, db: AsyncSession, signal_id: str) -> bool:
        """嗜好シグナルを削除"""
        result = await db.execute(
            delete(PreferenceSignal).where(PreferenceSignal.id == signal_id)
        )
        return result.rowcount > 0

    async def update_profile_summary(
        self,
        db: AsyncSession,
        user_id: str,
        summary: str,
    ) -> UserProfile:
        """プロフィール要約を更新"""
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if profile:
            profile.summary = summary
        else:
            profile = UserProfile(user_id=user_id, summary=summary)
            db.add(profile)

        await db.flush()
        return profile

    async def integrate_feedback(
        self,
        db: AsyncSession,
        user_id: str,
        plan_summary: str,
        feedback: str,
    ) -> dict[str, Any]:
        """
        旅行プランへのフィードバックを長期記憶に反映

        Args:
            db: データベースセッション
            user_id: ユーザーID
            plan_summary: 生成されたプランの概要
            feedback: ユーザーのフィードバック

        Returns:
            更新結果
        """
        # Get current memory
        current_memory = await self.get_user_profile(db, user_id)

        # Call Profile Updater Agent
        feedback_result = await profile_updater.integrate_feedback(
            current_summary=current_memory["profile_summary"],
            signals=current_memory["signals"],
            plan_summary=plan_summary,
            feedback=feedback,
        )

        # Apply updates
        for signal_update in feedback_result.get("updated_signals", []):
            action = signal_update.get("action", "add")

            if action == "add":
                await self.add_signal(
                    db,
                    user_id,
                    category=signal_update["category"],
                    tag=signal_update["tag"],
                    weight=signal_update["weight"],
                    evidence=signal_update["evidence"],
                )
            elif action == "remove":
                # Find and remove signal
                result = await db.execute(
                    select(PreferenceSignal).where(
                        PreferenceSignal.user_id == user_id,
                        PreferenceSignal.tag == signal_update["tag"],
                    )
                )
                signal = result.scalar_one_or_none()
                if signal:
                    await self.remove_signal(db, signal.id)
            elif action == "update":
                # Find and update signal
                result = await db.execute(
                    select(PreferenceSignal).where(
                        PreferenceSignal.user_id == user_id,
                        PreferenceSignal.tag == signal_update["tag"],
                    )
                )
                signal = result.scalar_one_or_none()
                if signal:
                    await self.update_signal(
                        db,
                        signal.id,
                        weight=signal_update["weight"],
                        evidence=signal_update["evidence"],
                    )

        # Update profile if needed
        if feedback_result.get("profile_update"):
            result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if profile:
                profile.summary = profile.summary + " " + feedback_result["profile_update"]
            else:
                await self.update_profile_summary(
                    db, user_id, feedback_result["profile_update"]
                )

        await db.commit()

        logger.info(
            f"Feedback integrated for user {user_id}: "
            f"updated_signals={len(feedback_result.get('updated_signals', []))}"
        )

        return feedback_result

    async def cleanup_low_weight_signals(
        self,
        db: AsyncSession,
        user_id: str,
        threshold: float = LOW_WEIGHT_THRESHOLD,
    ) -> int:
        """低重みのシグナルを削除"""
        result = await db.execute(
            delete(PreferenceSignal).where(
                PreferenceSignal.user_id == user_id,
                PreferenceSignal.weight < threshold,
            )
        )
        return result.rowcount

    async def enforce_signal_limit(
        self,
        db: AsyncSession,
        user_id: str,
        max_signals: int = MAX_SIGNALS_PER_USER,
    ) -> int:
        """シグナル数の上限を強制（低重みから削除）"""
        # Get all signals ordered by weight
        result = await db.execute(
            select(PreferenceSignal)
            .where(PreferenceSignal.user_id == user_id)
            .order_by(PreferenceSignal.weight.desc())
        )
        signals = list(result.scalars().all())

        if len(signals) <= max_signals:
            return 0

        # Delete excess signals (lowest weight first)
        signals_to_delete = signals[max_signals:]
        deleted_count = 0

        for signal in signals_to_delete:
            await db.execute(
                delete(PreferenceSignal).where(PreferenceSignal.id == signal.id)
            )
            deleted_count += 1

        return deleted_count

    async def complete_learning_session(
        self,
        db: AsyncSession,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        嗜好学習セッションを完了し、長期記憶を更新

        Args:
            db: データベースセッション
            user_id: ユーザーID
            session_id: セッションID

        Returns:
            統合結果
        """
        # Mark session as inactive
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False

        # Consolidate memory
        consolidation_result = await self.consolidate_memory(
            db, user_id, session_id
        )

        # Cleanup low weight signals
        cleaned = await self.cleanup_low_weight_signals(db, user_id)
        if cleaned:
            logger.info(f"Cleaned {cleaned} low-weight signals for user {user_id}")

        # Enforce signal limit
        limited = await self.enforce_signal_limit(db, user_id)
        if limited:
            logger.info(f"Removed {limited} excess signals for user {user_id}")

        await db.commit()

        return {
            **consolidation_result,
            "cleaned_signals": cleaned,
            "limited_signals": limited,
        }

    async def _apply_consolidation(
        self,
        db: AsyncSession,
        user_id: str,
        consolidation_result: dict[str, Any],
    ) -> None:
        """統合結果をデータベースに適用"""
        # Update profile summary
        await self.update_profile_summary(
            db, user_id, consolidation_result["profile_summary"]
        )

        # Delete removed signals
        for removed_tag in consolidation_result.get("removed_signals", []):
            result = await db.execute(
                select(PreferenceSignal).where(
                    PreferenceSignal.user_id == user_id,
                    PreferenceSignal.tag == removed_tag,
                )
            )
            signal = result.scalar_one_or_none()
            if signal:
                await db.execute(
                    delete(PreferenceSignal).where(PreferenceSignal.id == signal.id)
                )

        # Update or add consolidated signals
        for signal_data in consolidation_result.get("consolidated_signals", []):
            await self.add_signal(
                db,
                user_id,
                category=signal_data["category"],
                tag=signal_data["tag"],
                weight=signal_data["weight"],
                evidence=signal_data["evidence"],
            )

        await db.flush()


# Singleton instance
long_term_memory = LongTermMemoryService()
