"""
Search Agents Tests

CLAUDE.md セクション4.2, 8.7の要件:
- 検索エージェント4体（Activity, Food, Hotel, Transportation）の並列実行
- SearchReasoningLoop（推論→検索→検証の自律ループ）
- SearchEvaluatorAgent（横断評価）
- 1-2エージェント失敗時は残りの結果で続行
- 全エージェント失敗時はエラー報告
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from app.agents.search_agents import (
    ActivitySearchAgent,
    FoodSearchAgent,
    HotelSearchAgent,
    TransportationSearchAgent,
    SearchReasoningLoop,
    search_all_categories,
    search_with_reasoning,
    SearchStatus,
    SearchAllResult,
    _get_agent_for_category,
)
from app.schemas.travel_planning import (
    CrossCategoryEvaluation,
    InsufficientCategory,
    POICategory,
    POISearchResult,
    SearchQuery,
    SearchResult,
    SearchVerdict,
    TravelConstraints,
    TravelWishes,
)
from app.core.exceptions import SearchAllFailedError


# =============================================================================
# ActivitySearchAgent Tests
# =============================================================================

class TestActivitySearchAgent:
    """アクティビティ検索エージェントのテスト"""

    def test_init(self):
        """初期化のテスト"""
        agent = ActivitySearchAgent()
        assert agent.category == POICategory.ACTIVITY

    def test_build_keywords_empty(self):
        """キーワード構築（空の場合）"""
        agent = ActivitySearchAgent()
        query = SearchQuery(
            category=POICategory.ACTIVITY,
            destination="京都",
            keywords=[],
            constraints={},
        )
        keywords = agent._build_keywords(query)
        assert keywords == []

    def test_build_keywords_with_constraints(self):
        """キーワード構築（制約あり）"""
        agent = ActivitySearchAgent()
        query = SearchQuery(
            category=POICategory.ACTIVITY,
            destination="京都",
            keywords=["神社"],
            constraints={
                "activities": ["寺院巡り"],
                "experiences": ["文化体験"],
            },
        )
        keywords = agent._build_keywords(query)
        assert "神社" in keywords
        assert "寺院巡り" in keywords
        assert "文化体験" in keywords

    def test_extract_tags_from_content(self):
        """コンテンツからタグ抽出"""
        agent = ActivitySearchAgent()
        content = "京都の歴史ある神社で自然を感じながら文化体験ができます"
        tags = agent._extract_tags_from_content(content)
        assert "歴史" in tags
        assert "自然" in tags
        assert "文化" in tags
        assert "神社" in tags

    def test_extract_tags_max_5(self):
        """タグは最大5個"""
        agent = ActivitySearchAgent()
        content = "自然 文化 歴史 体験 アウトドア インドア 家族 カップル グループ"
        tags = agent._extract_tags_from_content(content)
        assert len(tags) <= 5

    def test_extract_poi_from_result_valid(self):
        """POI抽出（有効な結果）"""
        agent = ActivitySearchAgent()
        result = {
            "title": "金閣寺",
            "url": "https://example.com/kinkakuji",
            "content": "世界遺産の歴史ある寺院です",
            "score": 0.9,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.name == "金閣寺"
        assert poi.category == POICategory.ACTIVITY
        assert poi.source_url == "https://example.com/kinkakuji"
        assert poi.relevance_score == 0.9
        assert "歴史" in poi.tags

    def test_extract_poi_from_result_no_title(self):
        """POI抽出（タイトルなし）"""
        agent = ActivitySearchAgent()
        result = {"url": "https://example.com", "content": "test"}
        poi = agent._extract_poi_from_result(result)
        assert poi is None

    @pytest.mark.asyncio
    async def test_search_success(self):
        """検索成功"""
        agent = ActivitySearchAgent()
        query = SearchQuery(
            category=POICategory.ACTIVITY,
            destination="京都",
            keywords=["神社"],
            constraints={},
        )

        mock_results = {
            "results": [
                {
                    "title": "金閣寺",
                    "url": "https://example.com/kinkakuji",
                    "content": "歴史ある寺院",
                    "score": 0.9,
                },
                {
                    "title": "清水寺",
                    "url": "https://example.com/kiyomizu",
                    "content": "絶景の寺院",
                    "score": 0.85,
                },
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_results)
            result = await agent.search(query)

        assert result.category == POICategory.ACTIVITY
        assert len(result.items) == 2
        assert result.source == "tavily"
        assert result.search_time_ms >= 0

    @pytest.mark.asyncio
    async def test_search_failure(self):
        """検索失敗時は空のリストを返す"""
        agent = ActivitySearchAgent()
        query = SearchQuery(
            category=POICategory.ACTIVITY,
            destination="京都",
            keywords=[],
            constraints={},
        )

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(
                side_effect=Exception("API Error")
            )
            result = await agent.search(query)

        assert result.category == POICategory.ACTIVITY
        assert result.items == []


# =============================================================================
# FoodSearchAgent Tests
# =============================================================================

class TestFoodSearchAgent:
    """食検索エージェントのテスト"""

    def test_init(self):
        """初期化のテスト"""
        agent = FoodSearchAgent()
        assert agent.category == POICategory.FOOD

    def test_build_keywords_with_food_preferences(self):
        """キーワード構築（食の好みあり）"""
        agent = FoodSearchAgent()
        query = SearchQuery(
            category=POICategory.FOOD,
            destination="京都",
            keywords=["ランチ"],
            constraints={"food_preferences": ["和食", "抹茶"]},
        )
        keywords = agent._build_keywords(query)
        assert "ランチ" in keywords
        assert "和食" in keywords
        assert "抹茶" in keywords

    def test_extract_price_range_expensive(self):
        """価格帯抽出（高級）"""
        agent = FoodSearchAgent()
        content = "高級な京懐石料理を提供します"
        price = agent._extract_price_range(content)
        assert price == "¥10,000~"

    def test_extract_price_range_reasonable(self):
        """価格帯抽出（リーズナブル）"""
        agent = FoodSearchAgent()
        content = "リーズナブルな価格で京料理が楽しめます"
        price = agent._extract_price_range(content)
        assert price == "~¥2,000"

    def test_extract_price_range_unknown(self):
        """価格帯抽出（不明）"""
        agent = FoodSearchAgent()
        content = "美味しい料理を提供します"
        price = agent._extract_price_range(content)
        assert price == ""

    def test_extract_food_tags(self):
        """食関連タグ抽出"""
        agent = FoodSearchAgent()
        content = "本格的な和食と寿司、海鮮料理が楽しめるお店です"
        tags = agent._extract_food_tags(content)
        assert "和食" in tags
        assert "寿司" in tags
        assert "海鮮" in tags

    def test_extract_poi_food(self):
        """POI抽出（食）"""
        agent = FoodSearchAgent()
        result = {
            "title": "京都懐石 山本",
            "url": "https://example.com/yamamoto",
            "content": "高級な和食懐石料理店",
            "score": 0.88,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.name == "京都懐石 山本"
        assert poi.category == POICategory.FOOD
        assert poi.duration_minutes == 60  # デフォルト
        assert poi.price_range == "¥10,000~"


# =============================================================================
# HotelSearchAgent Tests
# =============================================================================

class TestHotelSearchAgent:
    """宿泊検索エージェントのテスト"""

    def test_init(self):
        """初期化のテスト"""
        agent = HotelSearchAgent()
        assert agent.category == POICategory.HOTEL

    def test_build_keywords_with_accommodation_type(self):
        """キーワード構築（宿泊タイプあり）"""
        agent = HotelSearchAgent()
        query = SearchQuery(
            category=POICategory.HOTEL,
            destination="京都",
            keywords=["温泉"],
            constraints={"accommodation_type": "旅館"},
        )
        keywords = agent._build_keywords(query)
        assert "温泉" in keywords
        assert "旅館" in keywords

    def test_extract_hotel_price_luxury(self):
        """宿泊料金抽出（高級）"""
        agent = HotelSearchAgent()
        content = "ラグジュアリーな客室で極上の滞在を"
        price = agent._extract_hotel_price(content)
        assert price == "¥30,000~/泊"

    def test_extract_hotel_price_budget(self):
        """宿泊料金抽出（格安）"""
        agent = HotelSearchAgent()
        content = "格安で泊まれるゲストハウス"
        price = agent._extract_hotel_price(content)
        assert price == "~¥10,000/泊"

    def test_extract_hotel_tags(self):
        """宿泊関連タグ抽出"""
        agent = HotelSearchAgent()
        content = "温泉付き旅館で露天風呂と朝食付きのプラン"
        tags = agent._extract_hotel_tags(content)
        assert "温泉" in tags
        assert "旅館" in tags
        assert "露天風呂" in tags
        assert "朝食付き" in tags


# =============================================================================
# TransportationSearchAgent Tests
# =============================================================================

class TestTransportationSearchAgent:
    """交通検索エージェントのテスト"""

    def test_init(self):
        """初期化のテスト"""
        agent = TransportationSearchAgent()
        assert agent.category == POICategory.TRANSPORTATION

    def test_build_keywords_empty(self):
        """キーワード構築（空の場合）"""
        agent = TransportationSearchAgent()
        query = SearchQuery(
            category=POICategory.TRANSPORTATION,
            destination="京都",
            keywords=[],
            constraints={},
        )
        keywords = agent._build_keywords(query)
        assert keywords == []

    def test_build_keywords_with_transportation_constraint(self):
        """キーワード構築（交通制約あり）"""
        agent = TransportationSearchAgent()
        query = SearchQuery(
            category=POICategory.TRANSPORTATION,
            destination="京都",
            keywords=["空港"],
            constraints={"transportation": "新幹線"},
        )
        keywords = agent._build_keywords(query)
        assert "空港" in keywords
        assert "新幹線" in keywords

    def test_extract_transport_tags(self):
        """交通タグ抽出"""
        agent = TransportationSearchAgent()
        content = "京都駅から電車とバスで移動。レンタカーも利用可能"
        tags = agent._extract_transport_tags(content)
        assert "電車" in tags
        assert "バス" in tags
        assert "レンタカー" in tags
        assert "駅" in tags

    def test_extract_transport_tags_max_5(self):
        """交通タグは最大5個"""
        agent = TransportationSearchAgent()
        content = "電車 バス タクシー レンタカー 新幹線 飛行機 フェリー 徒歩 自転車"
        tags = agent._extract_transport_tags(content)
        assert len(tags) <= 5

    def test_extract_transport_price_shinkansen(self):
        """交通料金抽出（新幹線）"""
        agent = TransportationSearchAgent()
        content = "東京から京都まで新幹線で約2時間"
        price = agent._extract_transport_price(content)
        assert price == "¥5,000~20,000"

    def test_extract_transport_price_rental(self):
        """交通料金抽出（レンタカー）"""
        agent = TransportationSearchAgent()
        content = "空港でレンタカーを借りて自由に移動"
        price = agent._extract_transport_price(content)
        assert price == "¥5,000~/日"

    def test_extract_transport_price_bus(self):
        """交通料金抽出（高速バス）"""
        agent = TransportationSearchAgent()
        content = "高速バスで格安に移動できます"
        price = agent._extract_transport_price(content)
        assert price == "¥2,000~5,000"

    def test_extract_transport_price_unknown(self):
        """交通料金抽出（不明）"""
        agent = TransportationSearchAgent()
        content = "便利な移動手段があります"
        price = agent._extract_transport_price(content)
        assert price == ""

    def test_extract_poi_transport(self):
        """POI抽出（交通）"""
        agent = TransportationSearchAgent()
        result = {
            "title": "京都駅から嵐山へのアクセス",
            "url": "https://example.com/access",
            "content": "電車とバスで便利にアクセスできます",
            "score": 0.75,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.name == "京都駅から嵐山へのアクセス"
        assert poi.category == POICategory.TRANSPORTATION
        assert poi.relevance_score == 0.75
        assert "電車" in poi.tags
        assert "バス" in poi.tags

    def test_extract_poi_no_title(self):
        """POI抽出（タイトルなし）"""
        agent = TransportationSearchAgent()
        result = {"url": "https://example.com", "content": "test"}
        poi = agent._extract_poi_from_result(result)
        assert poi is None

    @pytest.mark.asyncio
    async def test_search_success(self):
        """交通検索成功"""
        agent = TransportationSearchAgent()
        query = SearchQuery(
            category=POICategory.TRANSPORTATION,
            destination="京都",
            keywords=["アクセス"],
            constraints={},
        )

        mock_results = {
            "results": [
                {
                    "title": "京都アクセスガイド",
                    "url": "https://example.com/access",
                    "content": "新幹線で東京から約2時間。駅からバスで移動",
                    "score": 0.85,
                },
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_results)
            result = await agent.search(query)

        assert result.category == POICategory.TRANSPORTATION
        assert len(result.items) == 1
        assert result.source == "tavily"


# =============================================================================
# _get_agent_for_category Tests
# =============================================================================

class TestGetAgentForCategory:
    """カテゴリからエージェント取得のテスト"""

    def test_activity(self):
        agent = _get_agent_for_category(POICategory.ACTIVITY)
        assert isinstance(agent, ActivitySearchAgent)

    def test_food(self):
        agent = _get_agent_for_category(POICategory.FOOD)
        assert isinstance(agent, FoodSearchAgent)

    def test_hotel(self):
        agent = _get_agent_for_category(POICategory.HOTEL)
        assert isinstance(agent, HotelSearchAgent)

    def test_transportation(self):
        agent = _get_agent_for_category(POICategory.TRANSPORTATION)
        assert isinstance(agent, TransportationSearchAgent)


# =============================================================================
# SearchStatus Tests
# =============================================================================

class TestSearchStatus:
    """検索ステータスのテスト"""

    def test_success_rate_all_success(self):
        """成功率（全成功）"""
        status = SearchStatus(
            total_categories=4,
            successful_categories=["activity", "food", "hotel", "transportation"],
            failed_categories=[],
        )
        assert status.success_rate == 1.0

    def test_success_rate_partial_failure(self):
        """成功率（部分失敗）"""
        status = SearchStatus(
            total_categories=4,
            successful_categories=["activity", "food", "hotel"],
            failed_categories=["transportation"],
        )
        assert status.success_rate == pytest.approx(3 / 4)

    def test_success_rate_all_failed(self):
        """成功率（全失敗）"""
        status = SearchStatus(
            total_categories=4,
            successful_categories=[],
            failed_categories=["activity", "food", "hotel", "transportation"],
        )
        assert status.success_rate == 0.0

    def test_success_rate_zero_categories(self):
        """成功率（カテゴリ0）"""
        status = SearchStatus(total_categories=0)
        assert status.success_rate == 0.0

    def test_to_dict(self):
        """辞書変換"""
        status = SearchStatus(
            total_categories=4,
            successful_categories=["activity"],
            failed_categories=["food", "hotel", "transportation"],
            total_results=5,
            partial_failure=True,
            all_failed=False,
        )
        d = status.to_dict()
        assert d["total_categories"] == 4
        assert d["successful_categories"] == ["activity"]
        assert d["failed_categories"] == ["food", "hotel", "transportation"]
        assert d["partial_failure"] is True
        assert d["all_failed"] is False
        assert d["success_rate"] == pytest.approx(1 / 4)


# =============================================================================
# search_all_categories Tests (4カテゴリ)
# =============================================================================

class TestSearchAllCategories:
    """並列検索のテスト（4カテゴリ）"""

    @pytest.mark.asyncio
    async def test_all_success(self):
        """全エージェント成功"""
        mock_results = {
            "results": [
                {"title": "Test POI", "url": "https://example.com", "content": "test", "score": 0.8}
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_results)
            result = await search_all_categories("京都")

        assert isinstance(result, SearchAllResult)
        assert result.status.all_failed is False
        assert result.status.partial_failure is False
        assert len(result.status.successful_categories) == 4
        assert POICategory.ACTIVITY in result.results
        assert POICategory.FOOD in result.results
        assert POICategory.HOTEL in result.results
        assert POICategory.TRANSPORTATION in result.results

    @pytest.mark.asyncio
    async def test_partial_failure(self):
        """部分失敗（1-2エージェント）"""
        call_count = 0

        async def mock_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("API Error")
            return {"results": [{"title": "Test", "url": "https://example.com", "content": "test", "score": 0.8}]}

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = mock_search
            result = await search_all_categories("京都")

        assert result.status.all_failed is False
        assert len(result.status.successful_categories) == 4
        # One search returns empty items due to internal exception handling
        assert result.status.total_results == 3  # 3 out of 4 have items

    @pytest.mark.asyncio
    async def test_all_failed_no_exception(self):
        """全エージェントがエラーで空結果を返す"""
        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(
                side_effect=Exception("API Error")
            )
            result = await search_all_categories("京都", raise_on_all_failed=False)

        assert result.status.all_failed is False
        assert result.status.total_results == 0
        assert len(result.status.successful_categories) == 4

    @pytest.mark.asyncio
    async def test_with_constraints_and_keywords(self):
        """制約とキーワード付き検索"""
        mock_results = {"results": []}

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_results)
            result = await search_all_categories(
                destination="京都",
                constraints={
                    "activities": ["神社巡り"],
                    "food_preferences": ["和食"],
                    "accommodation_type": "旅館",
                    "transportation": "新幹線",
                },
                keywords={
                    "activity": ["観光"],
                    "food": ["ランチ"],
                    "hotel": ["温泉"],
                    "transportation": ["空港アクセス"],
                },
            )

        assert result.status.all_failed is False
        assert mock_client.search_for_travel.call_count == 4

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """並列実行の確認（4カテゴリ）"""
        execution_times = []

        async def mock_search(*args, **kwargs):
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(0.1)  # 100ms
            end = asyncio.get_event_loop().time()
            execution_times.append((start, end))
            return {"results": []}

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = mock_search

            start = asyncio.get_event_loop().time()
            await search_all_categories("京都")
            total_time = asyncio.get_event_loop().time() - start

        # 4つの検索が並列実行されているので、合計時間は400msより大幅に短いはず
        assert total_time < 0.3  # 余裕を持って300ms以内
        assert len(execution_times) == 4


# =============================================================================
# SearchReasoningLoop Tests
# =============================================================================

class TestSearchReasoningLoop:
    """推論→検索→検証ループのテスト"""

    def _make_constraints(self) -> TravelConstraints:
        return TravelConstraints(
            destination="京都",
            duration_days=3,
            num_people=2,
        )

    def _make_wishes(self) -> TravelWishes:
        return TravelWishes(
            activities=["神社巡り"],
            food_preferences=["和食"],
        )

    @pytest.mark.asyncio
    async def test_loop_sufficient_first_iteration(self):
        """1回目で十分と判定されるケース"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        # _reason: クエリ生成, _extract_pois_with_llm: POI抽出, _verify: 評価
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光 おすすめ"]},  # reason
            {"pois": [  # extract
                {"name": "金閣寺", "location": "北区", "description": "歴史ある寺院", "source_index": 0},
                {"name": "清水寺", "location": "東山区", "description": "絶景の寺院", "source_index": 1},
            ]},
            {"sufficient": True, "reason": "十分な結果", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "京都観光ランキングTOP10", "url": "https://example.com/1", "content": "歴史ある寺院", "score": 0.9},
                {"title": "清水寺の観光ガイド", "url": "https://example.com/2", "content": "絶景の寺院", "score": 0.85},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=2,
            )

        assert result.category == POICategory.ACTIVITY
        assert len(result.items) == 2
        assert result.items[0].name == "金閣寺"  # LLM抽出で実際の施設名
        assert result.items[1].name == "清水寺"
        assert result.source == "tavily+reasoning"
        # generate_json は3回呼ばれる（reason + extract + verify）
        assert mock_gateway.generate_json.call_count == 3

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self):
        """最大イテレーション到達"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        # iter 1: reason + extract + verify, iter 2: reason + extract (verify skipped on final)
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光"]},  # iter 1 reason
            {"pois": [{"name": "金閣寺", "location": "北区", "description": "test", "source_index": 0}]},  # iter 1 extract
            {"sufficient": False, "reason": "不足", "missing_aspects": ["自然系"], "suggested_queries": ["京都 自然"]},  # iter 1 verify
            {"queries": ["京都 自然 体験"]},  # iter 2 reason
            {"pois": [{"name": "嵐山竹林", "location": "右京区", "description": "test", "source_index": 0}]},  # iter 2 extract
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "Test POI", "url": "https://example.com/1", "content": "test", "score": 0.8},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=2,
            )

        assert result.category == POICategory.ACTIVITY
        # 2イテレーション分のアイテムが蓄積
        assert len(result.items) == 2  # 各イテレーションで1件
        # generate_json は5回（最終イテレーションのverifyがスキップされる）
        assert mock_gateway.generate_json.call_count == 5

    @pytest.mark.asyncio
    async def test_loop_with_hints(self):
        """Phase 2からのヒント付きループ"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 空港 アクセス"]},  # reason with hints
            {"pois": [{"name": "関西空港はるか", "location": "京都駅", "description": "電車で移動", "source_index": 0}]},  # extract
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "関西空港アクセスガイド", "url": "https://example.com/1", "content": "電車で移動", "score": 0.8},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.TRANSPORTATION,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="okamototk/llama-swallow:8b",
                hints=["空港からのアクセス情報が必要"],
                max_iterations=2,
            )

        assert result.category == POICategory.TRANSPORTATION
        assert len(result.items) == 1
        assert result.items[0].name == "関西空港はるか"

    @pytest.mark.asyncio
    async def test_loop_reason_failure_fallback(self):
        """推論ステップ失敗時のフォールバック"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        # reason が例外を投げる
        mock_gateway.generate_json = AsyncMock(side_effect=[
            Exception("LLM Error"),
        ])
        loop._gateway = mock_gateway

        # reasonが失敗してもフォールバッククエリで検索は実行されるが、
        # ループ全体がexceptブロックでbreakする
        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value={"results": []})
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=2,
            )

        # エラーでもSearchResultは返される
        assert result.category == POICategory.ACTIVITY
        assert result.items == []

    @pytest.mark.asyncio
    async def test_loop_search_failure(self):
        """検索失敗時でも結果は返される"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        # Tavily検索が失敗するのでextractは呼ばれない → reason + verify の2回
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光"]},  # reason
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(
                side_effect=Exception("Tavily Error")
            )
            result = await loop.execute(
                category=POICategory.FOOD,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="okamototk/llama-swallow:8b",
                max_iterations=2,
            )

        assert result.category == POICategory.FOOD
        assert result.items == []


