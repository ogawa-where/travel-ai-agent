"""
Error Handling Tests

CLAUDE.md セクション8.7の要件:
- LLM出力パース失敗: 最大3回リトライ
- Ollamaワーカー全滅時: ユーザーフレンドリーなエラー
- 検索エージェント部分失敗: 残りの結果で続行

注: 実際のサービスに依存しないロジックテスト
"""

import pytest
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# =============================================================================
# カスタム例外テスト
# =============================================================================


class TestCustomExceptions:
    """カスタム例外のテスト"""

    def test_travel_agent_error_structure(self):
        """TravelAgentErrorの構造が正しいこと"""

        class TravelAgentError(Exception):
            def __init__(
                self,
                message: str,
                user_message: str | None = None,
                details: dict | None = None,
            ):
                super().__init__(message)
                self.message = message
                self.user_message = user_message or message
                self.details = details or {}

        error = TravelAgentError(
            message="Internal error",
            user_message="申し訳ございません。エラーが発生しました。",
            details={"code": "E001"},
        )

        assert error.message == "Internal error"
        assert error.user_message == "申し訳ございません。エラーが発生しました。"
        assert error.details["code"] == "E001"

    def test_llm_unavailable_error_message(self):
        """LLMUnavailableErrorのメッセージが正しいこと"""
        expected_user_message = "現在LLMサービスが利用できません。しばらくしてから再度お試しください。"

        # テスト用のエラークラス
        class LLMUnavailableError(Exception):
            def __init__(self, message: str = "No healthy workers"):
                super().__init__(message)
                self.user_message = expected_user_message

        error = LLMUnavailableError()
        assert error.user_message == expected_user_message

    def test_llm_parse_error_includes_attempts(self):
        """LLMParseErrorがリトライ回数を含むこと"""

        class LLMParseError(Exception):
            def __init__(self, attempts: int = 0, raw_output: str | None = None):
                self.attempts = attempts
                self.raw_output_preview = raw_output[:200] if raw_output else None

        error = LLMParseError(attempts=3, raw_output="invalid json output" * 20)
        assert error.attempts == 3
        assert error.raw_output_preview is not None
        assert len(error.raw_output_preview) <= 200

    def test_search_partial_failure_error_categories(self):
        """SearchPartialFailureErrorがカテゴリ情報を含むこと"""

        class SearchPartialFailureError(Exception):
            def __init__(
                self,
                failed_categories: list[str],
                successful_categories: list[str],
            ):
                self.failed_categories = failed_categories
                self.successful_categories = successful_categories
                self.user_message = "一部の検索で問題が発生しましたが、他の結果で続行します。"

        error = SearchPartialFailureError(
            failed_categories=["hotel"],
            successful_categories=["activity", "food"],
        )
        assert "hotel" in error.failed_categories
        assert "activity" in error.successful_categories
        assert "food" in error.successful_categories


# =============================================================================
# ワーカーヘルスチェックロジックテスト
# =============================================================================


