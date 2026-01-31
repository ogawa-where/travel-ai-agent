"""
POI Cache Service

POI情報と抽出された体験をキャッシュし、
体験ベースの埋め込みを提供する。
"""

import logging
from datetime import datetime, timezone, timedelta


def _utcnow() -> datetime:
    """timezone-naive な UTC 現在時刻（TIMESTAMP WITHOUT TIME ZONE 用）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import POICache
from app.schemas.travel_planning import POISearchResult
from app.services.experience_extractor import experience_extractor
from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)

# キャッシュの有効期限（日）
CACHE_EXPIRY_DAYS = 7
# 体験抽出の有効期限（日）
EXPERIENCE_EXPIRY_DAYS = 30


class POICacheService:
    """POIキャッシュサービス"""

    async def get_or_create_cached_poi(
        self,
        db: AsyncSession,
        poi: POISearchResult,
        extract_experiences: bool = True,
    ) -> POICache:
        """
        キャッシュからPOIを取得、なければ作成

        Args:
            db: データベースセッション
            poi: 検索結果のPOI
            extract_experiences: 体験を抽出するか

        Returns:
            キャッシュされたPOI
        """
        # キャッシュを検索（名前とカテゴリで一致）
        result = await db.execute(
            select(POICache).where(
                POICache.name == poi.name,
                POICache.category == poi.category.value,
            )
        )
        cached = result.scalar_one_or_none()

        if cached:
            # キャッシュが有効期限内かチェック
            if self._is_cache_valid(cached):
                # 体験が未抽出または期限切れの場合は抽出
                if extract_experiences and self._needs_experience_extraction(cached):
                    await self._extract_and_cache_experiences(db, cached, poi)
                return cached

        # 新規作成
        cached = POICache(
            name=poi.name,
            category=poi.category.value,
            location=poi.location or "",
            details={
                "description": poi.description,
                "price_range": poi.price_range,
                "duration_minutes": poi.duration_minutes,
                "opening_hours": poi.opening_hours,
                "rating": poi.rating,
                "tags": poi.tags,
            },
            source_url=poi.source_url or "",
            source_name=poi.source_name or "tavily",
        )
        db.add(cached)
        await db.flush()

        if extract_experiences:
            await self._extract_and_cache_experiences(db, cached, poi)

        return cached

    async def get_experiences_for_pois(
        self,
        db: AsyncSession,
        pois: list[POISearchResult],
    ) -> dict[str, list[str]]:
        """
        複数のPOIの体験を取得

        Args:
            db: データベースセッション
            pois: POIリスト

        Returns:
            POI名 -> 体験リストの辞書
        """
        experiences_map = {}

        for poi in pois:
            cached = await self.get_or_create_cached_poi(db, poi)
            if cached.experiences:
                experiences_map[poi.name] = cached.experiences
            else:
                # 体験が取得できなかった場合はタグをフォールバック
                experiences_map[poi.name] = poi.tags or []

        return experiences_map

    async def get_experience_embedding(
        self,
        db: AsyncSession,
        poi: POISearchResult,
    ) -> list[float]:
        """
        POIの体験ベース埋め込みを取得

        Args:
            db: データベースセッション
            poi: POI

        Returns:
            埋め込みベクトル
        """
        cached = await self.get_or_create_cached_poi(db, poi)

        # 埋め込みがキャッシュされていればそれを返す
        if cached.embedding:
            return cached.embedding

        # 体験テキストを構築
        experience_text = self._build_experience_text(cached)

        # 埋め込みを取得（埋め込みタスクはrerankerにルーティング）
        try:
            embedding = await llm_gateway.embed(experience_text, agent_name="reranker")
            # キャッシュに保存
            cached.embedding = embedding
            await db.flush()
            return embedding
        except Exception as e:
            logger.warning(f"Failed to get embedding for {poi.name}: {e}")
            return []

    def _is_cache_valid(self, cached: POICache) -> bool:
        """キャッシュが有効期限内か"""
        if not cached.fetched_at:
            return False
        expiry = cached.fetched_at + timedelta(days=CACHE_EXPIRY_DAYS)
        return _utcnow() < expiry

    def _needs_experience_extraction(self, cached: POICache) -> bool:
        """体験の抽出が必要か"""
        if not cached.experiences:
            return True
        if not cached.experiences_extracted_at:
            return True
        expiry = cached.experiences_extracted_at + timedelta(days=EXPERIENCE_EXPIRY_DAYS)
        return _utcnow() > expiry

    async def _extract_and_cache_experiences(
        self,
        db: AsyncSession,
        cached: POICache,
        poi: POISearchResult,
    ) -> None:
        """体験を抽出してキャッシュ"""
        try:
            experiences = await experience_extractor.extract_experiences(
                poi_name=poi.name,
                poi_category=poi.category.value,
                poi_tags=poi.tags or [],
                feedback_type="good",  # 検索時は中立的に抽出
            )

            # 体験タグのリストを保存
            experience_tags = [exp.tag for exp in experiences]
            cached.experiences = experience_tags
            cached.experiences_extracted_at = _utcnow()
            # 埋め込みをクリア（再計算が必要）
            cached.embedding = None
            await db.flush()

            logger.info(f"Extracted {len(experience_tags)} experiences for {poi.name}")

        except Exception as e:
            logger.warning(f"Failed to extract experiences for {poi.name}: {e}")
            # 失敗時はタグをフォールバック
            cached.experiences = poi.tags or []
            cached.experiences_extracted_at = _utcnow()
            await db.flush()

    def _build_experience_text(self, cached: POICache) -> str:
        """体験ベースの埋め込み用テキストを構築"""
        parts = []

        # 体験タグ
        if cached.experiences:
            parts.append(" ".join(cached.experiences))

        # 詳細からの補足情報
        details = cached.details or {}
        if details.get("description"):
            # 説明文から体験に関連する部分を抽出（場所名は除く）
            desc = details["description"]
            # 簡易的に「できる」「楽しめる」「体験」などを含む文を重視
            if any(kw in desc for kw in ["できる", "楽しめる", "体験", "味わえる", "堪能"]):
                parts.append(desc)

        # タグ（体験がない場合のフォールバック）
        if not cached.experiences and details.get("tags"):
            parts.append(" ".join(details["tags"]))

        return " ".join(parts) if parts else cached.name


# シングルトンインスタンス
poi_cache_service = POICacheService()
