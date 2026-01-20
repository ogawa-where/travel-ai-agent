"""
Rerank Agent

埋め込み類似度ベースでPOIをリランクする。
Ollama embedding (nomic-embed-text) を使用。
"""

import asyncio
import logging
import math

from app.schemas.travel_planning import (
    POIRanked,
    POISearchResult,
    RerankInput,
    RerankOutput,
    TravelWishes,
)
from app.services.llm_gateway import llm_gateway

logger = logging.getLogger(__name__)


class RerankAgent:
    """埋め込み類似度ベースのリランクエージェント"""

    def __init__(self):
        self._embedding_cache: dict[str, list[float]] = {}

    async def rerank(self, input_data: RerankInput) -> RerankOutput:
        """
        POI候補をユーザー嗜好に基づいてリランク

        Args:
            input_data: リランク入力（候補、プロフィール、嗜好）

        Returns:
            ランク付けされたPOIリスト
        """
        if not input_data.candidates:
            return RerankOutput(ranked_items=[])

        # ユーザー嗜好を表すテキストを構築
        preference_text = self._build_preference_text(
            input_data.user_profile_summary,
            input_data.preference_signals,
            input_data.wishes,
        )

        # 嗜好テキストの埋め込みを取得
        preference_embedding = await self._get_embedding(preference_text)

        # 各候補の埋め込みを取得してスコアリング
        ranked_items = await self._score_candidates(
            input_data.candidates,
            preference_embedding,
            input_data.wishes,
        )

        # スコア順にソート
        ranked_items.sort(key=lambda x: x.final_score, reverse=True)

        logger.info(
            f"Rerank completed: {len(input_data.candidates)} candidates -> "
            f"top score={ranked_items[0].final_score:.3f} if ranked_items else 0"
        )

        return RerankOutput(ranked_items=ranked_items)

    def _build_preference_text(
        self,
        profile_summary: str,
        preference_signals: list[dict],
        wishes: TravelWishes,
    ) -> str:
        """ユーザー嗜好を表すテキストを構築"""
        parts = []

        if profile_summary:
            parts.append(f"プロフィール: {profile_summary}")

        if preference_signals:
            signals_text = ", ".join(
                f"{s.get('tag', '')}({s.get('category', '')})"
                for s in preference_signals
                if s.get("category") == "likes"
            )
            if signals_text:
                parts.append(f"好み: {signals_text}")

        if wishes.activities:
            parts.append(f"やりたいこと: {', '.join(wishes.activities)}")
        if wishes.experiences:
            parts.append(f"体験したいこと: {', '.join(wishes.experiences)}")
        if wishes.food_preferences:
            parts.append(f"食の好み: {', '.join(wishes.food_preferences)}")
        if wishes.priority:
            parts.append(f"重視: {wishes.priority}")
        if wishes.mood:
            parts.append(f"雰囲気: {wishes.mood}")

        return " ".join(parts) if parts else "旅行を楽しみたい"

    async def _get_embedding(self, text: str) -> list[float]:
        """テキストの埋め込みを取得（キャッシュあり）"""
        cache_key = text[:200]  # キャッシュキーは最初の200文字

        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        try:
            embedding = await llm_gateway.embed(text)
            self._embedding_cache[cache_key] = embedding
            return embedding
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            # 空の埋め込みを返す（フォールバック）
            return []

    async def _score_candidates(
        self,
        candidates: list[POISearchResult],
        preference_embedding: list[float],
        wishes: TravelWishes,
    ) -> list[POIRanked]:
        """候補をスコアリング"""
        ranked_items = []

        # 候補の埋め込みを並列で取得
        candidate_texts = [
            f"{c.name} {c.description} {' '.join(c.tags)}" for c in candidates
        ]

        embeddings = await asyncio.gather(
            *[self._get_embedding(text) for text in candidate_texts],
            return_exceptions=True,
        )

        for i, candidate in enumerate(candidates):
            embedding = embeddings[i]

            # 嗜好との類似度スコア
            if (
                isinstance(embedding, Exception)
                or not embedding
                or not preference_embedding
            ):
                preference_score = 0.5  # デフォルト
            else:
                preference_score = self._cosine_similarity(
                    preference_embedding, embedding
                )

            # 元の検索スコアと組み合わせ
            relevance_score = candidate.relevance_score
            final_score = 0.4 * relevance_score + 0.6 * preference_score

            # マッチ理由を生成
            match_reasons = self._generate_match_reasons(candidate, wishes)

            ranked_items.append(
                POIRanked(
                    name=candidate.name,
                    category=candidate.category,
                    location=candidate.location,
                    description=candidate.description,
                    price_range=candidate.price_range,
                    duration_minutes=candidate.duration_minutes,
                    opening_hours=candidate.opening_hours,
                    rating=candidate.rating,
                    tags=candidate.tags,
                    source_url=candidate.source_url,
                    relevance_score=relevance_score,
                    preference_score=preference_score,
                    final_score=final_score,
                    match_reasons=match_reasons,
                )
            )

        return ranked_items

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """コサイン類似度を計算"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)
        # 0-1の範囲に正規化（コサイン類似度は-1から1）
        return (similarity + 1) / 2

    def _generate_match_reasons(
        self,
        candidate: POISearchResult,
        wishes: TravelWishes,
    ) -> list[str]:
        """マッチ理由を生成"""
        reasons = []

        # タグとwishesの照合
        candidate_tags_lower = [t.lower() for t in candidate.tags]
        description_lower = (
            candidate.description.lower() if candidate.description else ""
        )

        for activity in wishes.activities:
            if activity.lower() in description_lower or activity.lower() in " ".join(
                candidate_tags_lower
            ):
                reasons.append(f"「{activity}」に関連")

        for experience in wishes.experiences:
            if experience.lower() in description_lower:
                reasons.append(f"「{experience}」の体験が可能")

        for food in wishes.food_preferences:
            if food.lower() in description_lower or food.lower() in " ".join(
                candidate_tags_lower
            ):
                reasons.append(f"「{food}」が楽しめる")

        if wishes.mood and wishes.mood.lower() in description_lower:
            reasons.append(f"「{wishes.mood}」な雰囲気")

        return reasons[:3]  # 最大3つ

    def clear_cache(self):
        """埋め込みキャッシュをクリア"""
        self._embedding_cache.clear()


# Singleton instance
rerank_agent = RerankAgent()
