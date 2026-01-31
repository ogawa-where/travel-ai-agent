"""
Planner/Explainer Agent Tests

CLAUDE.md セクション4.2の要件:
- Planner/Optimizer Agent：制約+スコアリングで旅程生成
- Explainer Agent：嗜好と体験軸に基づく根拠説明生成
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

from app.agents.planner import PlannerAgent, planner_agent
from app.agents.explainer import ExplainerAgent, explainer_agent
from app.schemas.travel_planning import (
    DayPlan,
    ExplainerInput,
    Itinerary,
    ItineraryItem,
    PlannerInput,
    POIBase,
    POIRanked,
    TravelConstraints,
    TravelWishes,
)


# =============================================================================
# PlannerAgent - Prompt Building Tests
# =============================================================================

class TestPlannerPromptBuilding:
    """プランナーのプロンプト構築テスト"""

    def test_build_prompt_basic(self):
        """基本的なプロンプト構築"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(
                destination="京都",
                duration_days=2,
                budget_total=50000,
                num_people=2,
            ),
            wishes=TravelWishes(
                activities=["神社巡り"],
                food_preferences=["和食"],
            ),
            activities=[],
            foods=[],
            hotels=[],
        )
        prompt = agent._build_prompt(input_data)

        assert "京都" in prompt
        assert "2日間" in prompt
        assert "50,000円" in prompt
        assert "2人" in prompt
        assert "神社巡り" in prompt
        assert "和食" in prompt

    def test_build_prompt_with_profile(self):
        """プロフィール付きプロンプト"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
            user_profile_summary="温泉好きな40代男性",
        )
        prompt = agent._build_prompt(input_data)
        assert "ユーザープロフィール" in prompt
        assert "温泉好きな40代男性" in prompt

    def test_build_prompt_with_pois(self):
        """POI付きプロンプト"""
        agent = PlannerAgent()
        activity_poi = POIRanked(
            name="金閣寺",
            category="activity",
            description="世界遺産の寺院",
            price_range="¥400",
            match_reasons=["文化体験にマッチ"],
            relevance_score=0.9,
            preference_score=0.85,
            final_score=0.87,
        )
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[activity_poi],
            foods=[],
            hotels=[],
        )
        prompt = agent._build_prompt(input_data)
        assert "金閣寺" in prompt
        assert "世界遺産の寺院" in prompt
        assert "¥400" in prompt
        assert "文化体験にマッチ" in prompt


class TestPlannerTransportationPOI:
    """交通POIプロンプトのテスト"""

    def test_build_prompt_with_transportation_pois(self):
        """交通POI付きプロンプト"""
        agent = PlannerAgent()
        transport_poi = POIRanked(
            name="京都駅バスターミナル",
            category="transportation",
            description="市内バスの拠点",
            match_reasons=["移動拠点"],
            relevance_score=0.8,
            preference_score=0.7,
            final_score=0.75,
        )
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
            transportation=[transport_poi],
        )
        prompt = agent._build_prompt(input_data)
        assert "交通・アクセス" in prompt
        assert "京都駅バスターミナル" in prompt
        assert "市内バスの拠点" in prompt

    def test_build_prompt_empty_transportation(self):
        """交通POIなしのプロンプト"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
            transportation=[],
        )
        prompt = agent._build_prompt(input_data)
        assert "交通・アクセス" in prompt
        assert "候補なし" in prompt


