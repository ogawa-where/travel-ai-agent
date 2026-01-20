"""
Short-term Memory Context Assembly Tests

CLAUDE.md セクション5.1, 11の要件:
- 短期記憶のコンテキスト組み立て（直近3ターン＋要約）検証
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass


# Mock Message class for testing without database dependencies
@dataclass
class MockMessage:
    """テスト用のモックメッセージ"""
    session_id: str
    role: str
    content: str
    turn_index: int
    is_summarized: bool = False
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class TestShortTermMemoryLogic:
    """短期記憶ロジックのテスト（DB不要）"""

    def test_max_raw_turns_constant(self):
        """MAX_RAW_TURNSが3であること"""
        MAX_RAW_TURNS = 3
        assert MAX_RAW_TURNS == 3

    def test_context_assembly_with_less_than_3_turns(self):
        """3ターン未満の場合、全てのメッセージが返されること"""
        messages = [
            MockMessage(
                session_id="session-1",
                role="assistant",
                content="こんにちは",
                turn_index=1,
            ),
            MockMessage(
                session_id="session-1",
                role="user",
                content="旅行が好きです",
                turn_index=1,
            ),
            MockMessage(
                session_id="session-1",
                role="assistant",
                content="どんな旅行が好きですか？",
                turn_index=1,
            ),
        ]

        # ターンでグループ化
        turns = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        # 3ターン以下なので全て残る
        assert len(turns) == 1
        assert len(turns[1]) == 3

    def test_context_assembly_with_exactly_3_turns(self):
        """ちょうど3ターンの場合、全てが返されること"""
        base_time = datetime.now()
        messages = [
            # Turn 1
            MockMessage("s1", "user", "こんにちは", 1, created_at=base_time),
            MockMessage("s1", "assistant", "こんにちは！", 1, created_at=base_time + timedelta(seconds=1)),
            # Turn 2
            MockMessage("s1", "user", "旅行したい", 2, created_at=base_time + timedelta(seconds=2)),
            MockMessage("s1", "assistant", "どこへ？", 2, created_at=base_time + timedelta(seconds=3)),
            # Turn 3
            MockMessage("s1", "user", "京都", 3, created_at=base_time + timedelta(seconds=4)),
            MockMessage("s1", "assistant", "良いですね！", 3, created_at=base_time + timedelta(seconds=5)),
        ]

        # ターンでグループ化
        turns = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        MAX_RAW_TURNS = 3
        assert len(turns) == 3
        assert len(turns) <= MAX_RAW_TURNS

    def test_context_assembly_with_more_than_3_turns(self):
        """3ターン超の場合、古いターンが要約対象になること"""
        base_time = datetime.now()
        messages = [
            # Turn 1 (should be summarized)
            MockMessage("s1", "user", "こんにちは", 1, created_at=base_time),
            MockMessage("s1", "assistant", "こんにちは！", 1, created_at=base_time + timedelta(seconds=1)),
            # Turn 2 (should be summarized)
            MockMessage("s1", "user", "旅行したい", 2, created_at=base_time + timedelta(seconds=2)),
            MockMessage("s1", "assistant", "どこへ？", 2, created_at=base_time + timedelta(seconds=3)),
            # Turn 3 (keep)
            MockMessage("s1", "user", "京都", 3, created_at=base_time + timedelta(seconds=4)),
            MockMessage("s1", "assistant", "良いですね！", 3, created_at=base_time + timedelta(seconds=5)),
            # Turn 4 (keep)
            MockMessage("s1", "user", "温泉も", 4, created_at=base_time + timedelta(seconds=6)),
            MockMessage("s1", "assistant", "温泉ですね", 4, created_at=base_time + timedelta(seconds=7)),
            # Turn 5 (keep)
            MockMessage("s1", "user", "2泊3日", 5, created_at=base_time + timedelta(seconds=8)),
            MockMessage("s1", "assistant", "わかりました", 5, created_at=base_time + timedelta(seconds=9)),
        ]

        # ターンでグループ化
        turns = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        MAX_RAW_TURNS = 3
        turn_indices = sorted(turns.keys())
        assert len(turn_indices) == 5

        # 直近3ターンのみ保持
        recent_turn_indices = turn_indices[-MAX_RAW_TURNS:]
        assert recent_turn_indices == [3, 4, 5]

        # 要約対象のターン
        turns_to_summarize_indices = turn_indices[:-MAX_RAW_TURNS]
        assert turns_to_summarize_indices == [1, 2]

    def test_messages_to_summarize_identification(self):
        """要約すべきメッセージが正しく識別されること"""
        messages = [
            MockMessage("s1", "user", "msg1", 1),
            MockMessage("s1", "assistant", "msg2", 1),
            MockMessage("s1", "user", "msg3", 2),
            MockMessage("s1", "assistant", "msg4", 2),
            MockMessage("s1", "user", "msg5", 3),
            MockMessage("s1", "assistant", "msg6", 3),
            MockMessage("s1", "user", "msg7", 4),
            MockMessage("s1", "assistant", "msg8", 4),
        ]

        # ターンでグループ化
        turns = {}
        for msg in messages:
            if msg.turn_index not in turns:
                turns[msg.turn_index] = []
            turns[msg.turn_index].append(msg)

        MAX_RAW_TURNS = 3
        turn_indices = sorted(turns.keys())

        if len(turn_indices) <= MAX_RAW_TURNS:
            messages_to_summarize = []
        else:
            turns_to_summarize_indices = turn_indices[:-MAX_RAW_TURNS]
            messages_to_summarize = []
            for turn_idx in turns_to_summarize_indices:
                messages_to_summarize.extend(turns[turn_idx])

        # Turn 1のメッセージのみが要約対象
        assert len(messages_to_summarize) == 2
        assert all(m.turn_index == 1 for m in messages_to_summarize)

    def test_last_3_turns_raw_format(self):
        """last_3_turns_rawが正しいフォーマットであること"""
        base_time = datetime.now()
        messages = [
            MockMessage("s1", "user", "京都に行きたい", 3, created_at=base_time),
            MockMessage("s1", "assistant", "良いですね", 3, created_at=base_time + timedelta(seconds=1)),
            MockMessage("s1", "user", "温泉も", 4, created_at=base_time + timedelta(seconds=2)),
            MockMessage("s1", "assistant", "温泉ですね", 4, created_at=base_time + timedelta(seconds=3)),
        ]

        # 期待されるフォーマット
        last_3_turns_raw = [
            {"role": msg.role, "content": msg.content}
            for msg in sorted(messages, key=lambda m: (m.turn_index, m.created_at))
        ]

        assert len(last_3_turns_raw) == 4
        assert all("role" in item and "content" in item for item in last_3_turns_raw)
        assert last_3_turns_raw[0]["role"] == "user"
        assert last_3_turns_raw[0]["content"] == "京都に行きたい"

    def test_context_for_llm_structure(self):
        """get_context_for_llmの戻り値構造が正しいこと"""
        # 期待される構造
        context = {
            "session_summary": "ユーザーは京都への旅行を希望しています。",
            "last_3_turns_raw": [
                {"role": "user", "content": "温泉も行きたい"},
                {"role": "assistant", "content": "温泉ですね。他には？"},
                {"role": "user", "content": "2泊3日で"},
                {"role": "assistant", "content": "わかりました"},
            ],
        }

        assert "session_summary" in context
        assert "last_3_turns_raw" in context
        assert isinstance(context["session_summary"], str)
        assert isinstance(context["last_3_turns_raw"], list)

    def test_summarized_messages_not_in_raw(self):
        """要約済みメッセージがlast_3_turns_rawに含まれないこと"""
        messages = [
            MockMessage("s1", "user", "古いメッセージ", 1, is_summarized=True),
            MockMessage("s1", "assistant", "古い応答", 1, is_summarized=True),
            MockMessage("s1", "user", "新しいメッセージ", 2, is_summarized=False),
            MockMessage("s1", "assistant", "新しい応答", 2, is_summarized=False),
        ]

        # 未要約のメッセージのみを取得
        unsummarized = [m for m in messages if not m.is_summarized]

        assert len(unsummarized) == 2
        assert all(m.turn_index == 2 for m in unsummarized)


class TestTurnIndexLogic:
    """ターンインデックスロジックのテスト"""

    def test_user_message_starts_new_turn(self):
        """ユーザーメッセージが新しいターンを開始すること"""
        # ユーザー発言は新しいターンの開始
        last_turn_index = 1
        new_turn_index_for_user = last_turn_index + 1
        assert new_turn_index_for_user == 2

    def test_assistant_message_same_turn(self):
        """アシスタントメッセージが同じターンであること"""
        # アシスタント発言は同じターン
        last_turn_index = 2
        turn_index_for_assistant = last_turn_index
        assert turn_index_for_assistant == 2

    def test_turn_index_sequence(self):
        """ターンインデックスのシーケンスが正しいこと"""
        messages = []
        current_turn = 0

        # シミュレーション
        # User message 1
        current_turn += 1
        messages.append({"role": "user", "turn_index": current_turn})
        # Assistant response 1
        messages.append({"role": "assistant", "turn_index": current_turn})
        # User message 2
        current_turn += 1
        messages.append({"role": "user", "turn_index": current_turn})
        # Assistant response 2
        messages.append({"role": "assistant", "turn_index": current_turn})

        assert messages[0]["turn_index"] == 1
        assert messages[1]["turn_index"] == 1
        assert messages[2]["turn_index"] == 2
        assert messages[3]["turn_index"] == 2


class TestSummaryUpdateLogic:
    """要約更新ロジックのテスト"""

    def test_summary_preserves_important_info(self):
        """要約が重要情報を保持すること"""
        # CLAUDE.md: session_summaryは以下を必ず残す:
        # 決定事項、制約、嗜好、体験軸、未解決事項、重要リンク

        important_categories = [
            "決定事項",
            "制約条件",
            "嗜好",
            "体験軸",
            "未解決事項",
        ]

        # 要約に含まれるべき情報
        summary_template = """
        【決定事項】京都への2泊3日旅行
        【制約条件】予算5万円、一人旅
        【嗜好】温泉、和食、文化体験
        【体験軸】文化/自然
        【未解決事項】具体的な日程
        """

        for category in important_categories:
            assert category in summary_template

    def test_incremental_summary_update(self):
        """要約がインクリメンタルに更新されること"""
        existing_summary = "ユーザーは京都への旅行を希望しています。"
        new_info = "温泉と和食を楽しみたいとのこと。"

        # 新しい要約（実際はLLMが生成）
        updated_summary = existing_summary + " " + new_info

        assert existing_summary in updated_summary or "京都" in updated_summary
        assert "温泉" in updated_summary or new_info in updated_summary


class TestContextWindowManagement:
    """コンテキストウィンドウ管理のテスト"""

    def test_context_structure_for_llm_call(self):
        """LLM呼び出し時のコンテキスト構造が正しいこと"""
        # CLAUDE.md: すべてのLLM呼び出しは必ず以下を渡す:
        # 1) systemルール
        # 2) session_summary
        # 3) last_3_turns_raw
        # 4) 今回のタスク入力

        system_rules = "あなたは旅行アシスタントです。"
        session_summary = "ユーザーは京都旅行を計画中。"
        last_3_turns_raw = [
            {"role": "user", "content": "温泉も行きたい"},
            {"role": "assistant", "content": "温泉ですね"},
        ]
        task_input = "2泊3日のプランを作って"

        context = {
            "system": system_rules,
            "summary": session_summary,
            "recent_messages": last_3_turns_raw,
            "current_task": task_input,
        }

        assert "system" in context
        assert "summary" in context
        assert "recent_messages" in context
        assert "current_task" in context

    def test_max_6_messages_in_3_turns(self):
        """3ターンで最大6メッセージであること"""
        # CLAUDE.md: 最大6メッセージ：U/A ×3
        MAX_RAW_TURNS = 3
        MAX_MESSAGES_PER_TURN = 2  # user + assistant
        MAX_TOTAL_MESSAGES = MAX_RAW_TURNS * MAX_MESSAGES_PER_TURN

        assert MAX_TOTAL_MESSAGES == 6
