"""
PreferenceLearner & ProfileUpdater Agent Tests

CLAUDE.md セクション3.1, 4.2, 5.2の要件:
- PreferenceLearner: チャット形式で嗜好を学習
- ProfileUpdater: 長期記憶（プロフィール/嗜好シグナル）更新
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

from app.agents.preference_learner import PreferenceLearnerAgent, preference_learner
from app.agents.profile_updater import ProfileUpdaterAgent, profile_updater


# =============================================================================
# PreferenceLearnerAgent Tests
# =============================================================================

class TestPreferenceLearnerQuestionGeneration:
    """質問生成のテスト"""

    @pytest.mark.asyncio
    async def test_generate_question_no_history(self):
        """履歴なしでの質問生成"""
        agent = PreferenceLearnerAgent()

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="どんな旅行スタイルがお好みですか？"
            )
            result = await agent.generate_question(
                profile_summary="",
                known_signals=[],
                conversation_history=[],
            )

        assert len(result) > 0
        assert "?" in result or "？" in result

    @pytest.mark.asyncio
    async def test_generate_question_with_signals(self):
        """既存シグナルありでの質問生成"""
        agent = PreferenceLearnerAgent()
        signals = [
            {"category": "likes", "tag": "温泉", "weight": 0.8},
            {"category": "dislikes", "tag": "混雑", "weight": 0.7},
        ]

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="食事の好みはありますか？"
            )
            await agent.generate_question(
                profile_summary="温泉好きのユーザー",
                known_signals=signals,
                conversation_history=[],
            )

            # プロンプトにシグナルが含まれることを確認
            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "温泉" in prompt
            assert "混雑" in prompt

    @pytest.mark.asyncio
    async def test_generate_question_with_history(self):
        """会話履歴ありでの質問生成"""
        agent = PreferenceLearnerAgent()
        history = [
            {"role": "assistant", "content": "どこに行きたいですか？"},
            {"role": "user", "content": "京都がいいですね"},
            {"role": "assistant", "content": "京都ですね。"},
            {"role": "user", "content": "神社が好きです"},
        ]

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="宿泊の希望はありますか？"
            )
            await agent.generate_question(
                profile_summary="",
                known_signals=[],
                conversation_history=history,
            )

            # プロンプトに会話履歴が含まれることを確認
            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "京都" in prompt
            assert "神社" in prompt

    @pytest.mark.asyncio
    async def test_history_limited_to_6_messages(self):
        """履歴は直近6メッセージに制限"""
        agent = PreferenceLearnerAgent()
        # 10メッセージの履歴
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"メッセージ{i}"}
            for i in range(10)
        ]

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value="質問")
            await agent.generate_question(
                profile_summary="",
                known_signals=[],
                conversation_history=history,
            )

            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            # 最初の4メッセージは含まれない
            assert "メッセージ0" not in prompt
            assert "メッセージ3" not in prompt
            # 最後の6メッセージは含まれる
            assert "メッセージ9" in prompt


class TestPreferenceLearnerSignalExtraction:
    """シグナル抽出のテスト"""

    @pytest.mark.asyncio
    async def test_extract_signals_success(self):
        """シグナル抽出成功"""
        agent = PreferenceLearnerAgent()

        mock_response = {
            "signals": [
                {
                    "category": "likes",
                    "tag": "温泉",
                    "weight": 0.9,
                    "evidence": "温泉が好きと言った",
                }
            ],
            "response": "温泉がお好きなんですね！",
        }

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.extract_signals(
                user_message="温泉が大好きです",
                context="旅行の好みについて聞いている",
            )

        assert len(result["signals"]) == 1
        assert result["signals"][0]["category"] == "likes"
        assert result["signals"][0]["tag"] == "温泉"
        assert 0.0 <= result["signals"][0]["weight"] <= 1.0

    @pytest.mark.asyncio
    async def test_extract_signals_invalid_category(self):
        """無効なカテゴリはスキップ"""
        agent = PreferenceLearnerAgent()

        mock_response = {
            "signals": [
                {
                    "category": "invalid_category",
                    "tag": "テスト",
                    "weight": 0.5,
                    "evidence": "テスト",
                },
                {
                    "category": "likes",
                    "tag": "温泉",
                    "weight": 0.8,
                    "evidence": "温泉好き",
                },
            ],
            "response": "承知しました",
        }

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.extract_signals("テスト", "テスト")

        # 無効なカテゴリのシグナルはスキップされる
        assert len(result["signals"]) == 1
        assert result["signals"][0]["tag"] == "温泉"

    @pytest.mark.asyncio
    async def test_extract_signals_weight_clamped(self):
        """weightは0-1にクランプされる"""
        agent = PreferenceLearnerAgent()

        mock_response = {
            "signals": [
                {"category": "likes", "tag": "A", "weight": 1.5, "evidence": ""},
                {"category": "likes", "tag": "B", "weight": -0.5, "evidence": ""},
            ],
            "response": "",
        }

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.extract_signals("テスト", "テスト")

        assert result["signals"][0]["weight"] == 1.0  # 1.5 -> 1.0
        assert result["signals"][1]["weight"] == 0.0  # -0.5 -> 0.0

    @pytest.mark.asyncio
    async def test_extract_signals_failure(self):
        """シグナル抽出失敗時は空結果"""
        agent = PreferenceLearnerAgent()

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(
                side_effect=Exception("API Error")
            )
            result = await agent.extract_signals("テスト", "テスト")

        assert result["signals"] == []
        assert result["response"] == ""


class TestPreferenceLearnerProfileUpdate:
    """プロフィール更新のテスト"""

    @pytest.mark.asyncio
    async def test_update_profile_with_signals(self):
        """シグナルありでプロフィール更新"""
        agent = PreferenceLearnerAgent()
        signals = [
            {"category": "likes", "tag": "温泉", "evidence": "好きと言った"},
        ]

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="温泉が好きなユーザー"
            )
            result = await agent.update_profile_summary(
                current_summary="",
                new_signals=signals,
            )

        assert "温泉" in result

    @pytest.mark.asyncio
    async def test_update_profile_empty_signals(self):
        """シグナルなしではプロフィールは変更されない"""
        agent = PreferenceLearnerAgent()
        current = "既存のプロフィール"

        result = await agent.update_profile_summary(
            current_summary=current,
            new_signals=[],
        )

        assert result == current


class TestPreferenceLearnerInitialGreeting:
    """初回挨拶のテスト"""

    @pytest.mark.asyncio
    async def test_initial_greeting(self):
        """初回挨拶メッセージ生成"""
        agent = PreferenceLearnerAgent()

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="こんにちは！旅行の好みを教えてください。"
            )
            result = await agent.get_initial_greeting()

        assert len(result) > 0


# =============================================================================
# ProfileUpdaterAgent Tests
# =============================================================================

class TestProfileUpdaterConsolidation:
    """プロフィール統合のテスト"""

    @pytest.mark.asyncio
    async def test_consolidate_profile_success(self):
        """プロフィール統合成功"""
        agent = ProfileUpdaterAgent()
        signals = [
            {"category": "likes", "tag": "温泉", "weight": 0.8, "evidence": "好き"},
            {"category": "likes", "tag": "神社", "weight": 0.7, "evidence": "好き"},
        ]

        mock_response = {
            "profile_summary": "温泉と神社が好きなユーザー",
            "consolidated_signals": [
                {"category": "likes", "tag": "温泉", "weight": 0.8, "evidence": "好き"},
                {"category": "likes", "tag": "神社", "weight": 0.7, "evidence": "好き"},
            ],
            "removed_signals": [],
        }

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.consolidate_profile(
                current_summary="",
                signals=signals,
                session_summary="温泉と神社が好きと判明",
            )

        assert "温泉" in result["profile_summary"]
        assert len(result["consolidated_signals"]) == 2

    @pytest.mark.asyncio
    async def test_consolidate_profile_removes_duplicates(self):
        """重複シグナルの削除"""
        agent = ProfileUpdaterAgent()
        signals = [
            {"category": "likes", "tag": "温泉", "weight": 0.8, "evidence": "1回目"},
            {"category": "likes", "tag": "温泉", "weight": 0.9, "evidence": "2回目"},
        ]

        mock_response = {
            "profile_summary": "温泉好き",
            "consolidated_signals": [
                {"category": "likes", "tag": "温泉", "weight": 0.85, "evidence": "統合"},
            ],
            "removed_signals": ["温泉（重複）"],
        }

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.consolidate_profile(
                current_summary="",
                signals=signals,
                session_summary="",
            )

        # 統合後は1つになる
        assert len(result["consolidated_signals"]) == 1

    @pytest.mark.asyncio
    async def test_consolidate_profile_failure_returns_original(self):
        """統合失敗時は元のデータを返す"""
        agent = ProfileUpdaterAgent()
        original_summary = "元のプロフィール"
        original_signals = [{"category": "likes", "tag": "温泉", "weight": 0.8}]

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(
                side_effect=Exception("API Error")
            )
            result = await agent.consolidate_profile(
                current_summary=original_summary,
                signals=original_signals,
                session_summary="",
            )

        assert result["profile_summary"] == original_summary
        assert result["consolidated_signals"] == original_signals


class TestProfileUpdaterFeedbackIntegration:
    """フィードバック統合のテスト"""

    @pytest.mark.asyncio
    async def test_integrate_feedback_success(self):
        """フィードバック統合成功"""
        agent = ProfileUpdaterAgent()

        mock_response = {
            "updated_signals": [
                {
                    "category": "likes",
                    "tag": "静かな場所",
                    "weight": 0.9,
                    "evidence": "フィードバック",
                    "action": "add",
                }
            ],
            "profile_update": "静かな場所を好む傾向",
        }

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.integrate_feedback(
                current_summary="",
                signals=[],
                plan_summary="にぎやかな観光地を含むプラン",
                feedback="もう少し静かな場所がよかった",
            )

        assert len(result["updated_signals"]) == 1
        assert result["updated_signals"][0]["action"] == "add"
        assert "静かな場所" in result["profile_update"]

    @pytest.mark.asyncio
    async def test_integrate_feedback_failure(self):
        """フィードバック統合失敗時は空結果"""
        agent = ProfileUpdaterAgent()

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(
                side_effect=Exception("API Error")
            )
            result = await agent.integrate_feedback(
                current_summary="",
                signals=[],
                plan_summary="プラン",
                feedback="フィードバック",
            )

        assert result["updated_signals"] == []
        assert result["profile_update"] == ""


class TestProfileUpdaterFormatting:
    """フォーマット関数のテスト"""

    def test_format_signals_empty(self):
        """空のシグナルリスト"""
        agent = ProfileUpdaterAgent()
        result = agent._format_signals([])
        assert result == ""

    def test_format_signals_with_evidence(self):
        """根拠付きシグナル"""
        agent = ProfileUpdaterAgent()
        signals = [
            {"category": "likes", "tag": "温泉", "weight": 0.8, "evidence": "好きと言った"},
        ]
        result = agent._format_signals(signals)
        assert "[likes]" in result
        assert "温泉" in result
        assert "0.80" in result
        assert "好きと言った" in result

    def test_format_signals_evidence_truncated(self):
        """長い根拠は切り詰められる"""
        agent = ProfileUpdaterAgent()
        long_evidence = "A" * 100
        signals = [
            {"category": "likes", "tag": "テスト", "weight": 0.5, "evidence": long_evidence},
        ]
        result = agent._format_signals(signals)
        # 50文字で切り詰め
        assert len(result.split(" - ")[-1]) <= 50


class TestProfileUpdaterValidation:
    """バリデーション関数のテスト"""

    def test_validate_consolidation_result(self):
        """統合結果のバリデーション"""
        agent = ProfileUpdaterAgent()
        result = {
            "profile_summary": "A" * 600,  # 長すぎる
            "consolidated_signals": [
                {"category": "likes", "tag": "A" * 200, "weight": 1.5, "evidence": ""},
            ],
            "removed_signals": ["test"],
        }
        validated = agent._validate_consolidation_result(result)

        # profile_summaryは500文字に切り詰め
        assert len(validated["profile_summary"]) == 500
        # tagは100文字に切り詰め
        assert len(validated["consolidated_signals"][0]["tag"]) == 100
        # weightは1.0にクランプ
        assert validated["consolidated_signals"][0]["weight"] == 1.0

    def test_validate_feedback_result(self):
        """フィードバック結果のバリデーション"""
        agent = ProfileUpdaterAgent()
        result = {
            "updated_signals": [
                {"category": "likes", "tag": "温泉", "weight": 0.8, "evidence": "", "action": "add"},
            ],
            "profile_update": "A" * 300,  # 長すぎる
        }
        validated = agent._validate_feedback_result(result)

        # profile_updateは200文字に切り詰め
        assert len(validated["profile_update"]) == 200
        assert len(validated["updated_signals"]) == 1


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingletons:
    """シングルトンのテスト"""

    def test_preference_learner_singleton(self):
        """PreferenceLearnerシングルトン"""
        assert preference_learner is not None
        assert isinstance(preference_learner, PreferenceLearnerAgent)

    def test_profile_updater_singleton(self):
        """ProfileUpdaterシングルトン"""
        assert profile_updater is not None
        assert isinstance(profile_updater, ProfileUpdaterAgent)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """エッジケースのテスト"""

    @pytest.mark.asyncio
    async def test_preference_learner_empty_profile(self):
        """空のプロフィールでの質問生成"""
        agent = PreferenceLearnerAgent()

        with patch("app.agents.preference_learner.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value="質問")
            await agent.generate_question(
                profile_summary="",
                known_signals=[],
                conversation_history=[],
            )

            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "まだ情報がありません" in prompt

    @pytest.mark.asyncio
    async def test_profile_updater_empty_signals(self):
        """空のシグナルでの統合"""
        agent = ProfileUpdaterAgent()

        mock_response = {
            "profile_summary": "情報なし",
            "consolidated_signals": [],
            "removed_signals": [],
        }

        with patch("app.agents.profile_updater.llm_gateway") as mock_gateway:
            mock_gateway.generate_json = AsyncMock(return_value=mock_response)
            result = await agent.consolidate_profile(
                current_summary="",
                signals=[],
                session_summary="",
            )

        assert result["consolidated_signals"] == []

    def test_format_signals_missing_fields(self):
        """フィールドが欠けているシグナル"""
        agent = ProfileUpdaterAgent()
        signals = [
            {"category": "likes"},  # tagとweightがない
            {"tag": "温泉"},  # categoryとweightがない
        ]
        result = agent._format_signals(signals)
        # エラーにならずにフォーマットされる
        assert "[likes]" in result or "温泉" in result
