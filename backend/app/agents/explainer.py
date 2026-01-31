"""
Explainer Agent

嗜好と体験軸に基づいて旅程の根拠説明を生成する。
重量モデル（HEAVY tier）を使用。
"""

import json
import logging
import re

from app.schemas.travel_planning import (
    ExplainerInput,
    ExplainerOutput,
    Itinerary,
)
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは旅行プランの説明の専門家です。
生成された旅程が、なぜユーザーにとって最適なのかを説明してください。

説明では以下を含めてください：
1. 旅程全体の魅力（2-3文）
2. ユーザーの嗜好・希望とのマッチング
3. 体験軸（文化/自然/学び/参加型/ウェルネスなど）との関連
4. ハイライトとなるポイント

出力は以下のJSON形式で返してください：
{
  "rationale": "旅程全体の説明（200-400文字）",
  "highlights": ["ハイライト1", "ハイライト2", "ハイライト3"],
  "preference_matches": [
    {
      "preference": "ユーザーの嗜好/希望",
      "match": "どのようにマッチしているか",
      "poi_name": "関連するPOI名（あれば）"
    }
  ]
}
"""

EXPLAINER_PROMPT = """以下の旅程について、ユーザーへの説明を作成してください。

【旅程概要】
タイトル: {title}
概要: {summary}
日数: {num_days}日間
予算見積もり: {budget}

【日程詳細】
{days_detail}

【ユーザープロフィール】
{profile}

【ユーザーの希望】
- やりたいこと: {activities}
- 体験したいこと: {experiences}
- 食の好み: {food_preferences}
- 重視すること: {priority}
- 雰囲気: {mood}

【ユーザーの嗜好シグナル】
{preference_signals}

上記を考慮して、なぜこの旅程がユーザーに最適なのかをJSON形式で説明してください。
JSONのみを出力し、他の説明は不要です。
"""


class ExplainerAgent:
    """根拠説明エージェント"""

    async def explain(self, input_data: ExplainerInput) -> ExplainerOutput:
        """
        旅程の説明を生成

        Args:
            input_data: 説明生成入力

        Returns:
            説明出力
        """
        # プロンプトを構築
        prompt = self._build_prompt(input_data)

        # LLM呼び出し
        response = await self._call_llm_with_retry(prompt)

        # JSONパース
        parsed = self._parse_response(response)

        return ExplainerOutput(
            rationale=parsed.get("rationale", ""),
            highlights=parsed.get("highlights", []),
            preference_matches=parsed.get("preference_matches", []),
        )

    def _build_prompt(self, input_data: ExplainerInput) -> str:
        """プロンプトを構築"""
        itinerary = input_data.itinerary
        wishes = input_data.wishes

        # 日程詳細を文字列化
        days_detail = self._format_days(itinerary)

        # 嗜好シグナルを文字列化
        signals_text = "なし"
        if input_data.preference_signals:
            signals_list = []
            for s in input_data.preference_signals:
                category = s.get("category", "")
                tag = s.get("tag", "")
                weight = s.get("weight", 1.0)
                signals_list.append(f"- {category}: {tag} (重み: {weight})")
            signals_text = "\n".join(signals_list)

        # 予算
        budget = "未定"
        if itinerary.total_budget_estimate:
            budget = f"約{itinerary.total_budget_estimate:,}円"

        return EXPLAINER_PROMPT.format(
            title=itinerary.title,
            summary=itinerary.summary,
            num_days=len(itinerary.days),
            budget=budget,
            days_detail=days_detail,
            profile=input_data.user_profile_summary or "未設定",
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
            priority=wishes.priority or "特になし",
            mood=wishes.mood or "特になし",
            preference_signals=signals_text,
        )

    def _format_days(self, itinerary: Itinerary) -> str:
        """日程を文字列化"""
        lines = []

        for day in itinerary.days:
            lines.append(f"\n=== {day.day_number}日目: {day.theme or '探索'} ===")

            for item in day.items:
                time_range = (
                    f"{item.time_start}-{item.time_end}" if item.time_start else ""
                )
                poi = item.poi
                line = f"  {time_range} {poi.name} ({poi.category})"
                if poi.tags:
                    line += f" [タグ: {', '.join(poi.tags[:3])}]"
                lines.append(line)

            if day.accommodation:
                lines.append(f"  【宿泊】{day.accommodation.name}")

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
                    tier=ModelTier.HEAVY,  # 説明生成は重量モデル
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_tokens=2048,
                    agent_name="explainer",
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Explainer LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    prompt = prompt + "\n\n必ず有効なJSON形式で出力してください。"

        raise RuntimeError(
            f"Explainer failed after {max_retries} attempts: {last_error}"
        )

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
            logger.error(f"Failed to parse explainer response: {e}")
            logger.debug(f"Raw response: {response}")
            return {
                "rationale": "この旅程はあなたの希望に合わせて作成されました。",
                "highlights": [],
                "preference_matches": [],
            }


# Singleton instance
explainer_agent = ExplainerAgent()
