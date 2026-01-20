"""
Translator & Summarizer Agent Tests

CLAUDE.md セクション4.2の要件:
- Translator Agent: 要求文 → 制約/嗜好JSON
- Summarizer Agent: 短期要約（session_summary）更新
"""

import pytest
from unittest.mock import AsyncMock, patch
import json

from app.agents.translator import TranslatorAgent, translator_agent
from app.agents.summarizer import SummarizerAgent, summarizer_agent
from app.schemas.travel_planning import (
    TranslateRequestInput,
    TranslateRequestOutput,
    TravelConstraints,
    TravelWishes,
)
from app.domain.models import Message


# =============================================================================
# TranslatorAgent Tests
# =============================================================================

class TestTranslatorPromptBuilding:
    """Translatorのプロンプト構築テスト"""

    @pytest.mark.asyncio
    async def test_translate_basic_request(self):
        """基本的なリクエストの変換"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(
            raw_request="来月、京都に2泊3日で一人旅したい",
        )

        mock_response = json.dumps({
            "constraints": {
                "destination": "京都",
                "duration_days": 3,
                "num_people": 1,
            },
            "wishes": {
                "activities": [],
            },
            "clarification_needed": [],
        })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            result = await agent.translate(input_data)

        assert result.constraints.destination == "京都"
        assert result.constraints.duration_days == 3
        assert result.constraints.num_people == 1

    @pytest.mark.asyncio
    async def test_translate_with_profile(self):
        """プロフィール付きリクエストの変換"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(
            raw_request="温泉旅行がしたい",
            user_profile_summary="温泉好きな40代男性",
            preference_signals=[
                {"category": "likes", "tag": "温泉", "weight": 0.9},
            ],
        )

        mock_response = json.dumps({
            "constraints": {},
            "wishes": {
                "activities": ["温泉"],
            },
            "clarification_needed": ["どの地域に行きたいですか？"],
        })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            result = await agent.translate(input_data)

            # プロンプトにプロフィール情報が含まれることを確認
            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "温泉好きな40代男性" in prompt

        assert "温泉" in result.wishes.activities
        assert len(result.clarification_needed) > 0


class TestTranslatorResponseParsing:
    """レスポンスパースのテスト"""

    def test_parse_valid_json(self):
        """有効なJSONのパース"""
        agent = TranslatorAgent()
        response = json.dumps({
            "constraints": {"destination": "京都"},
            "wishes": {"activities": ["神社巡り"]},
            "clarification_needed": [],
        })
        parsed = agent._parse_response(response)
        assert parsed["constraints"]["destination"] == "京都"

    def test_parse_json_in_code_block(self):
        """コードブロック内のJSONのパース"""
        agent = TranslatorAgent()
        response = """```json
{
  "constraints": {"destination": "東京"},
  "wishes": {},
  "clarification_needed": []
}
```"""
        parsed = agent._parse_response(response)
        assert parsed["constraints"]["destination"] == "東京"

    def test_parse_invalid_json(self):
        """無効なJSONのパース"""
        agent = TranslatorAgent()
        response = "This is not valid JSON"
        parsed = agent._parse_response(response)
        assert "constraints" in parsed
        assert "clarification_needed" in parsed
        assert "リクエストの解析に失敗しました" in parsed["clarification_needed"]


class TestTranslatorLLMIntegration:
    """LLM統合テスト"""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """失敗時のリトライ"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(raw_request="京都旅行")

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API Error")
            return json.dumps({
                "constraints": {"destination": "京都"},
                "wishes": {},
                "clarification_needed": [],
            })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = mock_generate
            result = await agent.translate(input_data)

        assert call_count == 3
        assert result.constraints.destination == "京都"

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """最大リトライ回数超過"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(raw_request="京都旅行")

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(side_effect=Exception("API Error"))

            with pytest.raises(RuntimeError) as exc_info:
                await agent.translate(input_data)

        assert "3 attempts" in str(exc_info.value)


