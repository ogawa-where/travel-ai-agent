"""
Summarizer Agent

CLAUDE.md セクション5.1の要約更新ルールを実装:
- session_summaryは以下を必ず残す:
  - 決定事項、制約、嗜好、体験軸、未解決事項、重要リンク（最小限）
"""

import logging

from app.domain.models import Message
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたは会話要約の専門家です。
旅行の嗜好学習に関する会話を要約し、重要な情報を保持します。

要約に必ず含めるべき情報:
1. 決定事項（ユーザーが明確に述べた好み）
2. 制約条件（予算、日程、体力的制限など）
3. 嗜好（好きなもの、嫌いなもの）
4. 体験軸の傾向（文化/自然/学び/参加型/ウェルネスなど）
5. 未解決事項（まだ確認していないこと）

要約は簡潔に、箇条書きではなく文章で記述してください。
"""

SUMMARIZE_PROMPT = """以下の会話履歴を要約してください。

既存の要約:
{existing_summary}

新しく追加する会話:
{new_messages}

上記の情報を統合し、更新された要約を出力してください。
要約文のみを出力してください。
"""


class SummarizerAgent:
    """会話要約エージェント"""

    async def summarize_messages(
        self,
        existing_summary: str,
        messages: list[Message],
    ) -> str:
        """
        メッセージを要約に統合

        Args:
            existing_summary: 既存の要約
            messages: 新しく要約するメッセージ

        Returns:
            更新された要約
        """
        if not messages:
            return existing_summary

        # メッセージを文字列化
        messages_text = "\n".join(
            f"{msg.role}: {msg.content}"
            for msg in sorted(messages, key=lambda m: (m.turn_index, m.created_at))
        )

        prompt = SUMMARIZE_PROMPT.format(
            existing_summary=existing_summary or "なし（初回の要約）",
            new_messages=messages_text,
        )

        response = await llm_gateway.generate(
            prompt=prompt,
            tier=ModelTier.LIGHT,  # 要約は軽量モデルで十分
            system_prompt=SYSTEM_PROMPT,
            temperature=0.3,  # 低めの温度で一貫性を保つ
        )

        return response.strip()


# Singleton instance
summarizer_agent = SummarizerAgent()
