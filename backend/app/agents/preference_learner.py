import logging
from typing import Any

from app.schemas.preference import PreferenceCategory
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは旅行の嗜好を学習するアシスタントです。
ユーザーの旅行に関する好み、興味、傾向を理解するために質問を行います。

目標:
1. ユーザーの好きなもの・興味を把握する（likes）
   例: 和食が好き、歴史に興味がある、静かな場所が好き、自然が好き
2. ユーザーの嫌いなもの・避けたいものを把握する（dislikes）
   例: 混雑が苦手、辛いものNG、長時間歩くのは苦手
3. 旅行の傾向を把握する（tendency）
   例: 計画派か即興派か、ゆっくり派かアクティブ派か、朝型か夜型か

注意:
- 「予算3万円」「2泊3日」などの具体的な制約は扱わない（それは旅行企画モードで扱う）
- 「体験」の種類（座禅体験、陶芸体験など）は抽出しない。好みを元に旅行企画モードで体験を提案する
- 抽出するのは「好み」であり、「体験」ではない
  - ○ 「歴史に興味がある」（好み） → 旅行企画で寺社仏閣体験を提案
  - × 「文化体験が好き」（体験カテゴリ）

ルール:
- 一度に1つの質問をする
- 親しみやすく自然な会話を心がける
- ユーザーの回答から嗜好を推測し、確認する
- 日本語で回答する
"""

QUESTION_GENERATION_PROMPT = """以下のユーザープロフィールと会話履歴を踏まえて、
次に聞くべき質問を1つ生成してください。

現在のプロフィール:
{profile_summary}

既知の嗜好シグナル:
{known_signals}

会話履歴:
{conversation_history}

まだ把握していない重要な嗜好を聞き出す質問を生成してください。
質問文のみを出力してください。
"""

SIGNAL_EXTRACTION_PROMPT = """以下のユーザーの回答から、旅行の嗜好シグナルを抽出してJSON形式で出力してください。

ユーザーの回答: {user_message}

質問の文脈: {context}

既存の嗜好タグ（重複を避けること）:
{existing_tags}

カテゴリの説明:
- likes: 好きなもの・興味があるもの（食事、場所のタイプ、興味分野など）
- dislikes: 嫌いなもの・避けたいもの
- tendency: 旅行の傾向・スタイル

タグの形式（重要）:
- タグは単語または短いフレーズのみ。「〇〇が好き」「〇〇に興味がある」などの接尾辞は付けない
- 良い例: 歴史, 和食, 静かな場所, 自然, 山, 海, 計画派, ゆっくり派
- 悪い例: 歴史が好き, 和食に興味がある, 静かな場所が好き

重要な注意:
- 既存の嗜好タグと同じまたは類似のタグは抽出しない（重複回避）
- 「予算3万円」「2泊3日」などの具体的な数値制約は抽出しない
- 「体験」カテゴリ（文化体験、自然体験など）は抽出しない。具体的な好みを抽出する
  - × 文化体験 → ○ 歴史, 伝統工芸, 寺社仏閣
  - × 自然体験 → ○ 自然, 山, 海, 森

以下のJSON形式で出力してください:
{{
  "signals": [
    {{
      "category": "likes" | "dislikes" | "tendency",
      "tag": "単語または短いフレーズ（例: 歴史, 和食, 静かな場所, 計画派）",
      "weight": 0.0〜1.0の数値（確信度）,
      "evidence": "ユーザーの発言からの根拠"
    }}
  ],
  "response": "ユーザーへの返答（嗜好を確認・深掘りする内容）"
}}

シグナルが抽出できない場合は空の配列を返してください。
"""

PROFILE_UPDATE_PROMPT = """以下の新しい嗜好シグナルを踏まえて、ユーザープロフィールの要約文を更新してください。

現在のプロフィール要約:
{current_summary}

新しい嗜好シグナル:
{new_signals}

更新後のプロフィール要約文のみを出力してください。
簡潔に、箇条書きではなく文章で記述してください。
"""


class PreferenceLearnerAgent:
    """嗜好学習エージェント"""

    async def generate_question(
        self,
        profile_summary: str,
        known_signals: list[dict[str, Any]],
        conversation_history: list[dict[str, str]],
    ) -> str:
        """次の質問を生成"""
        signals_text = (
            "\n".join(
                f"- {s['category']}: {s['tag']} (weight: {s['weight']})"
                for s in known_signals
            )
            or "なし"
        )

        history_text = (
            "\n".join(
                f"{m['role']}: {m['content']}"
                for m in conversation_history[-6:]  # 直近3ターン
            )
            or "なし"
        )

        prompt = QUESTION_GENERATION_PROMPT.format(
            profile_summary=profile_summary or "まだ情報がありません",
            known_signals=signals_text,
            conversation_history=history_text,
        )

        response = await llm_gateway.generate(
            prompt=prompt,
            tier=ModelTier.LIGHT,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            agent_name="preference_learner",
        )
        return response.strip()

    async def extract_signals(
        self,
        user_message: str,
        context: str,
        existing_signals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """ユーザーの回答から嗜好シグナルを抽出

        Args:
            user_message: ユーザーの回答
            context: 質問の文脈
            existing_signals: 既存の嗜好シグナル（重複回避用）
        """
        existing_tags = "なし"
        if existing_signals:
            tags = [s.get("tag", "") for s in existing_signals if s.get("tag")]
            if tags:
                existing_tags = ", ".join(tags)

        prompt = SIGNAL_EXTRACTION_PROMPT.format(
            user_message=user_message,
            context=context,
            existing_tags=existing_tags,
        )

        try:
            result = await llm_gateway.generate_json(
                prompt=prompt,
                tier=ModelTier.LIGHT,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
                agent_name="preference_learner",
            )
            # Validate signals
            validated_signals = []
            for signal in result.get("signals", []):
                try:
                    category = PreferenceCategory(signal.get("category", ""))
                    validated_signals.append(
                        {
                            "category": category.value,
                            "tag": str(signal.get("tag", ""))[:100],
                            "weight": min(
                                1.0, max(0.0, float(signal.get("weight", 0.5)))
                            ),
                            "evidence": str(signal.get("evidence", "")),
                        }
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid signal skipped: {signal}, error: {e}")
                    continue

            return {
                "signals": validated_signals,
                "response": result.get("response", ""),
            }
        except Exception as e:
            logger.error(f"Signal extraction failed: {e}")
            return {"signals": [], "response": ""}

    async def update_profile_summary(
        self,
        current_summary: str,
        new_signals: list[dict[str, Any]],
    ) -> str:
        """プロフィール要約を更新"""
        if not new_signals:
            return current_summary

        signals_text = "\n".join(
            f"- {s['category']}: {s['tag']} (根拠: {s['evidence']})"
            for s in new_signals
        )

        prompt = PROFILE_UPDATE_PROMPT.format(
            current_summary=current_summary or "まだプロフィール情報がありません。",
            new_signals=signals_text,
        )

        response = await llm_gateway.generate(
            prompt=prompt,
            tier=ModelTier.LIGHT,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            agent_name="preference_learner",
        )
        return response.strip()

    async def get_initial_greeting(self) -> str:
        """初回挨拶メッセージを生成"""
        prompt = """旅行の嗜好学習を開始するための挨拶と最初の質問を生成してください。
親しみやすく、ユーザーが答えやすい簡単な質問から始めてください。"""

        response = await llm_gateway.generate(
            prompt=prompt,
            tier=ModelTier.LIGHT,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.8,
            agent_name="preference_learner",
        )
        return response.strip()


# Singleton instance
preference_learner = PreferenceLearnerAgent()
