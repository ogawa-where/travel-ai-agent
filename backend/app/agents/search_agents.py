"""
Search Agents

検索を担当するエージェント群（I/O主体）。
- ActivitySearchAgent: 体験・観光の検索
- FoodSearchAgent: 食・レストランの検索
- HotelSearchAgent: 宿泊先の検索

3体を非同期で並列実行可能。
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod

from app.schemas.travel_planning import (
    POICategory,
    POISearchResult,
    SearchQuery,
    SearchResult,
)
from app.services.tavily_client import tavily_client

logger = logging.getLogger(__name__)


class BaseSearchAgent(ABC):
    """検索エージェントの基底クラス"""

    def __init__(self, category: POICategory):
        self.category = category

    @abstractmethod
    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """検索キーワードを構築"""
        pass

    @abstractmethod
    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果からPOI情報を抽出"""
        pass

    async def search(self, query: SearchQuery) -> SearchResult:
        """
        検索を実行

        Args:
            query: 検索クエリ

        Returns:
            検索結果
        """
        start_time = time.time()

        keywords = self._build_keywords(query)

        try:
            raw_results = await tavily_client.search_for_travel(
                destination=query.destination,
                category=self.category.value,
                keywords=keywords,
                max_results=15,
            )

            items = []
            for result in raw_results.get("results", []):
                poi = self._extract_poi_from_result(result)
                if poi:
                    items.append(poi)

            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"{self.__class__.__name__} search completed: "
                f"destination={query.destination} "
                f"results={len(items)} "
                f"time={elapsed_ms}ms"
            )

            return SearchResult(
                category=self.category,
                query=f"{query.destination} {' '.join(keywords)}",
                items=items,
                source="tavily",
                search_time_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error(f"{self.__class__.__name__} search failed: {e}")
            return SearchResult(
                category=self.category,
                query=f"{query.destination} {' '.join(keywords)}",
                items=[],
                source="tavily",
                search_time_ms=int((time.time() - start_time) * 1000),
            )


class ActivitySearchAgent(BaseSearchAgent):
    """体験・観光検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.ACTIVITY)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """体験・観光用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        # 制約から追加キーワードを抽出
        constraints = query.constraints
        if constraints.get("activities"):
            keywords.extend(constraints["activities"])
        if constraints.get("experiences"):
            keywords.extend(constraints["experiences"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果からアクティビティPOIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        # 基本情報を抽出
        return POISearchResult(
            name=title,
            category=POICategory.ACTIVITY,
            location="",  # 後で正規化時に抽出
            description=content[:300] if content else "",
            price_range="",
            duration_minutes=None,
            opening_hours="",
            rating=None,
            tags=self._extract_tags_from_content(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_tags_from_content(self, content: str) -> list[str]:
        """コンテンツからタグを抽出"""
        tags = []
        tag_keywords = [
            "自然",
            "文化",
            "歴史",
            "体験",
            "アウトドア",
            "インドア",
            "家族",
            "カップル",
            "グループ",
            "ソロ",
            "絶景",
            "パワースポット",
            "温泉",
            "神社",
            "寺院",
            "美術館",
            "博物館",
        ]
        content_lower = content.lower() if content else ""
        for keyword in tag_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]  # 最大5個


class FoodSearchAgent(BaseSearchAgent):
    """食・レストラン検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.FOOD)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """食・レストラン用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        constraints = query.constraints
        if constraints.get("food_preferences"):
            keywords.extend(constraints["food_preferences"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果から食POIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        return POISearchResult(
            name=title,
            category=POICategory.FOOD,
            location="",
            description=content[:300] if content else "",
            price_range=self._extract_price_range(content),
            duration_minutes=60,  # デフォルト1時間
            opening_hours="",
            rating=None,
            tags=self._extract_food_tags(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_price_range(self, content: str) -> str:
        """価格帯を抽出"""
        if not content:
            return ""
        # 簡易的な価格帯抽出
        if "高級" in content or "贅沢" in content:
            return "¥10,000~"
        if "リーズナブル" in content or "お手頃" in content:
            return "~¥2,000"
        return ""

    def _extract_food_tags(self, content: str) -> list[str]:
        """食関連のタグを抽出"""
        tags = []
        food_keywords = [
            "和食",
            "洋食",
            "中華",
            "イタリアン",
            "フレンチ",
            "寿司",
            "ラーメン",
            "居酒屋",
            "カフェ",
            "スイーツ",
            "郷土料理",
            "海鮮",
            "肉料理",
            "野菜",
            "ヴィーガン",
            "ベジタリアン",
        ]
        content_lower = content.lower() if content else ""
        for keyword in food_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]


class HotelSearchAgent(BaseSearchAgent):
    """宿泊先検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.HOTEL)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """宿泊先用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        constraints = query.constraints
        if constraints.get("accommodation_type"):
            keywords.append(constraints["accommodation_type"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果から宿泊POIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        return POISearchResult(
            name=title,
            category=POICategory.HOTEL,
            location="",
            description=content[:300] if content else "",
            price_range=self._extract_hotel_price(content),
            duration_minutes=None,
            opening_hours="",
            rating=None,
            tags=self._extract_hotel_tags(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_hotel_price(self, content: str) -> str:
        """宿泊料金を抽出"""
        if not content:
            return ""
        if "高級" in content or "ラグジュアリー" in content:
            return "¥30,000~/泊"
        if "リーズナブル" in content or "格安" in content:
            return "~¥10,000/泊"
        return ""

    def _extract_hotel_tags(self, content: str) -> list[str]:
        """宿泊関連のタグを抽出"""
        tags = []
        hotel_keywords = [
            "温泉",
            "露天風呂",
            "旅館",
            "ホテル",
            "民宿",
            "ゲストハウス",
            "オーシャンビュー",
            "山の景色",
            "朝食付き",
            "夕食付き",
            "素泊まり",
            "ペット可",
            "駐車場",
            "Wi-Fi",
        ]
        content_lower = content.lower() if content else ""
        for keyword in hotel_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]


# =============================================================================
# 並列検索ヘルパー
# =============================================================================


async def search_all_categories(
    destination: str,
    constraints: dict | None = None,
    keywords: dict[str, list[str]] | None = None,
) -> dict[POICategory, SearchResult]:
    """
    3カテゴリを並列で検索

    Args:
        destination: 目的地
        constraints: 制約条件
        keywords: カテゴリごとのキーワード

    Returns:
        カテゴリごとの検索結果
    """
    constraints = constraints or {}
    keywords = keywords or {}

    # クエリを構築
    activity_query = SearchQuery(
        category=POICategory.ACTIVITY,
        destination=destination,
        keywords=keywords.get("activity", []),
        constraints=constraints,
    )
    food_query = SearchQuery(
        category=POICategory.FOOD,
        destination=destination,
        keywords=keywords.get("food", []),
        constraints=constraints,
    )
    hotel_query = SearchQuery(
        category=POICategory.HOTEL,
        destination=destination,
        keywords=keywords.get("hotel", []),
        constraints=constraints,
    )

    # エージェントを作成
    activity_agent = ActivitySearchAgent()
    food_agent = FoodSearchAgent()
    hotel_agent = HotelSearchAgent()

    # 並列実行
    results = await asyncio.gather(
        activity_agent.search(activity_query),
        food_agent.search(food_query),
        hotel_agent.search(hotel_query),
        return_exceptions=True,
    )

    # 結果を整理
    output = {}
    agents = [
        (POICategory.ACTIVITY, results[0]),
        (POICategory.FOOD, results[1]),
        (POICategory.HOTEL, results[2]),
    ]

    for category, result in agents:
        if isinstance(result, Exception):
            logger.error(f"Search failed for {category}: {result}")
            output[category] = SearchResult(
                category=category,
                query=destination,
                items=[],
                source="tavily",
                search_time_ms=0,
            )
        else:
            output[category] = result

    return output


# Singleton instances
activity_search_agent = ActivitySearchAgent()
food_search_agent = FoodSearchAgent()
hotel_search_agent = HotelSearchAgent()
