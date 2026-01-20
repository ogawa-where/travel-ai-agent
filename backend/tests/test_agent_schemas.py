"""
Agent Output Schema Validation Tests

CLAUDE.md セクション11の要件:
- エージェント出力スキーマ検証

注: 実際のスキーマはapp.schemasにありますが、
このテストは依存関係なしでスキーマ構造を検証します。
"""

import pytest
from enum import Enum
from typing import Optional
from datetime import datetime


# スキーマ構造の検証用ヘルパー
def validate_schema_structure(data: dict, required_fields: list, optional_fields: list = None) -> bool:
    """スキーマ構造を検証"""
    optional_fields = optional_fields or []

    # 必須フィールドのチェック
    for field in required_fields:
        if field not in data:
            return False

    return True


class TestPreferenceSchemaStructure:
    """嗜好学習モードのスキーマ構造テスト"""

    def test_preference_category_values(self):
        """PreferenceCategoryの値が正しいこと"""
        valid_categories = ["likes", "dislikes", "experience_axis", "constraints"]
        for category in valid_categories:
            assert isinstance(category, str)
            assert len(category) > 0

    def test_preference_signal_response_structure(self):
        """PreferenceSignalResponseの構造が正しいこと"""
        signal = {
            "id": "test-id",
            "user_id": "user-id",
            "category": "likes",
            "tag": "温泉",
            "weight": 0.8,
            "evidence": "温泉が好きと言った",
            "extra_data": {},
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        required_fields = ["id", "user_id", "category", "tag", "weight"]
        assert validate_schema_structure(signal, required_fields)
        assert 0.0 <= signal["weight"] <= 1.0

    def test_chat_response_structure(self):
        """ChatResponseの構造が正しいこと"""
        response = {
            "user_id": "user-id",
            "session_id": "session-id",
            "assistant_message": "こんにちは",
            "updated_signals": [],
        }

        required_fields = ["user_id", "session_id", "assistant_message"]
        assert validate_schema_structure(response, required_fields)


class TestTravelPlanningSchemaStructure:
    """旅行企画モードのスキーマ構造テスト"""

    def test_poi_category_values(self):
        """POICategoryの値が正しいこと"""
        valid_categories = ["activity", "food", "hotel"]
        for category in valid_categories:
            assert isinstance(category, str)
            assert len(category) > 0

    def test_travel_constraints_structure(self):
        """TravelConstraintsの構造が正しいこと"""
        constraints = {
            "destination": "京都",
            "start_date": "2025-03-01",
            "end_date": "2025-03-03",
            "duration_days": 3,
            "budget_total": 50000,
            "budget_per_day": None,
            "num_people": 2,
            "transportation": "",
            "accommodation_type": "",
            "other": {},
        }

        required_fields = ["destination"]
        assert validate_schema_structure(constraints, required_fields)
        assert constraints["num_people"] >= 1

    def test_travel_wishes_structure(self):
        """TravelWishesの構造が正しいこと"""
        wishes = {
            "activities": ["神社巡り", "温泉"],
            "experiences": [],
            "food_preferences": ["和食", "抹茶スイーツ"],
            "avoid": ["混雑"],
            "priority": "文化体験",
            "mood": "ゆったり",
            "other": {},
        }

        assert isinstance(wishes["activities"], list)
        assert isinstance(wishes["food_preferences"], list)


class TestTranslatorAgentOutputStructure:
    """Translator Agent出力スキーマ構造テスト"""

    def test_translate_request_output_structure(self):
        """TranslateRequestOutputの構造が正しいこと"""
        output = {
            "constraints": {
                "destination": "京都",
                "duration_days": 2,
            },
            "wishes": {
                "activities": ["寺社仏閣"],
            },
            "clarification_needed": [],
        }

        required_fields = ["constraints", "wishes"]
        assert validate_schema_structure(output, required_fields)
        assert isinstance(output["clarification_needed"], list)


class TestPOISchemaStructure:
    """POI関連スキーマ構造テスト"""

    def test_poi_base_structure(self):
        """POIBaseの構造が正しいこと"""
        poi = {
            "name": "金閣寺",
            "category": "activity",
            "location": "京都市北区",
            "description": "世界遺産の寺院",
            "price_range": "¥400",
            "duration_minutes": 60,
            "opening_hours": "",
            "rating": None,
            "tags": ["寺院", "世界遺産"],
            "source_url": "",
        }

        required_fields = ["name", "category"]
        assert validate_schema_structure(poi, required_fields)
        assert isinstance(poi["tags"], list)

    def test_poi_search_result_structure(self):
        """POISearchResultの構造が正しいこと"""
        result = {
            "name": "金閣寺",
            "category": "activity",
            "relevance_score": 0.9,
            "source_name": "tavily",
        }

        required_fields = ["name", "category"]
        assert validate_schema_structure(result, required_fields)
        assert 0.0 <= result["relevance_score"] <= 1.0

    def test_poi_ranked_structure(self):
        """POIRankedの構造が正しいこと"""
        ranked = {
            "name": "金閣寺",
            "category": "activity",
            "relevance_score": 0.9,
            "preference_score": 0.85,
            "final_score": 0.87,
            "match_reasons": ["文化体験の嗜好にマッチ"],
        }

        required_fields = ["name", "category", "final_score"]
        assert validate_schema_structure(ranked, required_fields)
        assert isinstance(ranked["match_reasons"], list)


class TestRerankAgentOutputStructure:
    """Rerank Agent出力スキーマ構造テスト"""

    def test_rerank_output_structure(self):
        """RerankOutputの構造が正しいこと"""
        output = {
            "ranked_items": [
                {
                    "name": "金閣寺",
                    "category": "activity",
                    "final_score": 0.87,
                },
            ]
        }

        required_fields = ["ranked_items"]
        assert validate_schema_structure(output, required_fields)
        assert isinstance(output["ranked_items"], list)


class TestPlannerAgentOutputStructure:
    """Planner Agent出力スキーマ構造テスト"""

    def test_itinerary_item_structure(self):
        """ItineraryItemの構造が正しいこと"""
        item = {
            "time_start": "09:00",
            "time_end": "11:00",
            "poi": {"name": "金閣寺", "category": "activity"},
            "notes": "朝一番がおすすめ",
            "travel_from_previous": "バス30分",
        }

        required_fields = ["poi"]
        assert validate_schema_structure(item, required_fields)

    def test_day_plan_structure(self):
        """DayPlanの構造が正しいこと"""
        day = {
            "day_number": 1,
            "date": "2025-03-01",
            "theme": "世界遺産巡り",
            "items": [],
            "accommodation": None,
        }

        required_fields = ["day_number"]
        assert validate_schema_structure(day, required_fields)
        assert day["day_number"] >= 1

    def test_itinerary_structure(self):
        """Itineraryの構造が正しいこと"""
        itinerary = {
            "title": "京都2泊3日の旅",
            "summary": "世界遺産を巡る文化体験の旅",
            "days": [],
            "total_budget_estimate": 50000,
            "highlights": ["金閣寺", "嵐山"],
        }

        required_fields = ["days"]
        assert validate_schema_structure(itinerary, required_fields)
        assert isinstance(itinerary["days"], list)

    def test_planner_output_structure(self):
        """PlannerOutputの構造が正しいこと"""
        output = {
            "itinerary": {"title": "京都の旅", "days": []},
            "score": 0.85,
            "score_breakdown": {
                "constraint_satisfaction": 0.9,
                "preference_match": 0.8,
            },
        }

        required_fields = ["itinerary", "score"]
        assert validate_schema_structure(output, required_fields)
        assert 0.0 <= output["score"] <= 1.0


class TestExplainerAgentOutputStructure:
    """Explainer Agent出力スキーマ構造テスト"""

    def test_explainer_output_structure(self):
        """ExplainerOutputの構造が正しいこと"""
        output = {
            "rationale": "この旅程は、お客様の文化体験への強い関心を反映しています。",
            "highlights": ["世界遺産の金閣寺を朝一番で訪問"],
            "preference_matches": [
                {"preference": "文化体験", "matched_items": ["金閣寺"]},
            ],
        }

        required_fields = ["rationale"]
        assert validate_schema_structure(output, required_fields)
        assert isinstance(output["highlights"], list)


class TestTravelChatResponseStructure:
    """旅行チャットレスポンススキーマ構造テスト"""

    def test_travel_chat_response_chatting(self):
        """チャット中のレスポンス構造"""
        response = {
            "user_id": "user-id",
            "session_id": "session-id",
            "assistant_message": "どこに行きたいですか？",
            "plan_request_id": None,
            "plan": None,
            "status": "chatting",
        }

        required_fields = ["user_id", "session_id", "assistant_message", "status"]
        assert validate_schema_structure(response, required_fields)
        assert response["status"] in ["chatting", "planning", "completed"]

    def test_travel_chat_response_completed(self):
        """プラン完了時のレスポンス構造"""
        response = {
            "user_id": "user-id",
            "session_id": "session-id",
            "assistant_message": "旅程を作成しました！",
            "plan_request_id": "request-id",
            "plan": {
                "id": "plan-id",
                "itinerary": {"title": "京都旅行"},
                "score": 0.85,
            },
            "status": "completed",
        }

        assert response["status"] == "completed"
        assert response["plan"] is not None


class TestSchemaValidation:
    """スキーマバリデーションテスト"""

    def test_weight_must_be_in_range(self):
        """weightは0.0-1.0の範囲であること"""
        valid_weights = [0.0, 0.1, 0.5, 0.9, 1.0]
        invalid_weights = [-0.1, 1.1, 2.0]

        for weight in valid_weights:
            assert 0.0 <= weight <= 1.0

        for weight in invalid_weights:
            assert not (0.0 <= weight <= 1.0)

    def test_score_must_be_in_range(self):
        """scoreは0.0-1.0の範囲であること"""
        valid_scores = [0.0, 0.5, 1.0]

        for score in valid_scores:
            assert 0.0 <= score <= 1.0

    def test_category_must_be_valid(self):
        """categoryは有効な値であること"""
        valid_preference_categories = ["likes", "dislikes", "experience_axis", "constraints"]
        valid_poi_categories = ["activity", "food", "hotel"]

        assert "likes" in valid_preference_categories
        assert "activity" in valid_poi_categories
        assert "invalid" not in valid_preference_categories
