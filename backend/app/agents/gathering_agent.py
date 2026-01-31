"""旅行情報収集エージェント

対話を通じてユーザーから旅行企画に必要な情報を収集する。
"""

import json
import logging
from typing import AsyncGenerator

from app.schemas.travel_planning import CollectedTravelInfo
from app.services.llm_gateway import llm_gateway, ModelTier

logger = logging.getLogger(__name__)

# 情報収集のためのシステムプロンプト
GATHERING_SYSTEM_PROMPT = """あなたは旅行プランナーのアシスタントです。
ユーザーから旅行に関する詳細情報を収集するために会話を行います。

## あなたの役割
1. ユーザーの旅行に関する希望や制約を聞き出す
2. 自然な会話を心がけ、一度に多くを聞きすぎない
3. ユーザーの回答から情報を正確に抽出する

## 収集すべき情報（優先度順）
1. 予算（総額または一人あたり）
2. 食の好み（和食、洋食、名物料理など）
3. やりたいこと・体験したいこと（観光、体験、アクティビティ）
4. 宿泊の希望（旅館、ホテル、民宿など）
5. 移動手段の希望（レンタカー、公共交通機関など）
6. 旅のペース（ゆっくり、普通、アクティブ）
7. 必ず行きたい場所（あれば）
8. 避けたいもの（あれば）

## 会話のルール
- 1回の返答で聞く質問は1-2つまで
- ユーザーの回答を要約してから次の質問に移る
- 強制しない、「もしあれば」「特になければ」などの表現を使う
- 十分な情報が集まったら「準備ができました」と伝える

## 出力形式
以下のJSON形式で回答してください：
```json
{
  "response": "ユーザーへの返答テキスト",
  "extracted_info": {
    "budget": null または 数値,
    "budget_per_person": null または 数値,
    "transportation": null または "レンタカー" など,
    "accommodation_type": null または "旅館" など,
    "food_preferences": ["和食", "地元の名物"] など,
    "activity_preferences": ["観光", "温泉"] など,
    "must_visit": ["金閣寺"] など,
    "avoid": ["混雑した場所"] など,
    "pace": null または "ゆっくり" / "普通" / "アクティブ",
    "special_requests": null または 特別なリクエスト
  },
  "is_ready": true/false (十分な情報が集まったか)
}
```
"""

INFO_EXTRACTION_PROMPT = """以下の会話履歴から、旅行に関する情報を抽出してください。

## 基本情報
- 観光エリア: {area}
- 日程: {start_date} 〜 {end_date}
- 人数: {num_people}人

## 会話履歴
{conversation_history}

## 現在の収集済み情報
{current_info}

## 最新のユーザーメッセージ
{user_message}

上記から、以下の形式で情報を抽出してください。
必ず有効なJSONのみを出力してください。

```json
{{
  "response": "ユーザーへの返答（次の質問を含む）",
  "extracted_info": {{
    "budget": null または 数値（例: 50000）,
    "budget_per_person": null または 数値,
    "transportation": null または "文字列",
    "accommodation_type": null または "文字列",
    "food_preferences": [],
    "activity_preferences": [],
    "must_visit": [],
    "avoid": [],
    "pace": null または "ゆっくり"/"普通"/"アクティブ",
    "special_requests": null または "文字列"
  }},
  "is_ready": false
}}
```

重要：
- 既存の情報と新しい情報をマージする
- 不明な項目はnullまたは空配列のまま
- is_ready は予算と少なくとも1つの希望が分かった場合にtrue
"""

GREETING_TEMPLATE = """ありがとうございます！

**{area}** への **{days}日間** の旅行ですね。
{num_people}人でのご旅行、素敵ですね！

より良いプランを作るために、いくつか教えてください。

まず、今回の旅行の**予算**はどのくらいをお考えですか？
（例：総額で5万円くらい、一人3万円くらい、など。特に決まっていなければ「特になし」でOKです）"""


