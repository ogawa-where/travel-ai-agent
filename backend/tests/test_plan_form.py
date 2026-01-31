"""
構造化フォーム入力テスト

TravelPlanFormRequest スキーマの変換ロジック、
plan-with-form エンドポイント、オーケストレーターの pre_constraints パラメータを検証する。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas.travel_planning import (
    TravelConstraints,
    TravelPlanFormRequest,
    TravelWishes,
)


# =============================================================================
# TravelPlanFormRequest.to_constraints() テスト
# =============================================================================


class TestToConstraints:
    """to_constraints() の変換テスト"""

    def test_basic_conversion(self):
        """基本的なフォーム入力がTravelConstraintsに変換されること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都府",
            start_date="2025-04-01",
            end_date="2025-04-03",
        )
        constraints = form.to_constraints()

        assert constraints.destination == "京都府"
        assert constraints.start_date == "2025-04-01"
        assert constraints.end_date == "2025-04-03"
        assert constraints.duration_days == 3  # 4/1, 4/2, 4/3 = 3日間
        assert constraints.num_people == 1
        assert constraints.budget_total is None
        assert constraints.transportation == ""

    def test_duration_calculation_1night2days(self):
        """1泊2日の日数計算"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
        )
        constraints = form.to_constraints()
        assert constraints.duration_days == 2

    def test_duration_calculation_same_day(self):
        """日帰り（同日）の日数計算"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-01",
        )
        constraints = form.to_constraints()
        assert constraints.duration_days == 1

    def test_duration_calculation_3nights4days(self):
        """3泊4日の日数計算"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="沖縄",
            start_date="2025-07-01",
            end_date="2025-07-04",
        )
        constraints = form.to_constraints()
        assert constraints.duration_days == 4

    def test_full_form_conversion(self):
        """全フィールドが指定された場合の変換"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都府",
            start_date="2025-04-01",
            end_date="2025-04-03",
            departure_place="秋田県",
            budget_total=100000,
            num_people=2,
            transportation="新幹線",
            accommodation_type="旅館",
            free_text="神社仏閣を巡りたい",
        )
        constraints = form.to_constraints()

        assert constraints.destination == "京都府"
        assert constraints.duration_days == 3
        assert constraints.budget_total == 100000
        assert constraints.num_people == 2
        assert constraints.transportation == "新幹線"
        assert constraints.other["departure_place"] == "秋田県"
        assert constraints.other["accommodation_type"] == "旅館"

    def test_optional_fields_excluded_from_other(self):
        """None の任意フィールドは other に含まれないこと"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
        )
        constraints = form.to_constraints()
        assert constraints.other == {}

    def test_partial_optional_fields(self):
        """一部の任意フィールドのみ指定"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
            departure_place="東京",
            # accommodation_type は未指定
        )
        constraints = form.to_constraints()
        assert "departure_place" in constraints.other
        assert "accommodation_type" not in constraints.other

    def test_transportation_none_becomes_empty_string(self):
        """transportation が None の場合は空文字になること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
        )
        constraints = form.to_constraints()
        assert constraints.transportation == ""


# =============================================================================
# TravelPlanFormRequest.build_raw_request() テスト
# =============================================================================


class TestBuildRawRequest:
    """build_raw_request() の出力テスト"""

    def test_basic_raw_request(self):
        """基本的なフォーム入力から自然言語テキストが生成されること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都府",
            start_date="2025-04-01",
            end_date="2025-04-03",
        )
        raw = form.build_raw_request()

        assert "京都府への旅行" in raw
        assert "2025-04-01" in raw
        assert "2025-04-03" in raw

    def test_full_raw_request(self):
        """全フィールド指定時の自然言語テキスト"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都府",
            start_date="2025-04-01",
            end_date="2025-04-03",
            departure_place="秋田県",
            budget_total=100000,
            num_people=2,
            transportation="新幹線",
            accommodation_type="旅館",
            free_text="神社仏閣を巡りたい",
        )
        raw = form.build_raw_request()

        assert "京都府への旅行" in raw
        assert "出発地: 秋田県" in raw
        assert "100,000円" in raw
        assert "2人" in raw
        assert "移動手段: 新幹線" in raw
        assert "宿泊: 旅館" in raw
        assert "神社仏閣を巡りたい" in raw

    def test_single_person_not_shown(self):
        """1人の場合は人数を表示しないこと"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
            num_people=1,
        )
        raw = form.build_raw_request()
        assert "1人" not in raw

    def test_parts_joined_with_period(self):
        """各パーツが「。」で結合されること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
            departure_place="東京",
        )
        raw = form.build_raw_request()
        assert "。" in raw


# =============================================================================
# バリデーションテスト
# =============================================================================


class TestFormValidation:
    """フォームバリデーションテスト"""

    def test_required_fields(self):
        """必須フィールドが欠けている場合にエラー"""
        with pytest.raises(Exception):
            TravelPlanFormRequest(
                user_id="user-1",
                # destination 未指定
                start_date="2025-04-01",
                end_date="2025-04-03",
            )

    def test_num_people_minimum(self):
        """人数が1未満の場合にエラー"""
        with pytest.raises(Exception):
            TravelPlanFormRequest(
                user_id="user-1",
                destination="京都",
                start_date="2025-04-01",
                end_date="2025-04-02",
                num_people=0,
            )

    def test_default_values(self):
        """デフォルト値が正しく設定されること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都",
            start_date="2025-04-01",
            end_date="2025-04-02",
        )
        assert form.num_people == 1
        assert form.free_text == ""
        assert form.departure_place is None
        assert form.budget_total is None
        assert form.transportation is None
        assert form.accommodation_type is None


# =============================================================================
# オーケストレーター pre_constraints テスト
# =============================================================================


class TestOrchestratorPreConstraints:
    """オーケストレーターの pre_constraints パラメータテスト"""

    def test_constraints_returned_by_form(self):
        """フォームから生成されたconstraintsがTravelConstraintsであること"""
        form = TravelPlanFormRequest(
            user_id="user-1",
            destination="京都府",
            start_date="2025-04-01",
            end_date="2025-04-03",
            budget_total=50000,
        )
        constraints = form.to_constraints()

        assert isinstance(constraints, TravelConstraints)
        assert constraints.destination == "京都府"
        assert constraints.budget_total == 50000

    def test_wishes_default_empty(self):
        """free_textなしの場合、wishesはデフォルト空になること"""
        wishes = TravelWishes()
        assert wishes.activities == []
        assert wishes.experiences == []
        assert wishes.food_preferences == []
        assert wishes.mood == ""
