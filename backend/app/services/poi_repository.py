"""
POI Repository Service

PTSアーキテクチャ対応:
- 検索結果をPOI DBに保存
- 同じ(destination, category, name)の組み合わせで上書き更新
- TravelSearchResultでリクエストとPOIを紐付け
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.domain.models import POICache, TravelSearchResult
from app.schemas.travel_planning import POISearchResult, POICategory

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """timezone-naive な UTC 現在時刻（TIMESTAMP WITHOUT TIME ZONE 用）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class POIRepository:
    """POIリポジトリ（PTSアーキテクチャ対応）"""

    async def save_search_results(
        self,
        db: AsyncSession,
        destination: str,
        category: POICategory,
        pois: list[POISearchResult],
    ) -> list[POICache]:
        """
        検索結果をPOI DBに保存（UPSERT）

        Args:
            db: データベースセッション
            destination: 検索目的地
            category: POIカテゴリ
            pois: 検索結果のPOIリスト

        Returns:
            保存されたPOICacheのリスト
        """
        saved_pois: list[POICache] = []

        for poi in pois:
            # PTS形式のフィールドを準備
            poi_values = {
                # 基本情報
                "destination": destination,
                "name": poi.name,
                "category": category.value,
                "description": poi.description or "",
                # 位置情報
                "location": poi.location or "",
                "address": getattr(poi, "address", "") or "",
                "latitude": getattr(poi, "latitude", None),
                "longitude": getattr(poi, "longitude", None),
                # 評価・レビュー情報（PTS形式）
                "rating": poi.rating,
                "review_count": getattr(poi, "review_count", None),
                # 価格情報
                "price_level": getattr(poi, "price_level", None),
                "price_range": poi.price_range or "",
                "budget_per_person": getattr(poi, "budget_per_person", None),
                # 時間情報
                "hours": {"text": poi.opening_hours} if poi.opening_hours else None,
                "duration_minutes": poi.duration_minutes,
                # 特徴・タグ（PTS形式）
                "features": getattr(poi, "features", []) or [],
                "tags": poi.tags or [],
                # ソース情報
                "source_url": poi.source_url or "",
                "source_name": poi.source_name or "tavily",
                # メタデータ
                "details": {"relevance_score": poi.relevance_score},
                "fetched_at": _utcnow(),
            }

            # UPSERT: 既存のPOIがあれば更新、なければ挿入
            stmt = insert(POICache).values(**poi_values).on_conflict_do_update(
                index_elements=["destination", "category", "name"],
                set_={k: v for k, v in poi_values.items() if k not in ["destination", "name", "category"]},
            ).returning(POICache)

            result = await db.execute(stmt)
            cached_poi = result.scalar_one_or_none()

            if cached_poi:
                saved_pois.append(cached_poi)
            else:
                # フォールバック: 挿入後に取得
                existing = await db.execute(
                    select(POICache).where(
                        and_(
                            POICache.destination == destination,
                            POICache.category == category.value,
                            POICache.name == poi.name,
                        )
                    )
                )
                cached_poi = existing.scalar_one_or_none()
                if cached_poi:
                    saved_pois.append(cached_poi)

        await db.flush()

        logger.info(
            f"Saved {len(saved_pois)} POIs for {destination}/{category.value}"
        )

        return saved_pois

    async def get_pois_for_destination(
        self,
        db: AsyncSession,
        destination: str,
        category: POICategory | None = None,
    ) -> list[POICache]:
        """
        目的地のPOIを取得

        Args:
            db: データベースセッション
            destination: 目的地
            category: カテゴリ（Noneなら全カテゴリ）

        Returns:
            POIリスト
        """
        query = select(POICache).where(POICache.destination == destination)

        if category:
            query = query.where(POICache.category == category.value)

        result = await db.execute(query)
        return list(result.scalars().all())

    async def link_pois_to_request(
        self,
        db: AsyncSession,
        request_id: str,
        poi_scores: list[tuple[POICache, float, float]],
    ) -> list[TravelSearchResult]:
        """
        POIをTravelPlanRequestに紐付け（リランク後のスコア付き）

        Args:
            db: データベースセッション
            request_id: TravelPlanRequestのID
            poi_scores: (POICache, rerank_score, constraint_score)のリスト

        Returns:
            作成されたTravelSearchResultのリスト
        """
        results: list[TravelSearchResult] = []

        for poi, rerank_score, constraint_score in poi_scores:
            # 総合スコア計算（重み付け平均）
            total_score = (rerank_score * 0.6) + (constraint_score * 0.4)

            search_result = TravelSearchResult(
                request_id=request_id,
                poi_id=poi.id,
                category=poi.category,
                rerank_score=rerank_score,
                constraint_score=constraint_score,
                total_score=total_score,
            )
            db.add(search_result)
            results.append(search_result)

        await db.flush()

        logger.info(
            f"Linked {len(results)} POIs to request {request_id}"
        )

        return results

    async def get_ranked_pois_for_request(
        self,
        db: AsyncSession,
        request_id: str,
        category: POICategory | None = None,
        limit: int = 20,
    ) -> list[tuple[TravelSearchResult, POICache]]:
        """
        リクエストに紐付けられたPOIをスコア順で取得

        Args:
            db: データベースセッション
            request_id: TravelPlanRequestのID
            category: カテゴリ（Noneなら全カテゴリ）
            limit: 取得件数上限

        Returns:
            (TravelSearchResult, POICache)のリスト（スコア降順）
        """
        query = (
            select(TravelSearchResult, POICache)
            .join(POICache, TravelSearchResult.poi_id == POICache.id)
            .where(TravelSearchResult.request_id == request_id)
            .order_by(TravelSearchResult.total_score.desc())
            .limit(limit)
        )

        if category:
            query = query.where(TravelSearchResult.category == category.value)

        result = await db.execute(query)
        return list(result.all())

    async def mark_pois_as_selected(
        self,
        db: AsyncSession,
        search_result_ids: list[str],
        reasons: dict[str, str] | None = None,
    ) -> None:
        """
        Plannerが選択したPOIをマーク

        Args:
            db: データベースセッション
            search_result_ids: 選択されたTravelSearchResultのIDリスト
            reasons: POI ID -> 選択理由の辞書
        """
        reasons = reasons or {}

        for result_id in search_result_ids:
            result = await db.get(TravelSearchResult, result_id)
            if result:
                result.is_selected = True
                result.selection_reason = reasons.get(result_id, "")

        await db.flush()


# シングルトンインスタンス
poi_repository = POIRepository()