class TestPlannerDurationScore:
    """日数一致スコアのテスト"""

    def test_duration_match_score_match(self):
        """日数一致時のスコア"""
        agent = PlannerAgent()
        itinerary = Itinerary(
            title="Test", summary="",
            days=[
                DayPlan(day_number=1, items=[]),
                DayPlan(day_number=2, items=[]),
            ],
        )
        constraints = TravelConstraints(destination="京都", duration_days=2)
        wishes = TravelWishes()
        _, breakdown = agent._calculate_score(itinerary, constraints, wishes)
        assert breakdown["duration_match"] == 1.0

    def test_duration_match_score_mismatch(self):
        """日数不一致時のスコア"""
        agent = PlannerAgent()
        itinerary = Itinerary(
            title="Test", summary="",
            days=[
                DayPlan(day_number=1, items=[]),
                DayPlan(day_number=2, items=[]),
                DayPlan(day_number=3, items=[]),
            ],
        )
        constraints = TravelConstraints(destination="京都", duration_days=2)
        wishes = TravelWishes()
        _, breakdown = agent._calculate_score(itinerary, constraints, wishes)
        assert breakdown["duration_match"] == 0.0

    def test_duration_match_score_no_constraint(self):
        """日数制約なし時のスコア"""
        agent = PlannerAgent()
        itinerary = Itinerary(
            title="Test", summary="",
            days=[DayPlan(day_number=1, items=[])],
        )
        constraints = TravelConstraints(destination="京都")
        wishes = TravelWishes()
        _, breakdown = agent._calculate_score(itinerary, constraints, wishes)
        assert breakdown["duration_match"] == 1.0


class TestPlannerFormatPOIList:
    """POIリストのフォーマットテスト"""

    def test_format_empty_list(self):
        """空リスト"""
        agent = PlannerAgent()
        result = agent._format_poi_list([])
        assert result == "候補なし"

    def test_format_single_poi(self):
        """単一POI"""
        agent = PlannerAgent()
        poi = POIRanked(
            name="金閣寺",
            category="activity",
            description="世界遺産の寺院",
            relevance_score=0.9,
            preference_score=0.85,
            final_score=0.87,
        )
        result = agent._format_poi_list([poi])
        assert "1. 金閣寺" in result
        assert "世界遺産の寺院" in result

    def test_format_max_10_pois(self):
        """最大10件"""
        agent = PlannerAgent()
        pois = [
            POIRanked(
                name=f"POI{i}",
                category="activity",
                relevance_score=0.5,
                preference_score=0.5,
                final_score=0.5,
            )
            for i in range(15)
        ]
        result = agent._format_poi_list(pois)
        assert "POI0" in result
        assert "POI9" in result
        assert "POI10" not in result  # 11番目以降は含まれない


# =============================================================================
# PlannerAgent - Response Parsing Tests
# =============================================================================

class TestPlannerResponseParsing:
    """レスポンスパースのテスト"""

    def test_parse_valid_json(self):
        """有効なJSON"""
        agent = PlannerAgent()
        response = json.dumps({
            "title": "京都の旅",
            "summary": "文化体験の旅",
            "days": [],
            "highlights": ["金閣寺"],
        })
        parsed = agent._parse_response(response)
        assert parsed["title"] == "京都の旅"
        assert parsed["highlights"] == ["金閣寺"]

    def test_parse_json_in_code_block(self):
        """コードブロック内のJSON"""
        agent = PlannerAgent()
        response = """```json
{
  "title": "京都の旅",
  "summary": "文化体験の旅",
  "days": [],
  "highlights": []
}
```"""
        parsed = agent._parse_response(response)
        assert parsed["title"] == "京都の旅"

    def test_parse_invalid_json(self):
        """無効なJSON → LLMParseErrorを発生"""
        from app.core.exceptions import LLMParseError

        agent = PlannerAgent()
        response = "This is not valid JSON"
        with pytest.raises(LLMParseError):
            agent._parse_response(response)


# =============================================================================
# PlannerAgent - Itinerary Conversion Tests
# =============================================================================