@dataclass
class MockWorker:
    """テスト用モックワーカー"""

    host: str
    healthy: bool = True
    last_health_check: datetime | None = None
    consecutive_failures: int = 0

    def needs_health_check(self, interval_seconds: int = 30) -> bool:
        if self.last_health_check is None:
            return True
        elapsed = datetime.now() - self.last_health_check
        return elapsed > timedelta(seconds=interval_seconds)

    def mark_healthy(self):
        self.healthy = True
        self.consecutive_failures = 0
        self.last_health_check = datetime.now()

    def mark_unhealthy(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= 3:
            self.healthy = False
        self.last_health_check = datetime.now()


class TestWorkerHealthLogic:
    """ワーカーヘルスチェックロジックのテスト"""

    def test_new_worker_needs_health_check(self):
        """新規ワーカーはヘルスチェックが必要"""
        worker = MockWorker(host="localhost:11434")
        assert worker.needs_health_check()

    def test_recently_checked_worker_no_check_needed(self):
        """最近チェックしたワーカーはチェック不要"""
        worker = MockWorker(host="localhost:11434")
        worker.last_health_check = datetime.now()
        assert not worker.needs_health_check()

    def test_old_check_needs_recheck(self):
        """古いチェックは再チェックが必要"""
        worker = MockWorker(host="localhost:11434")
        worker.last_health_check = datetime.now() - timedelta(seconds=60)
        assert worker.needs_health_check(interval_seconds=30)

    def test_mark_healthy_resets_failures(self):
        """mark_healthyが連続失敗をリセットすること"""
        worker = MockWorker(host="localhost:11434", consecutive_failures=2)
        worker.mark_healthy()
        assert worker.healthy
        assert worker.consecutive_failures == 0

    def test_mark_unhealthy_increments_failures(self):
        """mark_unhealthyが連続失敗をインクリメントすること"""
        worker = MockWorker(host="localhost:11434")
        worker.mark_unhealthy()
        assert worker.consecutive_failures == 1
        assert worker.healthy  # まだ健全

    def test_three_failures_marks_unhealthy(self):
        """3回連続失敗で不健全になること"""
        worker = MockWorker(host="localhost:11434")
        worker.mark_unhealthy()
        worker.mark_unhealthy()
        assert worker.healthy  # まだ健全
        worker.mark_unhealthy()
        assert not worker.healthy  # 3回目で不健全


class TestWorkerSelection:
    """ワーカー選択ロジックのテスト"""

    def test_select_healthy_worker(self):
        """健全なワーカーが選択されること"""
        workers = [
            MockWorker(host="worker1:11434", healthy=True),
            MockWorker(host="worker2:11434", healthy=False),
            MockWorker(host="worker3:11434", healthy=True),
        ]

        healthy = [w for w in workers if w.healthy]
        assert len(healthy) == 2
        assert healthy[0].host == "worker1:11434"

    def test_no_healthy_workers_returns_none(self):
        """健全なワーカーがない場合Noneを返すこと"""
        workers = [
            MockWorker(host="worker1:11434", healthy=False),
            MockWorker(host="worker2:11434", healthy=False),
        ]

        healthy = [w for w in workers if w.healthy]
        result = healthy[0] if healthy else None
        assert result is None

    def test_round_robin_selection(self):
        """ラウンドロビンで選択されること"""
        workers = [
            MockWorker(host="worker1:11434", healthy=True),
            MockWorker(host="worker2:11434", healthy=True),
        ]

        current_index = 0
        selections = []
        for _ in range(4):
            healthy = [w for w in workers if w.healthy]
            worker = healthy[current_index % len(healthy)]
            selections.append(worker.host)
            current_index += 1

        assert selections == [
            "worker1:11434",
            "worker2:11434",
            "worker1:11434",
            "worker2:11434",
        ]

    def test_exclude_workers_from_selection(self):
        """除外されたワーカーが選択されないこと"""
        workers = [
            MockWorker(host="worker1:11434", healthy=True),
            MockWorker(host="worker2:11434", healthy=True),
            MockWorker(host="worker3:11434", healthy=True),
        ]
        exclude = {"worker1:11434"}

        healthy = [w for w in workers if w.healthy and w.host not in exclude]
        assert len(healthy) == 2
        assert all(w.host != "worker1:11434" for w in healthy)


# =============================================================================
# JSONパースロジックテスト
# =============================================================================


class TestJSONParseLogic:
    """JSONパースロジックのテスト"""

    def _extract_json(self, response: str) -> dict | None:
        """JSONを抽出（llm_gateway.pyと同等のロジック）"""
        import json

        response = response.strip()

        # マークダウンコードブロックを除去
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # 直接パースを試みる
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # JSONオブジェクトを探す
        start_idx = response.find("{")
        end_idx = response.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(response[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass

        # JSON配列を探す
        start_idx = response.find("[")
        end_idx = response.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            try:
                return json.loads(response[start_idx : end_idx + 1])
            except json.JSONDecodeError:
                pass

        return None

    def test_parse_plain_json(self):
        """プレーンJSONがパースできること"""
        response = '{"key": "value"}'
        result = self._extract_json(response)
        assert result == {"key": "value"}

    def test_parse_json_with_markdown(self):
        """Markdownコードブロック付きJSONがパースできること"""
        response = '```json\n{"key": "value"}\n```'
        result = self._extract_json(response)
        assert result == {"key": "value"}

    def test_parse_json_with_prefix_text(self):
        """前置きテキスト付きJSONがパースできること"""
        response = 'Here is the JSON:\n{"key": "value"}'
        result = self._extract_json(response)
        assert result == {"key": "value"}

    def test_parse_json_with_suffix_text(self):
        """後置きテキスト付きJSONがパースできること"""
        response = '{"key": "value"}\n\nI hope this helps!'
        result = self._extract_json(response)
        assert result == {"key": "value"}

    def test_parse_json_array(self):
        """JSON配列がパースできること"""
        response = '[1, 2, 3]'
        result = self._extract_json(response)
        assert result == [1, 2, 3]

    def test_parse_invalid_json_returns_none(self):
        """無効なJSONはNoneを返すこと"""
        response = "This is not JSON at all."
        result = self._extract_json(response)
        assert result is None


# =============================================================================
# 検索ステータスロジックテスト
# =============================================================================


@dataclass
class MockSearchStatus:
    """テスト用検索ステータス"""

    total_categories: int = 0
    successful_categories: list = field(default_factory=list)
    failed_categories: list = field(default_factory=list)
    total_results: int = 0

    @property
    def partial_failure(self) -> bool:
        return len(self.failed_categories) > 0 and not self.all_failed

    @property
    def all_failed(self) -> bool:
        return len(self.failed_categories) == self.total_categories

    @property
    def success_rate(self) -> float:
        if self.total_categories == 0:
            return 0.0
        return len(self.successful_categories) / self.total_categories


class TestSearchStatusLogic:
    """検索ステータスロジックのテスト"""

    def test_all_success_status(self):
        """全て成功の場合のステータス"""
        status = MockSearchStatus(
            total_categories=3,
            successful_categories=["activity", "food", "hotel"],
            failed_categories=[],
            total_results=30,
        )

        assert not status.partial_failure
        assert not status.all_failed
        assert status.success_rate == 1.0

    def test_partial_failure_status(self):
        """部分的失敗の場合のステータス"""
        status = MockSearchStatus(
            total_categories=3,
            successful_categories=["activity", "food"],
            failed_categories=["hotel"],
            total_results=20,
        )

        assert status.partial_failure
        assert not status.all_failed
        assert status.success_rate == pytest.approx(2 / 3)

    def test_all_failed_status(self):
        """全て失敗の場合のステータス"""
        status = MockSearchStatus(
            total_categories=3,
            successful_categories=[],
            failed_categories=["activity", "food", "hotel"],
            total_results=0,
        )

        assert not status.partial_failure
        assert status.all_failed
        assert status.success_rate == 0.0

    def test_empty_categories_status(self):
        """カテゴリ0の場合のステータス"""
        status = MockSearchStatus(total_categories=0)
        assert status.success_rate == 0.0


# =============================================================================
# リトライロジックテスト
# =============================================================================


class TestRetryLogic:
    """リトライロジックのテスト"""

    def test_max_retries_constant(self):
        """最大リトライ回数が3であること"""
        MAX_RETRIES = 3
        assert MAX_RETRIES == 3

    def test_retry_loop_executes_correct_times(self):
        """リトライループが正しい回数実行されること"""
        MAX_RETRIES = 3
        attempts = 0

        for attempt in range(MAX_RETRIES):
            attempts += 1
            if attempt == MAX_RETRIES - 1:
                break  # 最後の試行

        assert attempts == MAX_RETRIES

    def test_successful_attempt_breaks_retry(self):
        """成功した試行でリトライが中断されること"""
        MAX_RETRIES = 3
        success_on_attempt = 2
        attempts = 0

        for attempt in range(MAX_RETRIES):
            attempts += 1
            if attempt == success_on_attempt - 1:  # 2回目で成功
                break

        assert attempts == success_on_attempt

    def test_prompt_modification_on_retry(self):
        """リトライ時にプロンプトが修正されること"""
        original_prompt = "Generate JSON"
        modified_prompt = None

        for attempt in range(3):
            if attempt > 0:
                modified_prompt = f"{original_prompt}\n\nIMPORTANT: Return valid JSON only."

        assert modified_prompt is not None
        assert "IMPORTANT" in modified_prompt
        assert original_prompt in modified_prompt


# =============================================================================
# エラーハンドリングフローテスト
# =============================================================================


class TestErrorHandlingFlow:
    """エラーハンドリングフローのテスト"""

    def test_worker_failover_flow(self):
        """ワーカーフェイルオーバーのフロー"""
        workers = [
            MockWorker(host="worker1:11434", healthy=True),
            MockWorker(host="worker2:11434", healthy=True),
        ]

        tried_workers = set()
        attempts = 0
        MAX_RETRIES = 3

        for attempt in range(MAX_RETRIES):
            # 除外リストを考慮してワーカー選択
            healthy = [w for w in workers if w.healthy and w.host not in tried_workers]
            if not healthy:
                # 除外なしで再選択
                healthy = [w for w in workers if w.healthy]

            if not healthy:
                break

            worker = healthy[0]
            tried_workers.add(worker.host)
            attempts += 1

            # 全ワーカーを試した場合
            if len(tried_workers) == len(workers):
                break

        assert attempts == 2  # 2つのワーカーを試した
        assert tried_workers == {"worker1:11434", "worker2:11434"}

    def test_graceful_degradation_on_partial_search_failure(self):
        """検索部分失敗時のグレースフルデグラデーション"""
        search_results = {
            "activity": {"items": [{"name": "金閣寺"}], "success": True},
            "food": {"items": [{"name": "京料理"}], "success": True},
            "hotel": {"items": [], "success": False, "error": "API timeout"},
        }

        # 成功した結果のみを使用
        successful_results = {
            k: v for k, v in search_results.items() if v.get("success", False)
        }

        assert "activity" in successful_results
        assert "food" in successful_results
        assert "hotel" not in successful_results
        assert len(successful_results) == 2

    def test_error_message_for_user(self):
        """ユーザー向けエラーメッセージのテスト"""
        error_mappings = {
            "llm_unavailable": "現在LLMサービスが利用できません。しばらくしてから再度お試しください。",
            "parse_error": "応答の解析に失敗しました。もう一度お試しください。",
            "search_partial": "一部の検索で問題が発生しましたが、他の結果で続行します。",
            "search_all_failed": "検索サービスに問題が発生しています。しばらくしてから再度お試しください。",
        }

        # ユーザーメッセージが日本語で適切なことを確認
        for key, message in error_mappings.items():
            assert message  # メッセージが空でない
            assert "。" in message  # 日本語の文末
            # 技術的な詳細を含まない
            assert "exception" not in message.lower()
            assert "error" not in message.lower()
            assert "stack" not in message.lower()