# =============================================================================
# SearchReasoningLoop LLM Extraction Tests
# =============================================================================

class TestSearchReasoningLoopLLMExtraction:
    """LLMベースPOI抽出のテスト"""

    def _make_constraints(self) -> TravelConstraints:
        return TravelConstraints(
            destination="京都",
            duration_days=2,
            num_people=2,
        )

    def _make_wishes(self) -> TravelWishes:
        return TravelWishes(
            activities=["神社巡り"],
            food_preferences=["和食"],
        )

    @pytest.mark.asyncio
    async def test_llm_extraction_extracts_real_names(self):
        """LLM抽出で記事タイトルではなく実際の施設名が抽出される"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光"]},  # reason
            {"pois": [  # extract - 実際の施設名を返す
                {"name": "金閣寺", "location": "北区", "description": "世界遺産の寺院", "source_index": 0},
                {"name": "銀閣寺", "location": "左京区", "description": "東山文化の象徴", "source_index": 0},
                {"name": "清水寺", "location": "東山区", "description": "絶景の舞台", "source_index": 1},
            ]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "京都のおすすめ観光スポットランキングTOP30", "url": "https://example.com/ranking", "content": "金閣寺や銀閣寺が人気", "score": 0.9},
                {"title": "清水寺の見どころ完全ガイド2025", "url": "https://example.com/kiyomizu", "content": "清水の舞台からの絶景", "score": 0.85},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=1,
            )

        # 記事タイトルではなく実際の施設名が抽出される
        names = [item.name for item in result.items]
        assert "金閣寺" in names
        assert "銀閣寺" in names
        assert "清水寺" in names
        # 記事タイトルは含まれない
        assert "京都のおすすめ観光スポットランキングTOP30" not in names

        # source_urlが元のTavily結果から引き継がれる
        kinkakuji = next(item for item in result.items if item.name == "金閣寺")
        assert kinkakuji.source_url == "https://example.com/ranking"
        assert kinkakuji.source_name == "tavily+llm"

    @pytest.mark.asyncio
    async def test_llm_extraction_filters_by_destination(self):
        """LLM抽出が目的地外の場所を除外する"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光"]},  # reason
            {"pois": [  # extract - 京都のPOIのみ返す（沖縄は除外される）
                {"name": "金閣寺", "location": "北区", "description": "世界遺産", "source_index": 0},
            ]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "全国の観光地ランキング", "url": "https://example.com/1", "content": "金閣寺（京都）、美ら海水族館（沖縄）", "score": 0.9},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=1,
            )

        # 京都のPOIのみ
        assert len(result.items) == 1
        assert result.items[0].name == "金閣寺"

    @pytest.mark.asyncio
    async def test_llm_extraction_fallback_on_failure(self):
        """LLM抽出失敗時は従来のルールベース抽出にフォールバック"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        extract_call_count = 0

        async def mock_generate_json(**kwargs):
            nonlocal extract_call_count
            prompt = kwargs.get("prompt", "")
            agent_name = kwargs.get("agent_name", "")

            if agent_name == "search_reasoner":
                return {"queries": ["京都 観光"]}
            elif agent_name == "search_poi_extractor":
                extract_call_count += 1
                raise Exception("LLM抽出エラー")
            elif agent_name == "search_verifier":
                return {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []}
            return {}

        mock_gateway.generate_json = AsyncMock(side_effect=mock_generate_json)
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "金閣寺ガイド", "url": "https://example.com/1", "content": "歴史ある寺院", "score": 0.9},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=1,
            )

        # フォールバックでルールベース抽出が使われる
        assert len(result.items) == 1
        assert result.items[0].name == "金閣寺ガイド"  # タイトルがそのまま使われる
        assert extract_call_count == 1

    @pytest.mark.asyncio
    async def test_llm_extraction_empty_pois_fallback(self):
        """LLM抽出で空のPOIリストが返された場合はフォールバック"""
        loop = SearchReasoningLoop()

        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 観光"]},  # reason
            {"pois": []},  # extract - 空のPOIリスト
            # フォールバック後にverifyが呼ばれる
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])
        loop._gateway = mock_gateway

        mock_tavily_results = {
            "results": [
                {"title": "金閣寺ガイド", "url": "https://example.com/1", "content": "歴史ある寺院", "score": 0.9},
            ]
        }

        with patch("app.agents.search_agents.tavily_client") as mock_client:
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)
            result = await loop.execute(
                category=POICategory.ACTIVITY,
                destination="京都",
                constraints=self._make_constraints(),
                wishes=self._make_wishes(),
                worker_host="localhost:11434",
                model="qwen2.5:32b-instruct",
                max_iterations=1,
            )

        # フォールバックでルールベース抽出
        assert len(result.items) == 1
        assert result.items[0].name == "金閣寺ガイド"


# =============================================================================
# SearchEvaluatorAgent Tests
# =============================================================================

class TestSearchEvaluatorAgent:
    """横断評価エージェントのテスト"""

    def _make_search_results(self) -> dict:
        """テスト用の検索結果を作成"""
        return {
            POICategory.ACTIVITY: SearchResult(
                category=POICategory.ACTIVITY,
                query="京都 観光",
                items=[
                    POISearchResult(
                        name="金閣寺", category=POICategory.ACTIVITY,
                        relevance_score=0.9, source_name="tavily",
                    ),
                    POISearchResult(
                        name="清水寺", category=POICategory.ACTIVITY,
                        relevance_score=0.85, source_name="tavily",
                    ),
                ],
            ),
            POICategory.FOOD: SearchResult(
                category=POICategory.FOOD,
                query="京都 グルメ",
                items=[
                    POISearchResult(
                        name="京懐石", category=POICategory.FOOD,
                        relevance_score=0.8, source_name="tavily",
                    ),
                ],
            ),
            POICategory.HOTEL: SearchResult(
                category=POICategory.HOTEL,
                query="京都 宿泊",
                items=[],  # 空（不足）
            ),
            POICategory.TRANSPORTATION: SearchResult(
                category=POICategory.TRANSPORTATION,
                query="京都 交通",
                items=[
                    POISearchResult(
                        name="京都駅バス案内", category=POICategory.TRANSPORTATION,
                        relevance_score=0.7, source_name="tavily",
                    ),
                ],
            ),
        }

    @pytest.mark.asyncio
    async def test_evaluate_all_sufficient(self):
        """全カテゴリ十分"""
        from app.agents.search_evaluator import SearchEvaluatorAgent

        agent = SearchEvaluatorAgent()
        mock_result = {
            "sufficient_categories": ["activity", "food", "hotel", "transportation"],
            "insufficient_categories": [],
        }

        with patch("app.agents.search_evaluator.llm_gateway") as mock_gw:
            mock_gw.generate_json = AsyncMock(return_value=mock_result)
            evaluation = await agent.evaluate(
                search_results=self._make_search_results(),
                constraints=TravelConstraints(destination="京都", duration_days=2),
                wishes=TravelWishes(),
            )

        assert len(evaluation.sufficient_categories) == 4
        assert not evaluation.has_insufficient

    @pytest.mark.asyncio
    async def test_evaluate_with_insufficient(self):
        """一部カテゴリ不足"""
        from app.agents.search_evaluator import SearchEvaluatorAgent

        agent = SearchEvaluatorAgent()
        mock_result = {
            "sufficient_categories": ["activity", "food"],
            "insufficient_categories": [
                {"category": "hotel", "reason": "候補が0件", "hints": ["温泉旅館を追加で検索"]},
                {"category": "transportation", "reason": "空港アクセスが不足", "hints": ["関西空港からのアクセス"]},
            ],
        }

        with patch("app.agents.search_evaluator.llm_gateway") as mock_gw:
            mock_gw.generate_json = AsyncMock(return_value=mock_result)
            evaluation = await agent.evaluate(
                search_results=self._make_search_results(),
                constraints=TravelConstraints(destination="京都", duration_days=2),
                wishes=TravelWishes(),
            )

        assert len(evaluation.sufficient_categories) == 2
        assert evaluation.has_insufficient
        assert len(evaluation.insufficient_categories) == 2
        assert evaluation.insufficient_categories[0].category == "hotel"
        assert "温泉旅館を追加で検索" in evaluation.insufficient_categories[0].hints

    @pytest.mark.asyncio
    async def test_evaluate_llm_failure(self):
        """LLM失敗時は全て十分として続行"""
        from app.agents.search_evaluator import SearchEvaluatorAgent

        agent = SearchEvaluatorAgent()

        with patch("app.agents.search_evaluator.llm_gateway") as mock_gw:
            mock_gw.generate_json = AsyncMock(side_effect=Exception("LLM Error"))
            evaluation = await agent.evaluate(
                search_results=self._make_search_results(),
                constraints=TravelConstraints(destination="京都", duration_days=2),
                wishes=TravelWishes(),
            )

        # エラー時は全カテゴリ十分として続行
        assert len(evaluation.sufficient_categories) == 4
        assert not evaluation.has_insufficient


# =============================================================================
# search_with_reasoning Tests
# =============================================================================

class TestSearchWithReasoning:
    """推論ループ付き並列検索のテスト"""

    @pytest.mark.asyncio
    async def test_all_categories_parallel(self):
        """4カテゴリ並列実行"""
        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            # 各カテゴリでreason + extract + verifyの3コール × 4カテゴリ = 12コール
            {"queries": ["query1"]},
            {"pois": [{"name": "POI1", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
            {"queries": ["query2"]},
            {"pois": [{"name": "POI2", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
            {"queries": ["query3"]},
            {"pois": [{"name": "POI3", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
            {"queries": ["query4"]},
            {"pois": [{"name": "POI4", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
        ])

        mock_tavily_results = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "test", "score": 0.8}
            ]
        }

        with (
            patch("app.agents.search_agents.tavily_client") as mock_client,
            patch("app.agents.search_agents._load_search_routing", return_value={}),
        ):
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)

            # SearchReasoningLoopのgatewayをモック
            with patch.object(SearchReasoningLoop, "_get_gateway", return_value=mock_gateway):
                result = await search_with_reasoning(
                    destination="京都",
                    constraints=TravelConstraints(destination="京都", duration_days=2),
                    wishes=TravelWishes(),
                    max_iterations=1,
                )

        assert isinstance(result, SearchAllResult)
        assert len(result.status.successful_categories) == 4
        assert POICategory.TRANSPORTATION in result.results

    @pytest.mark.asyncio
    async def test_specific_categories_only(self):
        """特定カテゴリのみ検索"""
        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["query1"]},
            {"pois": [{"name": "POI1", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
            {"queries": ["query2"]},
            {"pois": [{"name": "POI2", "location": "", "description": "test", "source_index": 0}]},
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},
        ])

        mock_tavily_results = {"results": []}

        with (
            patch("app.agents.search_agents.tavily_client") as mock_client,
            patch("app.agents.search_agents._load_search_routing", return_value={}),
        ):
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)

            with patch.object(SearchReasoningLoop, "_get_gateway", return_value=mock_gateway):
                result = await search_with_reasoning(
                    destination="京都",
                    constraints=TravelConstraints(destination="京都"),
                    wishes=TravelWishes(),
                    categories=[POICategory.HOTEL, POICategory.TRANSPORTATION],
                    max_iterations=1,
                )

        assert result.status.total_categories == 2
        assert POICategory.HOTEL in result.results
        assert POICategory.TRANSPORTATION in result.results
        assert POICategory.ACTIVITY not in result.results

    @pytest.mark.asyncio
    async def test_with_hints(self):
        """ヒント付き再検索"""
        mock_gateway = MagicMock()
        mock_gateway.generate_json = AsyncMock(side_effect=[
            {"queries": ["京都 空港 アクセス"]},  # reason
            {"pois": [{"name": "関西空港はるか", "location": "京都駅", "description": "電車", "source_index": 0}]},  # extract
            {"sufficient": True, "reason": "OK", "missing_aspects": [], "suggested_queries": []},  # verify
        ])

        mock_tavily_results = {"results": [
            {"title": "空港アクセスガイド", "url": "https://example.com", "content": "電車", "score": 0.8}
        ]}

        with (
            patch("app.agents.search_agents.tavily_client") as mock_client,
            patch("app.agents.search_agents._load_search_routing", return_value={}),
        ):
            mock_client.search_for_travel = AsyncMock(return_value=mock_tavily_results)

            with patch.object(SearchReasoningLoop, "_get_gateway", return_value=mock_gateway):
                result = await search_with_reasoning(
                    destination="京都",
                    constraints=TravelConstraints(destination="京都"),
                    wishes=TravelWishes(),
                    categories=[POICategory.TRANSPORTATION],
                    hints_per_category={"transportation": ["空港アクセス情報が必要"]},
                    max_iterations=1,
                )

        assert POICategory.TRANSPORTATION in result.results
        assert len(result.results[POICategory.TRANSPORTATION].items) == 1


# =============================================================================
# Schema Tests
# =============================================================================

class TestNewSchemas:
    """新しいスキーマのテスト"""

    def test_poi_category_transportation(self):
        """POICategory.TRANSPORTATION"""
        assert POICategory.TRANSPORTATION.value == "transportation"

    def test_search_verdict_default(self):
        """SearchVerdict デフォルト値"""
        verdict = SearchVerdict()
        assert verdict.sufficient is False
        assert verdict.reason == ""
        assert verdict.missing_aspects == []
        assert verdict.suggested_queries == []

    def test_search_verdict_sufficient(self):
        """SearchVerdict 十分"""
        verdict = SearchVerdict(
            sufficient=True,
            reason="十分な結果が得られました",
        )
        assert verdict.sufficient is True

    def test_cross_category_evaluation_empty(self):
        """CrossCategoryEvaluation 空"""
        eval_ = CrossCategoryEvaluation()
        assert not eval_.has_insufficient
        assert eval_.sufficient_categories == []

    def test_cross_category_evaluation_with_insufficient(self):
        """CrossCategoryEvaluation 不足あり"""
        eval_ = CrossCategoryEvaluation(
            sufficient_categories=["activity", "food"],
            insufficient_categories=[
                InsufficientCategory(
                    category="hotel",
                    reason="候補不足",
                    hints=["温泉旅館で再検索"],
                )
            ],
        )
        assert eval_.has_insufficient
        assert len(eval_.insufficient_categories) == 1
        assert eval_.insufficient_categories[0].category == "hotel"

    def test_planner_input_transportation(self):
        """PlannerInput に transportation フィールドがある"""
        from app.schemas.travel_planning import PlannerInput
        input_ = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            transportation=[],
        )
        assert input_.transportation == []


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """エッジケースのテスト"""

    def test_empty_content_tag_extraction(self):
        """空コンテンツからのタグ抽出"""
        agent = ActivitySearchAgent()
        tags = agent._extract_tags_from_content("")
        assert tags == []

    def test_none_content_handling(self):
        """Noneコンテンツの処理"""
        agent = ActivitySearchAgent()
        result = {
            "title": "Test",
            "url": "https://example.com",
            "content": None,
            "score": 0.5,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.description == ""
        assert poi.tags == []

    def test_long_content_truncation(self):
        """長いコンテンツの切り詰め"""
        agent = ActivitySearchAgent()
        long_content = "A" * 500
        result = {
            "title": "Test",
            "url": "https://example.com",
            "content": long_content,
            "score": 0.5,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert len(poi.description) == 300

    def test_missing_score(self):
        """スコアなしの場合"""
        agent = ActivitySearchAgent()
        result = {
            "title": "Test",
            "url": "https://example.com",
            "content": "test",
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.relevance_score == 0.5  # デフォルト

    def test_transportation_empty_content(self):
        """交通エージェント: 空コンテンツ"""
        agent = TransportationSearchAgent()
        tags = agent._extract_transport_tags("")
        assert tags == []

    def test_transportation_none_content(self):
        """交通エージェント: Noneコンテンツ"""
        agent = TransportationSearchAgent()
        result = {
            "title": "Test",
            "url": "https://example.com",
            "content": None,
            "score": 0.5,
        }
        poi = agent._extract_poi_from_result(result)
        assert poi is not None
        assert poi.description == ""
        assert poi.tags == []
