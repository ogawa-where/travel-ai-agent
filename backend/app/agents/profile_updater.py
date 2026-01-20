"""
Profile Updater Agent

CLAUDE.md セクション4.2, 5.2に基づく長期記憶更新エージェント。
- プロフィール要約の更新
- 嗜好シグナルの統合・重複排除
- HEAVYティアモデルを使用（複雑な推論・統合が必要）

更新タイミング:
- 嗜好学習モードの完了時
- 旅行企画後の明示的フィードバック時
"""

import logging
from typing import Any

from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """あなたはユーザープロフィールの専門家です。
旅行の嗜好に関する情報を整理・統合し、簡潔で有用なプロフィールを作成します。

プロフィール作成の原則:
1. 重要な嗜好を優先して残す（確信度が高いもの）
2. 矛盾する情報は最新のものを優先
3. 冗長な情報は統合する
4. 簡潔さを保つ（肥大化させない）
"""

PROFILE_CONSOLIDATION_PROMPT = """以下の情報を統合し、ユーザーの旅行嗜好プロフィールを作成してください。

## 現在のプロフィール要約
{current_summary}

## 現在の嗜好シグナル一覧
{signals_text}

## セッション中に得られた新しい情報
{session_summary}

以下の形式で出力してください:
{{
  "profile_summary": "統合されたプロフィール要約（200文字以内）",
  "consolidated_signals": [
    {{
      "category": "likes" | "dislikes" | "experience_axis" | "constraints",
      "tag": "嗜好タグ",
      "weight": 0.0〜1.0,
      "evidence": "根拠"
    }}
  ],
  "removed_signals": ["削除した重複/矛盾シグナルのタグ名"]
}}

統合のルール:
1. 同じカテゴリ・タグの重複は1つに統合（重みは平均化）
2. 矛盾するシグナル（likes vs dislikes）は最新を優先
3. 重みが0.3未満のシグナルは削除検討
4. 最大20個程度に抑える（優先度順）
"""

FEEDBACK_INTEGRATION_PROMPT = """旅行プランへのフィードバックから嗜好を更新してください。

## 現在のプロフィール
{current_summary}

## 現在の嗜好シグナル
{signals_text}

## 生成されたプラン
{plan_summary}

## ユーザーのフィードバック
{feedback}

以下の形式で出力してください:
{{
  "updated_signals": [
    {{
      "category": "likes" | "dislikes" | "experience_axis" | "constraints",
      "tag": "嗜好タグ",
      "weight": 0.0〜1.0,
      "evidence": "フィードバックからの根拠",
      "action": "add" | "update" | "remove"
    }}
  ],
  "profile_update": "プロフィール要約への追記（なければ空文字）"
}}
"""


class ProfileUpdaterAgent:
    """プロフィール更新エージェント（長期記憶）"""

    async def consolidate_profile(
        self,
        current_summary: str,
        signals: list[dict[str, Any]],
        session_summary: str,
    ) -> dict[str, Any]:
        """
        プロフィールと嗜好シグナルを統合・整理

        Args:
            current_summary: 現在のプロフィール要約
            signals: 現在の嗜好シグナル一覧
            session_summary: セッション中に得られた情報の要約

        Returns:
            統合結果（profile_summary, consolidated_signals, removed_signals）
        """
        # Format signals for prompt
        signals_text = self._format_signals(signals)

        prompt = PROFILE_CONSOLIDATION_PROMPT.format(
            current_summary=current_summary or "まだプロフィール情報がありません。",
            signals_text=signals_text or "なし",
            session_summary=session_summary or "追加情報なし",
        )

        try:
            result = await llm_gateway.generate_json(
                prompt=prompt,
                tier=ModelTier.HEAVY,  # 複雑な統合タスクはHEAVYモデル
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
            )

            # Validate and clean result
            return self._validate_consolidation_result(result)

        except Exception as e:
            logger.error(f"Profile consolidation failed: {e}")
            # Return unchanged data on failure
            return {
                "profile_summary": current_summary,
                "consolidated_signals": signals,
                "removed_signals": [],
            }

    async def integrate_feedback(
        self,
        current_summary: str,
        signals: list[dict[str, Any]],
        plan_summary: str,
        feedback: str,
    ) -> dict[str, Any]:
        """
        旅行プランへのフィードバックを嗜好に反映

        Args:
            current_summary: 現在のプロフィール要約
            signals: 現在の嗜好シグナル一覧
            plan_summary: 生成されたプランの概要
            feedback: ユーザーのフィードバック

        Returns:
            更新情報（updated_signals, profile_update）
        """
        signals_text = self._format_signals(signals)

        prompt = FEEDBACK_INTEGRATION_PROMPT.format(
            current_summary=current_summary or "まだプロフィール情報がありません。",
            signals_text=signals_text or "なし",
            plan_summary=plan_summary,
            feedback=feedback,
        )

        try:
            result = await llm_gateway.generate_json(
                prompt=prompt,
                tier=ModelTier.HEAVY,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,
            )

            return self._validate_feedback_result(result)

        except Exception as e:
            logger.error(f"Feedback integration failed: {e}")
            return {
                "updated_signals": [],
                "profile_update": "",
            }

    def _format_signals(self, signals: list[dict[str, Any]]) -> str:
        """嗜好シグナルをテキスト形式にフォーマット"""
        if not signals:
            return ""

        lines = []
        for s in signals:
            line = f"- [{s.get('category', '')}] {s.get('tag', '')} "
            line += f"(weight: {s.get('weight', 0.5):.2f})"
            if s.get('evidence'):
                line += f" - {s.get('evidence', '')[:50]}"
            lines.append(line)

        return "\n".join(lines)

    def _validate_consolidation_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """統合結果のバリデーション"""
        validated = {
            "profile_summary": str(result.get("profile_summary", ""))[:500],
            "consolidated_signals": [],
            "removed_signals": list(result.get("removed_signals", [])),
        }

        for signal in result.get("consolidated_signals", []):
            try:
                validated["consolidated_signals"].append({
                    "category": str(signal.get("category", "likes")),
                    "tag": str(signal.get("tag", ""))[:100],
                    "weight": min(1.0, max(0.0, float(signal.get("weight", 0.5)))),
                    "evidence": str(signal.get("evidence", ""))[:200],
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid signal in consolidation: {signal}, error: {e}")
                continue

        return validated

    def _validate_feedback_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """フィードバック統合結果のバリデーション"""
        validated = {
            "updated_signals": [],
            "profile_update": str(result.get("profile_update", ""))[:200],
        }

        for signal in result.get("updated_signals", []):
            try:
                validated["updated_signals"].append({
                    "category": str(signal.get("category", "likes")),
                    "tag": str(signal.get("tag", ""))[:100],
                    "weight": min(1.0, max(0.0, float(signal.get("weight", 0.5)))),
                    "evidence": str(signal.get("evidence", ""))[:200],
                    "action": signal.get("action", "add"),
                })
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid signal in feedback: {signal}, error: {e}")
                continue

        return validated


# Singleton instance
profile_updater = ProfileUpdaterAgent()
