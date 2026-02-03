"""
Planner Agent

制約とスコアリングで旅程を生成する。
重量モデル（HEAVY tier）を使用。
"""

import json
import logging
import re

from app.core.exceptions import LLMParseError
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
5. 宿泊先は最終日以外の各日に必要（N日間の旅行 = N-1泊）
   例: 2日間 → 1泊（1日目のみ宿泊）、3日間 → 2泊（1日目と2日目に宿泊）
6. days配列の要素数は指定された日数と完全一致させること

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
            "tags": ["タグ1", "タグ2"],
            "match_tags": [{"text": "マッチ理由", "type": "preference または wish"}]
          },
          "notes": "補足説明",
          "travel_from_previous": "前の場所からの移動（例：徒歩10分）"
        }
      ],
      "accommodation": {
        "name": "宿泊先名",
        "category": "hotel",
        "match_tags": [{"text": "マッチ理由", "type": "preference または wish"}],
        ...
      }
    }
  ],
  "total_budget_estimate": 総予算見積もり（円）,
  "highlights": ["ハイライト1", "ハイライト2"]
}

match_tagsについて:
- 候補POIに記載されているマッチ情報を参照し、そのまま出力に含めてください
- type="preference" は長期的なユーザー嗜好、type="wish" は今回の旅行での要望を示します
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

【候補POI（交通・アクセス）】
{transportation_pois}

{profile_context}

上記を考慮して、最適な旅程をJSON形式で出力してください。
JSONのみを出力し、他の説明は不要です。
"""


class PlannerAgent:
    """旅程生成エージェント"""

    async def plan(self, input_data: PlannerInput) -> PlannerOutput:
        """
        旅程を生成

        LLM呼び出し → JSONパース → バリデーション を一体のリトライループで実行。
        JSONパース失敗や0日旅程もリトライ対象とする。

        Args:
            input_data: プランナー入力

        Returns:
            生成された旅程
        """
        prompt = self._build_prompt(input_data)
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # 1. LLM呼び出し
                current_prompt = prompt
                if attempt > 0:
                    expected_days = input_data.constraints.duration_days
                    days_instruction = ""
                    if expected_days:
                        days_instruction = (
                            f"days配列は必ず{expected_days}日分（{expected_days}要素）にしてください。"
                        )
                    current_prompt = (
                        prompt
                        + "\n\n注意: 必ず有効なJSON形式で出力してください。"
                        f"daysは1日以上含めてください。{days_instruction}"
                        "JSONのみを出力し、他の説明は不要です。"
                    )

                response = await llm_gateway.generate(
                    prompt=current_prompt,
                    tier=ModelTier.HEAVY,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_tokens=4096,
                    agent_name="planner",
                )

                # 2. JSONパース（失敗時は例外）
                parsed = self._parse_response(response)

                # 3. バリデーション: daysが空なら再試行
                days = parsed.get("days", [])
                if not days:
                    raise LLMParseError(
                        message="Planner returned empty days array",
                        raw_output=response[:500],
                        attempts=attempt + 1,
                    )

                # 3b. 日数一致チェック
                expected_days = input_data.constraints.duration_days
                if expected_days and len(days) != expected_days:
                    raise LLMParseError(
                        message=(
                            f"Planner returned {len(days)} days "
                            f"but expected {expected_days} days"
                        ),
                        raw_output=response[:500],
                        attempts=attempt + 1,
                    )

                # 4. Itineraryに変換
                itinerary = self._convert_to_itinerary(parsed)

                # 5. スコアを計算
                score, score_breakdown = self._calculate_score(
                    itinerary, input_data.constraints, input_data.wishes
                )

                return PlannerOutput(
                    itinerary=itinerary,
                    score=score,
                    score_breakdown=score_breakdown,
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Planner attempt {attempt + 1}/{max_retries} failed: {e}"
                )

        raise LLMParseError(
            message=f"Planner failed after {max_retries} attempts: {last_error}",
            attempts=max_retries,
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
        transportation_pois = self._format_poi_list(input_data.transportation)

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
            transportation_pois=transportation_pois,
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
                # マッチ理由をタイプ付きで表示
                formatted_reasons = []
                for r in poi.match_reasons:
                    if isinstance(r, dict):
                        type_label = "嗜好" if r.get("type") == "preference" else "要望"
                        formatted_reasons.append(f"{type_label}:{r.get('text', '')}")
                    else:
                        # 後方互換: 文字列の場合
                        formatted_reasons.append(str(r))
                if formatted_reasons:
                    line += f" [マッチ: {', '.join(formatted_reasons)}]"
                # match_tagsをJSON形式で追加（LLMが参照できるように）
                line += f" match_tags={poi.match_reasons}"
            lines.append(line)

        return "\n".join(lines)

    def _parse_response(self, response: str) -> dict:
        """LLMレスポンスからJSONをパース

        Raises:
            LLMParseError: JSONパースに失敗した場合
        """
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
            raise LLMParseError(
                message=f"Failed to parse planner response: {e}",
                raw_output=response[:500],
            )

    def _convert_to_itinerary(self, parsed: dict) -> Itinerary:
        """パースされたJSONをItineraryに変換"""
        days = []

        for day_data in parsed.get("days", []):
            items = []
            for item_data in day_data.get("items", []):
                poi_data = item_data.get("poi", {})
                # match_tagsを抽出（LLM出力から）
                match_tags = poi_data.get("match_tags", [])
                # 形式の検証: 各要素が{"text": ..., "type": ...}の形式かチェック
                validated_match_tags = []
                for tag in match_tags:
                    if isinstance(tag, dict) and "text" in tag and "type" in tag:
                        validated_match_tags.append(tag)

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
                    match_tags=validated_match_tags,
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
                # 宿泊先のmatch_tagsも抽出
                acc_match_tags = acc_data.get("match_tags", [])
                validated_acc_tags = []
                for tag in acc_match_tags:
                    if isinstance(tag, dict) and "text" in tag and "type" in tag:
                        validated_acc_tags.append(tag)

                accommodation = POIBase(
                    name=acc_data.get("name", ""),
                    category="hotel",
                    location=acc_data.get("location", ""),
                    description=acc_data.get("description", ""),
                    price_range=acc_data.get("price_range", ""),
                    tags=acc_data.get("tags", []),
                    match_tags=validated_acc_tags,
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

        # 2. 宿泊カバー率（最終日は宿泊不要: N日間 = N-1泊）
        days_with_accommodation = sum(1 for day in itinerary.days if day.accommodation)
        expected_nights = max(len(itinerary.days) - 1, 0)
        if expected_nights > 0:
            accommodation_coverage = days_with_accommodation / expected_nights
        else:
            accommodation_coverage = 1.0  # 1日旅行は宿泊不要
        scores["accommodation"] = min(accommodation_coverage, 1.0)

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

        # 5. 日数一致度
        duration_match = 1.0
        if constraints.duration_days:
            if len(itinerary.days) == constraints.duration_days:
                duration_match = 1.0
            else:
                duration_match = 0.0
        scores["duration_match"] = duration_match

        # 総合スコア（重み付け平均）
        weights = {
            "completeness": 0.25,
            "accommodation": 0.2,
            "meals": 0.2,
            "budget": 0.15,
            "duration_match": 0.2,
        }
        total_score = sum(scores[k] * weights[k] for k in weights)

        return total_score, scores


# Singleton instance
planner_agent = PlannerAgent()