class TestPlannerItineraryConversion:
    """旅程変換のテスト"""

    def test_convert_empty_itinerary(self):
        """空の旅程"""
        agent = PlannerAgent()
        parsed = {"days": []}
        itinerary = agent._convert_to_itinerary(parsed)
        assert itinerary.days == []

    def test_convert_full_itinerary(self):
        """完全な旅程"""
        agent = PlannerAgent()
        parsed = {
            "title": "京都2泊3日",
            "summary": "文化体験の旅",
            "days": [
                {
                    "day_number": 1,
                    "date": "2025-03-01",
                    "theme": "寺社巡り",
                    "items": [
                        {
                            "time_start": "09:00",
                            "time_end": "11:00",
                            "poi": {
                                "name": "金閣寺",
                                "category": "activity",
                                "location": "京都市北区",
                                "description": "世界遺産",
                                "tags": ["寺院"],
                            },
                            "notes": "朝一番がおすすめ",
                            "travel_from_previous": "バス30分",
                        }
                    ],
                    "accommodation": {
                        "name": "京都旅館",
                        "category": "hotel",
                        "location": "京都市中京区",
                    },
                }
            ],
            "total_budget_estimate": 50000,
            "highlights": ["金閣寺"],
        }
        itinerary = agent._convert_to_itinerary(parsed)

        assert itinerary.title == "京都2泊3日"
        assert itinerary.summary == "文化体験の旅"
        assert len(itinerary.days) == 1
        assert itinerary.days[0].day_number == 1
        assert itinerary.days[0].theme == "寺社巡り"
        assert len(itinerary.days[0].items) == 1
        assert itinerary.days[0].items[0].poi.name == "金閣寺"
        assert itinerary.days[0].accommodation.name == "京都旅館"
        assert itinerary.total_budget_estimate == 50000


# =============================================================================
# PlannerAgent - Score Calculation Tests
# =============================================================================

class TestPlannerScoreCalculation:
    """スコア計算のテスト"""

    def test_score_empty_itinerary(self):
        """空の旅程のスコア"""
        agent = PlannerAgent()
        itinerary = Itinerary(title="", summary="", days=[])
        constraints = TravelConstraints(destination="京都")
        wishes = TravelWishes()

        score, breakdown = agent._calculate_score(itinerary, constraints, wishes)

        # 空の旅程でも budget, duration_match は1.0（制約なし）
        # weights: completeness=0.25, accommodation=0.2, meals=0.2, budget=0.15, duration_match=0.2
        # score = 0*0.25 + 0*0.2 + 0*0.2 + 1.0*0.15 + 1.0*0.2 = 0.35
        assert breakdown["completeness"] == 0.0
        assert breakdown["accommodation"] == 0.0
        assert breakdown["meals"] == 0.0
        assert breakdown["budget"] == 1.0  # 予算制約なしで1.0
        assert breakdown["duration_match"] == 1.0  # 日数制約なしで1.0
        assert score == pytest.approx(0.35)

    def test_score_perfect_itinerary(self):
        """完璧な旅程のスコア"""
        agent = PlannerAgent()

        # 1日に4つのアクティビティと1つの食事と宿泊
        items = []
        for i in range(4):
            items.append(
                ItineraryItem(
                    time_start=f"{9+i*2}:00",
                    time_end=f"{11+i*2}:00",
                    poi=POIBase(name=f"Activity{i}", category="activity"),
                )
            )
        # 食事3回
        for i in range(3):
            items.append(
                ItineraryItem(
                    time_start=f"{8+i*4}:00",
                    time_end=f"{9+i*4}:00",
                    poi=POIBase(name=f"Food{i}", category="food"),
                )
            )

        day = DayPlan(
            day_number=1,
            items=items,
            accommodation=POIBase(name="Hotel", category="hotel"),
        )
        itinerary = Itinerary(
            title="Test",
            summary="Test",
            days=[day],
            total_budget_estimate=50000,
        )
        constraints = TravelConstraints(
            destination="京都",
            duration_days=1,
            budget_total=60000,
        )
        wishes = TravelWishes()

        score, breakdown = agent._calculate_score(itinerary, constraints, wishes)

        assert breakdown["completeness"] == 1.0
        assert breakdown["accommodation"] == 1.0
        assert breakdown["meals"] == 1.0
        assert breakdown["budget"] == 1.0
        assert breakdown["duration_match"] == 1.0
        assert score == pytest.approx(1.0)

    def test_score_over_budget(self):
        """予算オーバーのスコア"""
        agent = PlannerAgent()
        itinerary = Itinerary(
            title="Test",
            summary="Test",
            days=[],
            total_budget_estimate=100000,
        )
        constraints = TravelConstraints(
            destination="京都",
            budget_total=50000,  # 予算の2倍
        )
        wishes = TravelWishes()

        score, breakdown = agent._calculate_score(itinerary, constraints, wishes)

        assert breakdown["budget"] == 0.0  # 2倍以上で0


