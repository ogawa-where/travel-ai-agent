"""
Vector Store Service

CLAUDE.md セクション4.2の要件:
- Rerank（埋め込み類似度ベース）
- pgvector使用（後で埋め込み検索やrerankを入れる場合）

責務:
- ベクトルの保存と検索
- 類似度計算
- POIキャッシュへのベクトル保存
- pgvector対応（利用可能な場合）
"""

import logging
import math
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import POICache
from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)


class VectorStore:
    """ベクトルストアサービス"""

    def __init__(self):
        self._pgvector_available: bool | None = None

    async def check_pgvector(self, db: AsyncSession) -> bool:
        """
        pgvector拡張が利用可能かチェック

        Returns:
            利用可能な場合True
        """
        if self._pgvector_available is not None:
            return self._pgvector_available

        try:
            result = await db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
            )
            self._pgvector_available = result.scalar() is not None
        except Exception:
            self._pgvector_available = False

        if self._pgvector_available:
            logger.info("pgvector extension is available")
        else:
            logger.info("pgvector extension is not available, using fallback")

        return self._pgvector_available

    async def enable_pgvector(self, db: AsyncSession) -> bool:
        """
        pgvector拡張を有効化

        Returns:
            成功した場合True
        """
        try:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.commit()
            self._pgvector_available = True
            logger.info("pgvector extension enabled")
            return True
        except Exception as e:
            logger.warning(f"Failed to enable pgvector: {e}")
            self._pgvector_available = False
            return False

    # =========================================================================
    # 埋め込み生成
    # =========================================================================

    async def generate_embedding(self, text: str) -> list[float]:
        """
        テキストの埋め込みベクトルを生成

        Args:
            text: 埋め込むテキスト

        Returns:
            埋め込みベクトル
        """
        try:
            return await llm_gateway.embed(text)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return []

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        複数テキストの埋め込みベクトルを並列生成

        Args:
            texts: 埋め込むテキストのリスト

        Returns:
            埋め込みベクトルのリスト
        """
        import asyncio

        results = await asyncio.gather(
            *[self.generate_embedding(t) for t in texts],
            return_exceptions=True,
        )

        embeddings = []
        for result in results:
            if isinstance(result, Exception):
                embeddings.append([])
            else:
                embeddings.append(result)

        return embeddings

    # =========================================================================
    # 類似度計算
    # =========================================================================

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        コサイン類似度を計算

        Args:
            vec1: ベクトル1
            vec2: ベクトル2

        Returns:
            類似度（0.0〜1.0）
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # コサイン類似度を0-1に正規化
        return (dot_product / (norm1 * norm2) + 1) / 2

    def euclidean_distance(self, vec1: list[float], vec2: list[float]) -> float:
        """
        ユークリッド距離を計算

        Args:
            vec1: ベクトル1
            vec2: ベクトル2

        Returns:
            距離（0.0以上）
        """
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return float("inf")

        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))

    # =========================================================================
    # POIキャッシュ操作
    # =========================================================================

    async def store_poi_with_embedding(
        self,
        db: AsyncSession,
        poi_data: dict[str, Any],
    ) -> POICache:
        """
        POIを埋め込みベクトル付きで保存

        Args:
            db: データベースセッション
            poi_data: POIデータ（name, category, location, details等）

        Returns:
            保存されたPOICache
        """
        # 埋め込み用テキストを構築
        embed_text = self._build_embed_text(poi_data)

        # 埋め込みを生成
        embedding = await self.generate_embedding(embed_text)

        # POICacheを作成
        poi = POICache(
            name=poi_data.get("name", ""),
            category=poi_data.get("category", ""),
            location=poi_data.get("location", ""),
            details=poi_data.get("details", {}),
            source_url=poi_data.get("source_url", ""),
            source_name=poi_data.get("source_name", ""),
            embedding=embedding if embedding else None,
        )

        db.add(poi)
        await db.flush()

        logger.debug(f"Stored POI with embedding: {poi.name}")
        return poi

    async def find_similar_pois(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        category: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict]:
        """
        類似POIを検索

        Args:
            db: データベースセッション
            query_embedding: クエリの埋め込みベクトル
            category: カテゴリでフィルタ（オプション）
            limit: 最大取得件数
            min_similarity: 最小類似度

        Returns:
            類似POIのリスト（similarity付き）
        """
        # pgvectorが利用可能な場合はSQL検索
        if await self.check_pgvector(db):
            return await self._find_similar_pgvector(
                db, query_embedding, category, limit, min_similarity
            )

        # フォールバック: Python側で計算
        return await self._find_similar_fallback(
            db, query_embedding, category, limit, min_similarity
        )

    async def _find_similar_pgvector(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        category: str | None,
        limit: int,
        min_similarity: float,
    ) -> list[dict]:
        """pgvectorを使用した類似検索"""
        # pgvector用のSQLクエリ
        # 注: 実際のpgvectorカラム追加後に有効化
        # 現在はフォールバックと同じ実装
        return await self._find_similar_fallback(
            db, query_embedding, category, limit, min_similarity
        )

    async def _find_similar_fallback(
        self,
        db: AsyncSession,
        query_embedding: list[float],
        category: str | None,
        limit: int,
        min_similarity: float,
    ) -> list[dict]:
        """Python側での類似検索（フォールバック）"""
        # POIを取得
        query = select(POICache)
        if category:
            query = query.where(POICache.category == category)

        result = await db.execute(query)
        pois = list(result.scalars().all())

        # 類似度を計算
        results = []
        for poi in pois:
            if not poi.embedding:
                continue

            similarity = self.cosine_similarity(query_embedding, poi.embedding)
            if similarity >= min_similarity:
                results.append(
                    {
                        "poi": poi,
                        "similarity": similarity,
                    }
                )

        # 類似度でソート
        results.sort(key=lambda x: x["similarity"], reverse=True)

        return results[:limit]

    async def update_poi_embedding(
        self,
        db: AsyncSession,
        poi_id: str,
    ) -> bool:
        """
        POIの埋め込みを更新

        Args:
            db: データベースセッション
            poi_id: POIのID

        Returns:
            成功した場合True
        """
        result = await db.execute(select(POICache).where(POICache.id == poi_id))
        poi = result.scalar_one_or_none()

        if not poi:
            return False

        embed_text = self._build_embed_text(
            {
                "name": poi.name,
                "category": poi.category,
                "location": poi.location,
                "details": poi.details,
            }
        )

        embedding = await self.generate_embedding(embed_text)
        if embedding:
            poi.embedding = embedding
            await db.flush()
            return True

        return False

    def _build_embed_text(self, poi_data: dict) -> str:
        """POI埋め込み用テキストを構築"""
        parts = []

        if poi_data.get("name"):
            parts.append(poi_data["name"])
        if poi_data.get("category"):
            parts.append(poi_data["category"])
        if poi_data.get("location"):
            parts.append(poi_data["location"])

        details = poi_data.get("details", {})
        if details.get("description"):
            parts.append(details["description"][:300])
        if details.get("tags"):
            parts.append(" ".join(details["tags"][:5]))

        return " ".join(parts)

    # =========================================================================
    # バッチ処理
    # =========================================================================

    async def batch_update_embeddings(
        self,
        db: AsyncSession,
        category: str | None = None,
        batch_size: int = 10,
    ) -> dict:
        """
        POIの埋め込みを一括更新

        Args:
            db: データベースセッション
            category: カテゴリでフィルタ（オプション）
            batch_size: バッチサイズ

        Returns:
            処理結果
        """
        # 埋め込みがないPOIを取得
        query = select(POICache).where(POICache.embedding.is_(None))
        if category:
            query = query.where(POICache.category == category)

        result = await db.execute(query)
        pois = list(result.scalars().all())

        updated = 0
        failed = 0

        for i in range(0, len(pois), batch_size):
            batch = pois[i : i + batch_size]

            # テキストを構築
            texts = [
                self._build_embed_text(
                    {
                        "name": poi.name,
                        "category": poi.category,
                        "location": poi.location,
                        "details": poi.details,
                    }
                )
                for poi in batch
            ]

            # 埋め込みを生成
            embeddings = await self.generate_embeddings(texts)

            # 更新
            for poi, embedding in zip(batch, embeddings):
                if embedding:
                    poi.embedding = embedding
                    updated += 1
                else:
                    failed += 1

            await db.flush()
            logger.info(f"Batch update progress: {updated} updated, {failed} failed")

        await db.commit()

        return {
            "total": len(pois),
            "updated": updated,
            "failed": failed,
        }


# シングルトンインスタンス
vector_store = VectorStore()
