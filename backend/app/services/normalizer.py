"""
Normalizer / Deduper

検索結果の正規化と重複排除を担当（決定論コード）。
LLMを使用せず、ルールベースで処理。
"""

import logging
import re
from difflib import SequenceMatcher

from app.schemas.travel_planning import POICategory, POISearchResult

logger = logging.getLogger(__name__)


class Normalizer:
    """POI情報の正規化"""

    def normalize_poi(self, poi: POISearchResult) -> POISearchResult:
        """
        POI情報を正規化

        Args:
            poi: 正規化対象のPOI

        Returns:
            正規化されたPOI
        """
        return POISearchResult(
            name=self._normalize_name(poi.name),
            category=poi.category,
            location=self._normalize_location(poi.location),
            description=self._normalize_description(poi.description),
            price_range=self._normalize_price_range(poi.price_range),
            duration_minutes=poi.duration_minutes,
            opening_hours=self._normalize_opening_hours(poi.opening_hours),
            rating=poi.rating,
            tags=self._normalize_tags(poi.tags),
            source_url=poi.source_url,
            relevance_score=poi.relevance_score,
            source_name=poi.source_name,
        )

    def _normalize_name(self, name: str) -> str:
        """名前を正規化"""
        if not name:
            return ""
        # 余分な空白を削除
        name = re.sub(r"\s+", " ", name.strip())
        # 特殊文字を正規化
        name = name.replace("　", " ")  # 全角スペースを半角に
        # 括弧内の補足情報を簡潔に
        name = re.sub(r"\s*[（(].{20,}[)）]", "", name)
        return name[:100]  # 最大100文字

    def _normalize_location(self, location: str) -> str:
        """住所を正規化"""
        if not location:
            return ""
        # 郵便番号を削除
        location = re.sub(r"〒?\d{3}-?\d{4}", "", location)
        # 余分な空白を削除
        location = re.sub(r"\s+", " ", location.strip())
        return location[:200]

    def _normalize_description(self, description: str) -> str:
        """説明を正規化"""
        if not description:
            return ""
        # 余分な空白・改行を削除
        description = re.sub(r"\s+", " ", description.strip())
        # HTMLタグを削除
        description = re.sub(r"<[^>]+>", "", description)
        return description[:500]  # 最大500文字

    def _normalize_price_range(self, price_range: str) -> str:
        """価格帯を正規化"""
        if not price_range:
            return ""
        # 全角数字を半角に
        price_range = price_range.translate(
            str.maketrans("０１２３４５６７８９", "0123456789")
        )
        return price_range.strip()

    def _normalize_opening_hours(self, hours: str) -> str:
        """営業時間を正規化"""
        if not hours:
            return ""
        # 時間形式を統一
        hours = re.sub(r"(\d{1,2}):(\d{2})", r"\1:\2", hours)
        return hours.strip()[:100]

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        """タグを正規化"""
        if not tags:
            return []
        # 重複を除去し、小文字化
        normalized = []
        seen = set()
        for tag in tags:
            tag_lower = tag.strip().lower()
            if tag_lower and tag_lower not in seen:
                normalized.append(tag.strip())
                seen.add(tag_lower)
        return normalized[:10]  # 最大10個


class Deduper:
    """POIの重複排除"""

    def __init__(self, similarity_threshold: float = 0.8):
        """
        Args:
            similarity_threshold: 重複とみなす類似度の閾値
        """
        self.similarity_threshold = similarity_threshold

    def dedupe(self, pois: list[POISearchResult]) -> list[POISearchResult]:
        """
        POIリストから重複を除去

        Args:
            pois: 重複を含む可能性のあるPOIリスト

        Returns:
            重複を除去したPOIリスト
        """
        if not pois:
            return []

        unique_pois: list[POISearchResult] = []

        for poi in pois:
            is_duplicate = False

            for existing in unique_pois:
                if self._is_duplicate(poi, existing):
                    is_duplicate = True
                    # スコアが高い方を残す
                    if poi.relevance_score > existing.relevance_score:
                        unique_pois.remove(existing)
                        unique_pois.append(poi)
                    break

            if not is_duplicate:
                unique_pois.append(poi)

        logger.debug(
            f"Dedupe: {len(pois)} -> {len(unique_pois)} POIs "
            f"(removed {len(pois) - len(unique_pois)} duplicates)"
        )

        return unique_pois

    def _is_duplicate(self, poi1: POISearchResult, poi2: POISearchResult) -> bool:
        """2つのPOIが重複かどうか判定"""
        # カテゴリが異なれば重複ではない
        if poi1.category != poi2.category:
            return False

        # 名前の類似度をチェック
        name_similarity = self._calculate_similarity(poi1.name, poi2.name)
        if name_similarity >= self.similarity_threshold:
            return True

        # URLが同じなら重複
        if poi1.source_url and poi1.source_url == poi2.source_url:
            return True

        return False

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """2つの文字列の類似度を計算"""
        if not s1 or not s2:
            return 0.0
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()


class NormalizerDeduper:
    """正規化と重複排除を統合したサービス"""

    def __init__(self, similarity_threshold: float = 0.8):
        self.normalizer = Normalizer()
        self.deduper = Deduper(similarity_threshold)

    def process(
        self,
        pois: list[POISearchResult],
        normalize: bool = True,
        dedupe: bool = True,
    ) -> list[POISearchResult]:
        """
        POIリストを正規化・重複排除

        Args:
            pois: 処理対象のPOIリスト
            normalize: 正規化を行うか
            dedupe: 重複排除を行うか

        Returns:
            処理後のPOIリスト
        """
        result = pois

        if normalize:
            result = [self.normalizer.normalize_poi(poi) for poi in result]

        if dedupe:
            result = self.deduper.dedupe(result)

        return result

    def process_by_category(
        self,
        pois_by_category: dict[POICategory, list[POISearchResult]],
    ) -> dict[POICategory, list[POISearchResult]]:
        """
        カテゴリごとにPOIリストを正規化・重複排除

        Args:
            pois_by_category: カテゴリごとのPOIリスト

        Returns:
            処理後のカテゴリごとのPOIリスト
        """
        return {
            category: self.process(pois) for category, pois in pois_by_category.items()
        }


# Singleton instance
normalizer_deduper = NormalizerDeduper()