# =============================================================================
# PlannerAgent - LLM Integration Tests
# =============================================================================

class TestPlannerLLMIntegration:
    """LLM統合テスト"""

    @pytest.mark.asyncio
    async def test_plan_success(self):
        """プラン生成成功"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(
                destination="京都",
                duration_days=2,
            ),
            wishes=TravelWishes(activities=["神社巡り"]),
            activities=[],
            foods=[],
            hotels=[],
        )

        mock_response = json.dumps({
            "title": "京都の旅",
            "summary": "神社を巡る旅",
            "days": [
                {
                    "day_number": 1,
                    "theme": "神社巡り",
                    "items": [
                        {
                            "time_start": "09:00",
                            "time_end": "11:00",
                            "poi": {"name": "金閣寺", "category": "activity"},
                        }
                    ],
                },
                {
                    "day_number": 2,
                    "theme": "文化体験",
                    "items": [
                        {
                            "time_start": "09:00",
                            "time_end": "11:00",
                            "poi": {"name": "清水寺", "category": "activity"},
                        }
                    ],
                },
            ],
            "highlights": ["金閣寺", "清水寺"],
        })

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            output = await agent.plan(input_data)

        assert output.itinerary.title == "京都の旅"
        assert 0.0 <= output.score <= 1.0
        assert "completeness" in output.score_breakdown

    @pytest.mark.asyncio
    async def test_plan_retry_on_llm_failure(self):
        """LLM呼び出し失敗時のリトライ"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API Error")
            return json.dumps({
                "title": "Test",
                "days": [{"day_number": 1, "theme": "観光", "items": []}],
            })

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = mock_generate
            output = await agent.plan(input_data)

        assert call_count == 3
        assert output.itinerary.title == "Test"
        assert len(output.itinerary.days) == 1

    @pytest.mark.asyncio
    async def test_plan_retry_on_parse_failure(self):
        """JSONパース失敗時のリトライ"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return "This is not valid JSON"
            return json.dumps({
                "title": "Retry Success",
                "days": [{"day_number": 1, "theme": "観光", "items": []}],
            })

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = mock_generate
            output = await agent.plan(input_data)

        assert call_count == 2
        assert output.itinerary.title == "Retry Success"

    @pytest.mark.asyncio
    async def test_plan_retry_on_empty_days(self):
        """空のdays配列時のリトライ"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return json.dumps({"title": "Empty", "days": []})
            return json.dumps({
                "title": "Non-empty",
                "days": [{"day_number": 1, "theme": "観光", "items": []}],
            })

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = mock_generate
            output = await agent.plan(input_data)

        assert call_count == 2
        assert output.itinerary.title == "Non-empty"
        assert len(output.itinerary.days) == 1

    @pytest.mark.asyncio
    async def test_plan_retry_on_duration_mismatch(self):
        """日数不一致時のリトライ"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(
                destination="京都",
                duration_days=2,
            ),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # 1回目: 3日分を返す（2日のはずなのに）
                return json.dumps({
                    "title": "京都3日間",
                    "days": [
                        {"day_number": 1, "theme": "観光", "items": []},
                        {"day_number": 2, "theme": "文化", "items": []},
                        {"day_number": 3, "theme": "自然", "items": []},
                    ],
                })
            # 2回目: 正しく2日分
            return json.dumps({
                "title": "京都2日間",
                "days": [
                    {"day_number": 1, "theme": "観光", "items": []},
                    {"day_number": 2, "theme": "文化", "items": []},
                ],
            })

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = mock_generate
            output = await agent.plan(input_data)

        assert call_count == 2
        assert len(output.itinerary.days) == 2

    @pytest.mark.asyncio
    async def test_plan_max_retries_exceeded(self):
        """最大リトライ回数超過"""
        from app.core.exceptions import LLMParseError

        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )

        with patch("app.agents.planner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(LLMParseError) as exc_info:
                await agent.plan(input_data)

        assert "3 attempts" in str(exc_info.value)


# =============================================================================
# ExplainerAgent - Prompt Building Tests
# =============================================================================

class TestExplainerPromptBuilding:
    """説明エージェントのプロンプト構築テスト"""

    def test_build_prompt_basic(self):
        """基本的なプロンプト構築"""
        agent = ExplainerAgent()
        itinerary = Itinerary(
            title="京都の旅",
            summary="文化体験の旅",
            days=[],
            total_budget_estimate=50000,
        )
        input_data = ExplainerInput(
            itinerary=itinerary,
            wishes=TravelWishes(activities=["神社巡り"]),
        )
        prompt = agent._build_prompt(input_data)

        assert "京都の旅" in prompt
        assert "文化体験の旅" in prompt
        assert "50,000円" in prompt
        assert "神社巡り" in prompt

    def test_build_prompt_with_signals(self):
        """嗜好シグナル付きプロンプト"""
        agent = ExplainerAgent()
        itinerary = Itinerary(title="Test", summary="", days=[])
        input_data = ExplainerInput(
            itinerary=itinerary,
            wishes=TravelWishes(),
            preference_signals=[
                {"category": "likes", "tag": "温泉", "weight": 0.9},
                {"category": "dislikes", "tag": "混雑", "weight": 0.8},
            ],
        )
        prompt = agent._build_prompt(input_data)

        assert "温泉" in prompt
        assert "混雑" in prompt
        assert "0.9" in prompt


class TestExplainerFormatDays:
    """日程フォーマットのテスト"""

    def test_format_empty_days(self):
        """空の日程"""
        agent = ExplainerAgent()
        itinerary = Itinerary(title="Test", summary="", days=[])
        result = agent._format_days(itinerary)
        assert result == ""

    def test_format_days_with_items(self):
        """アイテム付き日程"""
        agent = ExplainerAgent()
        day = DayPlan(
            day_number=1,
            theme="寺社巡り",
            items=[
                ItineraryItem(
                    time_start="09:00",
                    time_end="11:00",
                    poi=POIBase(
                        name="金閣寺",
                        category="activity",
                        tags=["寺院", "世界遺産"],
                    ),
                )
            ],
            accommodation=POIBase(name="京都旅館", category="hotel"),
        )
        itinerary = Itinerary(title="Test", summary="", days=[day])
        result = agent._format_days(itinerary)

        assert "1日目" in result
        assert "寺社巡り" in result
        assert "09:00-11:00" in result
        assert "金閣寺" in result
        assert "寺院" in result
        assert "宿泊" in result
        assert "京都旅館" in result


# =============================================================================
# ExplainerAgent - Response Parsing Tests
# =============================================================================

class TestExplainerResponseParsing:
    """説明レスポンスパースのテスト"""

    def test_parse_valid_response(self):
        """有効なレスポンス"""
        agent = ExplainerAgent()
        response = json.dumps({
            "rationale": "この旅程は文化体験を重視しています",
            "highlights": ["金閣寺", "清水寺"],
            "preference_matches": [
                {"preference": "寺院巡り", "match": "世界遺産を含む"}
            ],
        })
        parsed = agent._parse_response(response)

        assert "文化体験" in parsed["rationale"]
        assert "金閣寺" in parsed["highlights"]

    def test_parse_invalid_response(self):
        """無効なレスポンス"""
        agent = ExplainerAgent()
        response = "Invalid JSON"
        parsed = agent._parse_response(response)

        assert "この旅程は" in parsed["rationale"]
        assert parsed["highlights"] == []


# =============================================================================
# ExplainerAgent - LLM Integration Tests
# =============================================================================

class TestExplainerLLMIntegration:
    """説明エージェントLLM統合テスト"""

    @pytest.mark.asyncio
    async def test_explain_success(self):
        """説明生成成功"""
        agent = ExplainerAgent()
        itinerary = Itinerary(
            title="京都の旅",
            summary="文化体験の旅",
            days=[],
        )
        input_data = ExplainerInput(
            itinerary=itinerary,
            wishes=TravelWishes(activities=["神社巡り"]),
            user_profile_summary="寺社仏閣が好き",
        )

        mock_response = json.dumps({
            "rationale": "お客様の寺社仏閣への関心を反映した旅程です",
            "highlights": ["金閣寺での静謐な時間"],
            "preference_matches": [
                {
                    "preference": "寺社仏閣好き",
                    "match": "世界遺産の寺院を中心に構成",
                    "poi_name": "金閣寺",
                }
            ],
        })

        with patch("app.agents.explainer.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            output = await agent.explain(input_data)

        assert "寺社仏閣" in output.rationale
        assert len(output.highlights) > 0
        assert len(output.preference_matches) > 0

    @pytest.mark.asyncio
    async def test_explain_max_retries_exceeded(self):
        """最大リトライ回数超過"""
        agent = ExplainerAgent()
        input_data = ExplainerInput(
            itinerary=Itinerary(title="Test", summary="", days=[]),
            wishes=TravelWishes(),
        )

        with patch("app.agents.explainer.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(RuntimeError) as exc_info:
                await agent.explain(input_data)

        assert "3 attempts" in str(exc_info.value)


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingletons:
    """シングルトンのテスト"""

    def test_planner_singleton(self):
        """プランナーシングルトン"""
        assert planner_agent is not None
        assert isinstance(planner_agent, PlannerAgent)

    def test_explainer_singleton(self):
        """説明エージェントシングルトン"""
        assert explainer_agent is not None
        assert isinstance(explainer_agent, ExplainerAgent)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """エッジケースのテスト"""

    def test_planner_no_budget(self):
        """予算未設定"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(destination="京都"),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )
        prompt = agent._build_prompt(input_data)
        assert "未定" in prompt

    def test_planner_per_day_budget(self):
        """1日あたり予算"""
        agent = PlannerAgent()
        input_data = PlannerInput(
            constraints=TravelConstraints(
                destination="京都",
                budget_per_day=10000,
            ),
            wishes=TravelWishes(),
            activities=[],
            foods=[],
            hotels=[],
        )
        prompt = agent._build_prompt(input_data)
        assert "1日あたり" in prompt
        assert "10,000円" in prompt

    def test_explainer_no_signals(self):
        """嗜好シグナルなし"""
        agent = ExplainerAgent()
        input_data = ExplainerInput(
            itinerary=Itinerary(title="Test", summary="", days=[]),
            wishes=TravelWishes(),
            preference_signals=[],
        )
        prompt = agent._build_prompt(input_data)
        assert "なし" in prompt

    def test_explainer_no_profile(self):
        """プロフィールなし（空文字）"""
        agent = ExplainerAgent()
        input_data = ExplainerInput(
            itinerary=Itinerary(title="Test", summary="", days=[]),
            wishes=TravelWishes(),
            user_profile_summary="",  # 空文字（Noneは許可されない）
        )
        prompt = agent._build_prompt(input_data)
        assert "未設定" in prompt