class GatheringAgent:
    """旅行情報収集エージェント"""

    def get_initial_greeting(self, basic_info: CollectedTravelInfo) -> str:
        """初回の挨拶メッセージを生成"""
        from datetime import datetime

        start = datetime.strptime(basic_info.start_date, "%Y-%m-%d")
        end = datetime.strptime(basic_info.end_date, "%Y-%m-%d")
        days = (end - start).days + 1

        return GREETING_TEMPLATE.format(
            area=basic_info.area,
            days=days,
            num_people=basic_info.num_people,
        )

    async def process_message(
        self,
        user_message: str,
        current_info: CollectedTravelInfo,
        conversation_history: list[dict],
    ) -> tuple[str, CollectedTravelInfo, bool, list[str]]:
        """
        ユーザーメッセージを処理し、情報を抽出

        Returns:
            tuple: (response, updated_info, is_ready, missing_info)
        """
        # 会話履歴を文字列に変換
        history_str = "\n".join(
            f"{'ユーザー' if msg['role'] == 'user' else 'アシスタント'}: {msg['content']}"
            for msg in conversation_history[-6:]  # 直近3ターン
        )

        # 現在の情報をJSON化
        current_info_dict = current_info.model_dump(exclude_none=True)

        prompt = INFO_EXTRACTION_PROMPT.format(
            area=current_info.area,
            start_date=current_info.start_date,
            end_date=current_info.end_date,
            num_people=current_info.num_people,
            conversation_history=history_str,
            current_info=json.dumps(current_info_dict, ensure_ascii=False, indent=2),
            user_message=user_message,
        )

        try:
            response = await llm_gateway.generate(
                prompt=prompt,
                tier=ModelTier.LIGHT,
                system_prompt=GATHERING_SYSTEM_PROMPT,
                agent_name="gathering_agent",
            )

            # JSONを抽出してパース
            result = self._parse_response(response)

            # 情報を更新
            updated_info = self._merge_info(current_info, result.get("extracted_info", {}))

            # 不足情報を判定
            missing_info = self._get_missing_info(updated_info)

            # is_ready の判定
            is_ready = result.get("is_ready", False) or len(missing_info) <= 2

            return (
                result.get("response", "情報をありがとうございます。"),
                updated_info,
                is_ready,
                missing_info,
            )

        except Exception as e:
            logger.error(f"Gathering agent error: {e}")
            return (
                "ありがとうございます。他にご希望はありますか？",
                current_info,
                False,
                self._get_missing_info(current_info),
            )

    async def process_message_stream(
        self,
        user_message: str,
        current_info: CollectedTravelInfo,
        conversation_history: list[dict],
    ) -> AsyncGenerator[tuple[str, CollectedTravelInfo | None, bool | None, list[str] | None], None]:
        """
        ストリーミングでユーザーメッセージを処理

        Yields:
            tuple: (chunk, updated_info, is_ready, missing_info)
            - chunkのみの場合: (chunk, None, None, None)
            - 最終結果: ("", updated_info, is_ready, missing_info)
        """
        # 会話履歴を文字列に変換
        history_str = "\n".join(
            f"{'ユーザー' if msg['role'] == 'user' else 'アシスタント'}: {msg['content']}"
            for msg in conversation_history[-6:]
        )

        current_info_dict = current_info.model_dump(exclude_none=True)

        # ストリーミング用のシンプルなプロンプト（JSON形式は使わない）
        stream_system_prompt = f"""あなたは旅行プランナーのアシスタントです。
ユーザーから旅行に関する詳細情報を収集するために会話を行います。

## 旅行の基本情報
- 観光エリア: {current_info.area}
- 日程: {current_info.start_date} 〜 {current_info.end_date}
- 人数: {current_info.num_people}人

## 既に収集した情報
{json.dumps(current_info_dict, ensure_ascii=False, indent=2)}

## 会話履歴
{history_str}

## あなたの役割
1. ユーザーの回答を確認し、要約する
2. まだ聞いていない情報について質問する
3. 十分な情報が集まったら「準備ができました」と伝える

## 収集すべき情報（優先度順）
- 予算（総額または一人あたり）
- 食の好み
- やりたいこと・体験したいこと
- 宿泊の希望
- 移動手段の希望
- 旅のペース

## ルール
- 1回の返答で聞く質問は1-2つまで
- 自然な会話を心がける
- プレーンテキストで返答（JSON不要）"""

        full_response = ""

        try:
            async for chunk in llm_gateway.generate_stream(
                prompt=user_message,
                tier=ModelTier.LIGHT,
                system_prompt=stream_system_prompt,
                agent_name="gathering_agent",
            ):
                full_response += chunk
                yield (chunk, None, None, None)

            # ストリーミング完了後、別途情報抽出を行う
            updated_info = await self._extract_info_from_conversation(
                user_message=user_message,
                assistant_response=full_response,
                current_info=current_info,
            )
            missing_info = self._get_missing_info(updated_info)
            is_ready = len(missing_info) <= 2

            # 最終結果を送信
            yield ("", updated_info, is_ready, missing_info)

        except Exception as e:
            logger.error(f"Gathering agent stream error: {e}")
            yield ("", current_info, False, self._get_missing_info(current_info))

    async def _extract_info_from_conversation(
        self,
        user_message: str,
        assistant_response: str,
        current_info: CollectedTravelInfo,
    ) -> CollectedTravelInfo:
        """会話から情報を抽出（非ストリーミング）"""
        extraction_prompt = f"""以下の会話から旅行に関する情報を抽出してJSON形式で返してください。

## ユーザーのメッセージ
{user_message}

## アシスタントの返答
{assistant_response}

## 既存の情報
{json.dumps(current_info.model_dump(exclude_none=True), ensure_ascii=False)}

## 出力形式（JSON のみ）
{{
  "budget": null または 数値,
  "budget_per_person": null または 数値,
  "transportation": null または "文字列",
  "accommodation_type": null または "文字列",
  "food_preferences": [],
  "activity_preferences": [],
  "must_visit": [],
  "avoid": [],
  "pace": null または "ゆっくり"/"普通"/"アクティブ",
  "special_requests": null または "文字列"
}}

既存情報に追加・更新がある項目のみ値を設定してください。"""

        try:
            response = await llm_gateway.generate(
                prompt=extraction_prompt,
                tier=ModelTier.LIGHT,
                agent_name="gathering_agent",
            )

            # JSONを抽出
            extracted = self._parse_json_only(response)
            return self._merge_info(current_info, extracted)

        except Exception as e:
            logger.warning(f"Info extraction failed: {e}")
            return current_info

    def _parse_json_only(self, response: str) -> dict:
        """レスポンスからJSONのみを抽出"""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            elif "{" in response:
                # JSON部分を探す
                start = response.index("{")
                end = response.rindex("}") + 1
                json_str = response[start:end]
            else:
                return {}

            return json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return {}

    def _parse_response(self, response: str) -> dict:
        """LLMレスポンスからJSONを抽出してパース"""
        try:
            # JSON部分を抽出
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                # 全体がJSONかもしれない
                json_str = response.strip()

            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"Failed to parse gathering response: {e}")
            # フォールバック: responseテキストだけ返す
            return {"response": response, "extracted_info": {}, "is_ready": False}

    def _merge_info(
        self, current: CollectedTravelInfo, extracted: dict
    ) -> CollectedTravelInfo:
        """現在の情報と抽出された情報をマージ"""
        data = current.model_dump()

        for key, value in extracted.items():
            if value is None:
                continue
            if isinstance(value, list):
                # リストはマージ（重複除去）
                existing = data.get(key, [])
                if existing is None:
                    existing = []
                merged = list(set(existing + value))
                data[key] = merged
            else:
                # スカラーは上書き
                data[key] = value

        return CollectedTravelInfo(**data)

    def _get_missing_info(self, info: CollectedTravelInfo) -> list[str]:
        """不足している情報のリストを返す"""
        missing = []

        if info.budget is None and info.budget_per_person is None:
            missing.append("予算")
        if not info.food_preferences:
            missing.append("食の好み")
        if not info.activity_preferences:
            missing.append("やりたいこと")
        if info.accommodation_type is None:
            missing.append("宿泊の希望")
        if info.transportation is None:
            missing.append("移動手段")
        if info.pace is None:
            missing.append("旅のペース")

        return missing


# シングルトンインスタンス
gathering_agent = GatheringAgent()
