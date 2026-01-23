"""
Planner Agent

制約とスコアリングで旅程を生成する。
重量モデル（HEAVY tier）を使用。
"""

import json
import logging
import re

from app.schemas.travel_planning import (
    DayPlan,
    Itinerary,
    ItineraryItem,
    PlannerInput,
    PlannerOutput,
    POIBase,
    POIRanked,
    TravelConstraints,
)
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは旅行計画の専門家です。
与えられた制約条件、希望、候補POI（観光地、飲食店、宿泊施設）を元に、
実行可能で魅力的な旅程を作成してください。

旅程作成のルール：
1. 制約条件（日程、予算、人数）を必ず守る
2. 移動時間を考慮し、無理のないスケジュールにする
3. 1日の活動は朝から夜まで、適度な休憩を入れる
4. 食事（朝・昼・夜）を適切に配置する
5. 宿泊先は毎晩必要

出力は以下のJSON形式で返してください：
{
  "title": "旅程のタイトル",
  "summary": "旅程の概要（2-3文）",
  "days": [
    {
      "day_number": 1,
      "date": "YYYY-MM-DD または null",
      "theme": "この日のテーマ",
      "items": [
        {
          "time_start": "09:00",
          "time_end": "11:00",
          "poi": {
            "name": "場所名",
            "category": "activity/food/hotel",
            "location": "場所",
            "description": "説明",
            "price_range": "価格帯",
            "duration_minutes": 所要時間,
            "tags": ["タグ1", "タグ2"]
          },
          "notes": "補足説明",
          "travel_from_previous": "前の場所からの移動（例：徒歩10分）"
        }
      ],
      "accommodation": {
        "name": "宿泊先名",
        "category": "hotel",
        ...
      }
    }
  ],
  "total_budget_estimate": 総予算見積もり（円）,
  "highlights": ["ハイライト1", "ハイライト2"]
}
"""

PLANNER_PROMPT = """以下の条件で旅程を作成してください。

【制約条件（必ず守る）】
- 目的地: {destination}
- 日程: {duration}日間
- 予算: {budget}
- 人数: {num_people}人
- 移動手段: {transportation}
- 身体的制限: {physical_limitations}

【希望（できれば叶える）】
- やりたいこと: {activities}
- 体験したいこと: {experiences}
- 食の好み: {food_preferences}
- 宿泊タイプ: {accommodation_type}
- 重視すること: {priority}
- 雰囲気: {mood}

【候補POI（観光・体験）】
{activity_pois}

【候補POI（食事）】
{food_pois}

【候補POI（宿泊）】
{hotel_pois}

{profile_context}

