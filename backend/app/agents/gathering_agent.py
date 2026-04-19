"""旅行情報収集エージェント

対話を通じてユーザーから旅行企画に必要な情報を収集する。
"""

import json
import logging
from typing import AsyncGenerator

from app.schemas.travel_planning import CollectedTravelInfo, RequiredInfoStatus
from app.services.llm_gateway import llm_gateway, ModelTier

logger = logging.getLogger(__name__)

# 情報収集のためのシステムプロンプト
GATHERING_SYSTEM_PROMPT = """あなたは旅行プランナーのアシスタントです。
ユーザーから旅行に関する詳細情報を収集するために会話を行います。

## あなたの役割
1. ユーザーの旅行に関する希望や制約を聞き出す
2. 自然な会話を心がけ、一度に多くを聞きすぎない
3. ユーザーの回答から情報を正確に抽出する

## 【必須】最優先で確認する情報
以下の3つは必ず確認してください：
1. **予算**（総額または一人あたり）
2. **やりたいこと**（観光、体験、アクティビティなど最低1つ）
3. **移動手段**（レンタカー、公共交通機関など）

## 【任意】必須情報が揃った後に確認する情報
- 食の好み（和食、洋食、名物料理など）
- 宿泊の希望（旅館、ホテル、民宿など）
- 旅のペース（ゆっくり、普通、アクティブ）
- 必ず行きたい場所（あれば）
- 避けたいもの（あれば）

## 会話のルール
- **まず必須情報（予算、やりたいこと、移動手段）を確認する**
- 1回の返答で聞く質問は1-2つまで
- ユーザーの回答を要約してから次の質問に移る
- 必須情報が3つ揃ったら「基本的な情報が揃いました！」と伝える
- 任意情報は「もしあれば」「特になければ」などの表現を使う

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
  }
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
  }}
}}
```

重要：
- 既存の情報と新しい情報をマージする
- 不明な項目はnullまたは空配列のまま
"""

GREETING_TEMPLATE = """ありがとうございます！

**{area}** への **{days}日間** の旅行ですね。
{num_people}人でのご旅行{budget_text}、素敵ですね！

より良いプランを作るために、いくつか教えてください。

まず、{area}で**どんなことをしたい**ですか？
（例：温泉に入りたい、景色を見たい、美術館に行きたい、など）"""


