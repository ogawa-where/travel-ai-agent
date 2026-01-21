"""
Translator Agent

ユーザーの自然言語入力を構造化された制約・希望に変換する。
軽量モデル（LIGHT tier）を使用。
"""

import json
import logging
import re

from app.schemas.travel_planning import (
    TranslateRequestInput,
    TranslateRequestOutput,
    TravelConstraints,
    TravelWishes,
)
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは旅行計画のアシスタントです。
ユーザーの旅行リクエストを分析し、構造化されたJSON形式で出力してください。

出力は必ず以下のJSON形式で返してください：
{
  "constraints": {
    "destination": "目的地・地域",
    "start_date": "開始日 (YYYY-MM-DD) または null",
    "end_date": "終了日 (YYYY-MM-DD) または null",
    "duration_days": 日数 または null,
    "budget_total": 総予算（円）または null,
    "budget_per_day": 1日あたり予算（円）または null,
    "num_people": 人数,
    "transportation": "移動手段の制約",
    "accommodation_type": "宿泊タイプの希望",
    "other": {}
  },
  "wishes": {
    "activities": ["やりたいアクティビティのリスト"],
    "experiences": ["体験したいことのリスト"],
    "food_preferences": ["食べたいもののリスト"],
    "avoid": ["避けたいことのリスト"],
    "priority": "最も重視すること",
    "mood": "旅の雰囲気・テーマ",
    "other": {}
  },
  "clarification_needed": ["確認が必要な項目のリスト"]
}

注意：
- 明示されていない項目はnullまたは空リストにする
- 予算は数値のみ（単位なし）
- 日付はYYYY-MM-DD形式
- clarification_neededには、曖昧で確認が必要な項目を入れる
"""

TRANSLATE_PROMPT = """以下の旅行リクエストを分析してください。

ユーザーのリクエスト：
{raw_request}

{profile_context}

上記を分析し、JSON形式で出力してください。
JSONのみを出力し、他の説明は不要です。
"""


class TranslatorAgent:
    """要求文を構造化するエージェント"""

    async def translate(
        self,
        input_data: TranslateRequestInput,
    ) -> TranslateRequestOutput:
        """
        自然言語の旅行リクエストを構造化

        Args:
            input_data: 翻訳入力（生テキスト、プロフィール情報）

        Returns:
            構造化された制約・希望
        """
        # プロフィールコンテキストの構築
        profile_context = ""
        if input_data.user_profile_summary:
            profile_context = (
                f"\nユーザーのプロフィール：\n{input_data.user_profile_summary}\n"
            )
        if input_data.preference_signals:
            signals_text = "\n".join(
                f"- {s.get('category')}: {s.get('tag')} (重み: {s.get('weight', 1.0)})"
                for s in input_data.preference_signals
            )
            profile_context += f"\nユーザーの嗜好シグナル：\n{signals_text}\n"

        prompt = TRANSLATE_PROMPT.format(
            raw_request=input_data.raw_request,
            profile_context=profile_context,
        )

        # LLM呼び出し（リトライあり）
        response = await self._call_llm_with_retry(prompt)

        # JSONパース
        parsed = self._parse_response(response)

        return TranslateRequestOutput(
            constraints=TravelConstraints(**parsed.get("constraints", {})),
            wishes=TravelWishes(**parsed.get("wishes", {})),
            clarification_needed=parsed.get("clarification_needed", []),
        )

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
                    tier=ModelTier.LIGHT,
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.3,
                    agent_name="translator",
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Translator LLM call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                # リトライ時にプロンプト補強
                if attempt < max_retries - 1:
                    prompt = prompt + "\n\n必ず有効なJSON形式で出力してください。"

        raise RuntimeError(
            f"Translator failed after {max_retries} attempts: {last_error}"
        )

    def _parse_response(self, response: str) -> dict:
        """LLMレスポンスからJSONをパース"""
        # JSONブロックを抽出
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if json_match:
            json_str = json_match.group(1)
        else:
            # コードブロックがない場合、全体をJSONとして扱う
            json_str = response.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse translator response: {e}")
            logger.debug(f"Raw response: {response}")
            # 空のデフォルト値を返す
            return {
                "constraints": {},
                "wishes": {},
                "clarification_needed": ["リクエストの解析に失敗しました"],
            }


# Singleton instance
translator_agent = TranslatorAgent()