class TestTranslatorOutputValidation:
    """出力バリデーションのテスト"""

    @pytest.mark.asyncio
    async def test_output_has_correct_types(self):
        """出力が正しい型を持つ"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(raw_request="京都に行きたい")

        mock_response = json.dumps({
            "constraints": {
                "destination": "京都",
                "budget_total": 50000,
                "num_people": 2,
            },
            "wishes": {
                "activities": ["神社巡り", "温泉"],
                "food_preferences": ["和食"],
                "priority": "文化体験",
            },
            "clarification_needed": ["日程は？"],
        })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            result = await agent.translate(input_data)

        assert isinstance(result, TranslateRequestOutput)
        assert isinstance(result.constraints, TravelConstraints)
        assert isinstance(result.wishes, TravelWishes)
        assert isinstance(result.clarification_needed, list)


# =============================================================================
# SummarizerAgent Tests
# =============================================================================

class TestSummarizerAgent:
    """Summarizerエージェントのテスト"""

    @pytest.mark.asyncio
    async def test_summarize_empty_messages(self):
        """空のメッセージリスト"""
        agent = SummarizerAgent()
        result = await agent.summarize_messages("existing summary", [])
        assert result == "existing summary"

    @pytest.mark.asyncio
    async def test_summarize_new_messages(self):
        """新しいメッセージの要約"""
        agent = SummarizerAgent()
        messages = [
            Message(
                id="1",
                session_id="sess1",
                role="user",
                content="温泉が好きです",
                turn_index=1,
            ),
            Message(
                id="2",
                session_id="sess1",
                role="assistant",
                content="温泉がお好きなんですね",
                turn_index=1,
            ),
        ]

        with patch("app.agents.summarizer.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="ユーザーは温泉が好き。"
            )
            result = await agent.summarize_messages("", messages)

        assert "温泉" in result

    @pytest.mark.asyncio
    async def test_summarize_with_existing_summary(self):
        """既存の要約との統合"""
        agent = SummarizerAgent()
        existing = "ユーザーは自然が好き。"
        messages = [
            Message(
                id="1",
                session_id="sess1",
                role="user",
                content="和食も好きです",
                turn_index=2,
            ),
        ]

        with patch("app.agents.summarizer.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(
                return_value="ユーザーは自然と和食が好き。"
            )
            result = await agent.summarize_messages(existing, messages)

            # プロンプトに既存の要約が含まれることを確認
            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]
            assert "ユーザーは自然が好き" in prompt

        assert result == "ユーザーは自然と和食が好き。"

    @pytest.mark.asyncio
    async def test_messages_sorted_by_turn(self):
        """メッセージがターン順にソートされる"""
        agent = SummarizerAgent()
        # 順序がバラバラのメッセージ
        messages = [
            Message(
                id="3",
                session_id="sess1",
                role="assistant",
                content="最後のメッセージ",
                turn_index=3,
            ),
            Message(
                id="1",
                session_id="sess1",
                role="user",
                content="最初のメッセージ",
                turn_index=1,
            ),
            Message(
                id="2",
                session_id="sess1",
                role="user",
                content="2番目のメッセージ",
                turn_index=2,
            ),
        ]

        with patch("app.agents.summarizer.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value="要約")
            await agent.summarize_messages("", messages)

            # プロンプトを確認
            call_args = mock_gateway.generate.call_args
            prompt = call_args.kwargs.get("prompt") or call_args.args[0]

            # 最初のメッセージが先に来ることを確認
            first_pos = prompt.find("最初のメッセージ")
            last_pos = prompt.find("最後のメッセージ")
            assert first_pos < last_pos


# =============================================================================
# Singleton Tests
# =============================================================================

class TestSingletons:
    """シングルトンのテスト"""

    def test_translator_singleton(self):
        """Translatorシングルトン"""
        assert translator_agent is not None
        assert isinstance(translator_agent, TranslatorAgent)

    def test_summarizer_singleton(self):
        """Summarizerシングルトン"""
        assert summarizer_agent is not None
        assert isinstance(summarizer_agent, SummarizerAgent)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """エッジケースのテスト"""

    @pytest.mark.asyncio
    async def test_translator_empty_request(self):
        """空のリクエスト"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(raw_request="")

        mock_response = json.dumps({
            "constraints": {},
            "wishes": {},
            "clarification_needed": ["旅行先を教えてください"],
        })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            result = await agent.translate(input_data)

        assert len(result.clarification_needed) > 0

    @pytest.mark.asyncio
    async def test_translator_complex_request(self):
        """複雑なリクエスト"""
        agent = TranslatorAgent()
        input_data = TranslateRequestInput(
            raw_request="来月15日から3泊4日で、予算10万円以内で、京都と奈良を巡りたい。神社仏閣が好きで、和食も楽しみたい。できれば温泉旅館に泊まりたい。",
        )

        mock_response = json.dumps({
            "constraints": {
                "destination": "京都・奈良",
                "duration_days": 4,
                "budget_total": 100000,
                "accommodation_type": "温泉旅館",
            },
            "wishes": {
                "activities": ["神社巡り", "寺院巡り"],
                "food_preferences": ["和食"],
            },
            "clarification_needed": [],
        })

        with patch("app.agents.translator.llm_gateway") as mock_gateway:
            mock_gateway.generate = AsyncMock(return_value=mock_response)
            result = await agent.translate(input_data)

        assert result.constraints.duration_days == 4
        assert result.constraints.budget_total == 100000
        assert "神社巡り" in result.wishes.activities

    def test_summarizer_prompt_format(self):
        """要約プロンプトのフォーマット確認"""
        # SummarizerAgentのプロンプトが正しくフォーマットされることを確認
        from app.agents.summarizer import SUMMARIZE_PROMPT

        formatted = SUMMARIZE_PROMPT.format(
            existing_summary="既存の要約",
            new_messages="user: こんにちは",
        )
        assert "既存の要約" in formatted
        assert "user: こんにちは" in formatted