class GatheringAgent:
    """旅行情報収集エージェント"""

    def get_initial_greeting(self, basic_info: CollectedTravelInfo) -> str:
        """初回の挨拶メッセージを生成"""
        from datetime import datetime

        start = datetime.strptime(basic_info.start_date, "%Y-%m-%d")
        end = datetime.strptime(basic_info.end_date, "%Y-%m-%d")
        days = (end - start).days + 1

        # 予算の表示テキスト
        if basic_info.budget:
            budget_text = f"、予算{basic_info.budget:,}円"
        else:
            budget_text = ""

        return GREETING_TEMPLATE.format(
            area=basic_info.area,
            days=days,
            num_people=basic_info.num_people,
            budget_text=budget_text,
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

        # 4カテゴリの収集状況をフォーマット
        # 1. 体験・観光（activity）
        # 2. 食（food）
        # 3. 宿（hotel）
        # 4. 交通（transportation）
        collected_items = []
        not_collected_items = []

        # 予算（フォームで入力済み）
        if current_info.budget:
            collected_items.append(f"- 予算: {current_info.budget:,}円（フォームで入力済み）")

        # 1. 体験・観光
        if current_info.activity_preferences:
            collected_items.append(f"- やりたいこと: {', '.join(current_info.activity_preferences)}")
        else:
            not_collected_items.append("- やりたいこと・体験したいこと（観光、アクティビティなど）")

        # 2. 食
        if current_info.food_preferences:
            collected_items.append(f"- 食の好み: {', '.join(current_info.food_preferences)}")
        else:
            not_collected_items.append("- 食の好み（和食、洋食、地元の名物など）")

        # 3. 宿
        if current_info.accommodation_type:
            collected_items.append(f"- 宿泊の希望: {current_info.accommodation_type}")
        else:
            not_collected_items.append("- 宿泊の希望（旅館、ホテル、民宿など）")

        # 4. 交通
        if current_info.transportation:
            collected_items.append(f"- 移動手段: {current_info.transportation}")
        else:
            not_collected_items.append("- 移動手段（レンタカー、公共交通機関など）")

        # その他の収集済み情報
        if current_info.must_visit:
            collected_items.append(f"- 行きたい場所: {', '.join(current_info.must_visit)}")
        if current_info.avoid:
            collected_items.append(f"- 避けたいこと: {', '.join(current_info.avoid)}")
        if current_info.pace:
            collected_items.append(f"- 旅のペース: {current_info.pace}")

        collected_str = "\n".join(collected_items) if collected_items else "（まだ何も収集していません）"
        not_collected_str = "\n".join(not_collected_items) if not_collected_items else "（全て収集済み）"

        # 4カテゴリのうちいくつ揃っているか
        category_count = sum([
            bool(current_info.activity_preferences),
            bool(current_info.food_preferences),
            bool(current_info.accommodation_type),
            bool(current_info.transportation),
        ])

        # ストリーミング用のプロンプト
        stream_system_prompt = f"""あなたは旅行プランナーのアシスタントです。
ユーザーから旅行に関する詳細情報を収集するために会話を行います。

## 旅行の基本情報（フォームで入力済み）
- 観光エリア: {current_info.area}
- 日程: {current_info.start_date} 〜 {current_info.end_date}
- 人数: {current_info.num_people}人
- 予算: {f'{current_info.budget:,}円' if current_info.budget else '未設定'}

## ★既に収集済みの情報（絶対にこれらについて再度質問しないでください）
{collected_str}

## まだ聞いていない情報（これらについて質問してください）
{not_collected_str}

## 会話履歴
{history_str}

## 収集すべき4カテゴリ
1. やりたいこと（体験・観光）
2. 食の好み
3. 宿泊の希望
4. 移動手段

現在 {category_count}/4 カテゴリ収集済み

## 重要なルール
1. **絶対に同じことを2回聞かない** - 上記「収集済みの情報」にあるものは質問しない
2. **予算は既にフォームで入力済みなので聞かない**
3. ユーザーの回答を短く確認してから、次の質問に移る
4. 1回の返答で聞く質問は1つだけ
5. 自然な会話を心がける
6. **4カテゴリのうち2つ以上揃ったら**「これで旅行プランを作成する準備ができました！他にご希望があればお聞かせください。」と伝える

## 出力形式
プレーンテキストで返答してください（JSON不要）"""

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

            # is_ready の判定:
            # 1. AIが「準備ができました」と言った場合
            # 2. または、4カテゴリのうち2つ以上揃った場合
            ready_phrases = ["準備ができました", "準備が整いました", "プランを作成する準備"]
            ai_said_ready = any(phrase in full_response for phrase in ready_phrases)

            # 4カテゴリのうちいくつ揃っているか
            category_count = sum([
                bool(updated_info.activity_preferences),
                bool(updated_info.food_preferences),
                bool(updated_info.accommodation_type),
                bool(updated_info.transportation),
            ])
            has_enough_info = category_count >= 2

            is_ready = ai_said_ready or has_enough_info

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
        extraction_prompt = f"""以下のユーザーメッセージから旅行に関する新しい情報を抽出してJSON形式で返してください。

## ユーザーのメッセージ
「{user_message}」

## 既存の収集済み情報（これらは既に収集済みなので変更しないでください）
- 予算: {current_info.budget or current_info.budget_per_person or '未収集'}
- やりたいこと: {', '.join(current_info.activity_preferences) if current_info.activity_preferences else '未収集'}
- 移動手段: {current_info.transportation or '未収集'}
- 食の好み: {', '.join(current_info.food_preferences) if current_info.food_preferences else '未収集'}
- 宿泊タイプ: {current_info.accommodation_type or '未収集'}
- ペース: {current_info.pace or '未収集'}

## 抽出ルール
1. ユーザーのメッセージから**新しく判明した情報のみ**を抽出する
2. 金額は数値に変換する（例: 「5万円」→ 50000）
3. 複数の項目が含まれる場合は配列にする
4. 関係ない情報や不明な項目はnullまたは空配列のまま

## 出力形式（JSONのみ、説明文なし）
{{
  "budget": null,
  "budget_per_person": null,
  "transportation": null,
  "accommodation_type": null,
  "food_preferences": [],
  "activity_preferences": [],
  "must_visit": [],
  "avoid": [],
  "pace": null,
  "special_requests": null
}}"""

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

    def _check_required_info(self, info: CollectedTravelInfo) -> RequiredInfoStatus:
        """4カテゴリの収集状況をチェック"""
        return RequiredInfoStatus(
            has_activities=(len(info.activity_preferences) >= 1),
            has_food=(len(info.food_preferences) >= 1),
            has_accommodation=(info.accommodation_type is not None),
            has_transportation=(info.transportation is not None),
        )

    def _get_missing_required_info(self, info: CollectedTravelInfo) -> list[str]:
        """不足している4カテゴリ情報のリスト"""
        missing = []
        if not info.activity_preferences:
            missing.append("やりたいこと")
        if not info.food_preferences:
            missing.append("食の好み")
        if info.accommodation_type is None:
            missing.append("宿泊の希望")
        if info.transportation is None:
            missing.append("移動手段")
        return missing

    def _get_missing_optional_info(self, info: CollectedTravelInfo) -> list[str]:
        """不足している任意情報のリスト"""
        missing = []
        if info.pace is None:
            missing.append("旅のペース")
        # must_visit, avoid, special_requests は積極的に聞かない
        return missing

    def _get_missing_info(self, info: CollectedTravelInfo) -> list[str]:
        """不足している情報のリストを返す（互換性のため維持）"""
        return self._get_missing_required_info(info) + self._get_missing_optional_info(info)


# シングルトンインスタンス
gathering_agent = GatheringAgent()