上記を考慮して、最適な旅程をJSON形式で出力してください。
JSONのみを出力し、他の説明は不要です。
"""


class PlannerAgent:
    """旅程生成エージェント"""

    async def plan(self, input_data: PlannerInput) -> PlannerOutput:
        """
        旅程を生成

        Args:
            input_data: プランナー入力

        Returns:
            生成された旅程
        """
        # プロンプトを構築
        prompt = self._build_prompt(input_data)

        # LLM呼び出し
        response = await self._call_llm_with_retry(prompt)

        # JSONパース
        parsed = self._parse_response(response)

        # Itineraryに変換
        itinerary = self._convert_to_itinerary(parsed)

        # スコアを計算
        score, score_breakdown = self._calculate_score(
            itinerary, input_data.constraints, input_data.wishes
        )

        return PlannerOutput(
            itinerary=itinerary,
            score=score,
            score_breakdown=score_breakdown,
        )

    def _build_prompt(self, input_data: PlannerInput) -> str:
        """プロンプトを構築"""
        constraints = input_data.constraints

        # 日程の文字列化
        duration = constraints.duration_days or "未定"

        # 予算の文字列化
        if constraints.budget_total:
            budget = f"総額 約{constraints.budget_total:,}円"
        elif constraints.budget_per_day:
            budget = f"1日あたり 約{constraints.budget_per_day:,}円"
        else:
            budget = "未定"

        # POIリストの文字列化
        activity_pois = self._format_poi_list(input_data.activities)
        food_pois = self._format_poi_list(input_data.foods)
        hotel_pois = self._format_poi_list(input_data.hotels)

        # プロフィールコンテキスト
        profile_context = ""
        if input_data.user_profile_summary:
            profile_context = (
                f"\n【ユーザープロフィール】\n{input_data.user_profile_summary}"
            )

        wishes = input_data.wishes

        # 身体的制限
        physical_limitations = (
            ", ".join(constraints.physical_limitations)
            if constraints.physical_limitations
            else "特になし"
        )

        return PLANNER_PROMPT.format(
            destination=constraints.destination or "未定",
            duration=duration,
            budget=budget,
            num_people=constraints.num_people,
            transportation=constraints.transportation or "特になし",
            physical_limitations=physical_limitations,
            activities=", ".join(wishes.activities)
            if wishes.activities
            else "特になし",
            experiences=", ".join(wishes.experiences)
            if wishes.experiences
            else "特になし",
            food_preferences=(
                ", ".join(wishes.food_preferences)
                if wishes.food_preferences
                else "特になし"
            ),
            accommodation_type=wishes.accommodation_type or "特になし",
            priority=wishes.priority or "特になし",
            mood=wishes.mood or "特になし",
            activity_pois=activity_pois,
            food_pois=food_pois,
            hotel_pois=hotel_pois,
            profile_context=profile_context,
        )

    def _format_poi_list(self, pois: list[POIRanked]) -> str:
        """POIリストを文字列化"""
        if not pois:
            return "候補なし"

        lines = []
        for i, poi in enumerate(pois[:10], 1):  # 上位10件
            line = f"{i}. {poi.name}"
            if poi.description:
                line += f" - {poi.description[:100]}"
            if poi.price_range:
                line += f" ({poi.price_range})"
            if poi.match_reasons:
                line += f" [マッチ: {', '.join(poi.match_reasons)}]"
            lines.append(line)

        return "\n".join(lines)

    async def _call_llm_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
    ) -> str:
        """リトライ付きLLM呼び出し"""
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await llm_gateway.generate(
                    prompt=prompt,
                    tier=ModelTier.HEAVY,  # 複雑な推論なので重量モデル
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_tokens=4096,
                    agent_name="planner",
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Planner LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    prompt = prompt + "\n\n必ず有効なJSON形式で出力してください。"

        raise RuntimeError(f"Planner failed after {max_retries} attempts: {last_error}")

    def _parse_response(self, response: str) -> dict:
        """LLMレスポンスからJSONをパース"""
        # JSONブロックを抽出
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse planner response: {e}")
            logger.debug(f"Raw response: {response}")
            return {"title": "旅程", "summary": "", "days": [], "highlights": []}

    def _convert_to_itinerary(self, parsed: dict) -> Itinerary:
        """パースされたJSONをItineraryに変換"""
        days = []

        for day_data in parsed.get("days", []):
            items = []
            for item_data in day_data.get("items", []):
                poi_data = item_data.get("poi", {})
                poi = POIBase(
                    name=poi_data.get("name", ""),
                    category=poi_data.get("category", "activity"),
                    location=poi_data.get("location", ""),
                    description=poi_data.get("description", ""),
                    price_range=poi_data.get("price_range", ""),
                    duration_minutes=poi_data.get("duration_minutes"),
                    opening_hours=poi_data.get("opening_hours", ""),
                    rating=poi_data.get("rating"),
                    tags=poi_data.get("tags", []),
                    source_url=poi_data.get("source_url", ""),
                )
                items.append(
                    ItineraryItem(
                        time_start=item_data.get("time_start", ""),
                        time_end=item_data.get("time_end", ""),
                        poi=poi,
                        notes=item_data.get("notes", ""),
                        travel_from_previous=item_data.get("travel_from_previous", ""),
                    )
                )

            # 宿泊先
            accommodation = None
            acc_data = day_data.get("accommodation")
            if acc_data:
                accommodation = POIBase(
                    name=acc_data.get("name", ""),
                    category="hotel",
                    location=acc_data.get("location", ""),
                    description=acc_data.get("description", ""),
                    price_range=acc_data.get("price_range", ""),
                    tags=acc_data.get("tags", []),
                )

            days.append(
                DayPlan(
                    day_number=day_data.get("day_number", len(days) + 1),
                    date=day_data.get("date"),
                    theme=day_data.get("theme", ""),
                    items=items,
                    accommodation=accommodation,
                )
            )

        return Itinerary(
            title=parsed.get("title", "旅程"),
            summary=parsed.get("summary", ""),
            days=days,
            total_budget_estimate=parsed.get("total_budget_estimate"),
            highlights=parsed.get("highlights", []),
        )

    def _calculate_score(
        self,
        itinerary: Itinerary,
        constraints: TravelConstraints,
        wishes,
    ) -> tuple[float, dict]:
        """旅程のスコアを計算"""
        scores = {}

        # 1. 日程充実度（アイテム数）
        total_items = sum(len(day.items) for day in itinerary.days)
        expected_items = len(itinerary.days) * 4  # 1日4アクティビティ目安
        completeness = min(total_items / max(expected_items, 1), 1.0)
        scores["completeness"] = completeness

        # 2. 宿泊カバー率
        days_with_accommodation = sum(1 for day in itinerary.days if day.accommodation)
        accommodation_coverage = days_with_accommodation / max(len(itinerary.days), 1)
        scores["accommodation"] = accommodation_coverage

        # 3. 食事カバー率（1日3食目安）
        food_items = sum(
            1
            for day in itinerary.days
            for item in day.items
            if item.poi.category == "food"
        )
        expected_meals = len(itinerary.days) * 3
        meal_coverage = min(food_items / max(expected_meals, 1), 1.0)
        scores["meals"] = meal_coverage

        # 4. 予算適合度（予算が設定されている場合）
        budget_score = 1.0
        if constraints.budget_total and itinerary.total_budget_estimate:
            if itinerary.total_budget_estimate <= constraints.budget_total:
                budget_score = 1.0
            else:
                over_ratio = itinerary.total_budget_estimate / constraints.budget_total
                budget_score = max(0, 2 - over_ratio)  # 2倍超えで0
        scores["budget"] = budget_score

        # 総合スコア（重み付け平均）
        weights = {
            "completeness": 0.3,
            "accommodation": 0.25,
            "meals": 0.25,
            "budget": 0.2,
        }
        total_score = sum(scores[k] * weights[k] for k in weights)

        return total_score, scores


# Singleton instance
planner_agent = PlannerAgent()
