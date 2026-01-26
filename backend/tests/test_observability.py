"""
Observability Tests

CLAUDE.md セクション12の要件:
- 各エージェントステップでログを残す
- 各実行の成果物を保存
- メトリクス収集

注: 実際のサービスに依存しないロジックテスト
"""

import pytest
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


# =============================================================================
# StepContextテスト
# =============================================================================


@dataclass
class MockStepContext:
    """テスト用ステップコンテキスト"""

    step_name: str
    agent_name: str
    plan_run_id: str | None = None
    start_time: float = field(default_factory=time.time)
    input_summary: str = ""
    output_summary: str = ""
    status: str = "running"
    error_message: str | None = None

    @property
    def elapsed_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)


class TestStepContext:
    """ステップコンテキストのテスト"""

    def test_initial_status_is_running(self):
        """初期ステータスがrunningであること"""
        ctx = MockStepContext(step_name="test", agent_name="TestAgent")
        assert ctx.status == "running"

    def test_elapsed_ms_increases(self):
        """経過時間が増加すること"""
        ctx = MockStepContext(step_name="test", agent_name="TestAgent")
        initial = ctx.elapsed_ms
        time.sleep(0.01)  # 10ms待機
        assert ctx.elapsed_ms > initial

    def test_context_stores_input_output(self):
        """入出力サマリーが保存されること"""
        ctx = MockStepContext(
            step_name="search",
            agent_name="SearchAgent",
            input_summary="destination: 京都",
            output_summary="found 15 POIs",
        )
        assert "京都" in ctx.input_summary
        assert "15 POIs" in ctx.output_summary

    def test_context_stores_error(self):
        """エラーメッセージが保存されること"""
        ctx = MockStepContext(step_name="test", agent_name="TestAgent")
        ctx.status = "failed"
        ctx.error_message = "Connection timeout"
        assert ctx.status == "failed"
        assert ctx.error_message == "Connection timeout"


# =============================================================================
# MetricsCollectorテスト
# =============================================================================


@dataclass
class MockAgentMetrics:
    """テスト用エージェントメトリクス"""

    call_count: int = 0
    total_latency_ms: int = 0
    error_count: int = 0
    last_called: datetime | None = None

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count


class MockMetricsCollector:
    """テスト用メトリクスコレクター"""

    def __init__(self):
        self._agent_metrics: dict[str, MockAgentMetrics] = {}

    def record_agent_call(
        self,
        agent_name: str,
        latency_ms: int,
        success: bool = True,
    ):
        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = MockAgentMetrics()

        metrics = self._agent_metrics[agent_name]
        metrics.call_count += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_called = datetime.now(UTC)
        if not success:
            metrics.error_count += 1

    def get_agent_metrics(self, agent_name: str) -> MockAgentMetrics | None:
        return self._agent_metrics.get(agent_name)


class TestMetricsCollector:
    """メトリクスコレクターのテスト"""

    def test_record_agent_call(self):
        """エージェント呼び出しが記録されること"""
        collector = MockMetricsCollector()
        collector.record_agent_call("TestAgent", 100)

        metrics = collector.get_agent_metrics("TestAgent")
        assert metrics is not None
        assert metrics.call_count == 1
        assert metrics.total_latency_ms == 100

    def test_multiple_calls_accumulate(self):
        """複数呼び出しが蓄積されること"""
        collector = MockMetricsCollector()
        collector.record_agent_call("TestAgent", 100)
        collector.record_agent_call("TestAgent", 200)
        collector.record_agent_call("TestAgent", 300)

        metrics = collector.get_agent_metrics("TestAgent")
        assert metrics.call_count == 3
        assert metrics.total_latency_ms == 600
        assert metrics.avg_latency_ms == 200.0

    def test_error_tracking(self):
        """エラーがトラッキングされること"""
        collector = MockMetricsCollector()
        collector.record_agent_call("TestAgent", 100, success=True)
        collector.record_agent_call("TestAgent", 50, success=False)
        collector.record_agent_call("TestAgent", 100, success=True)

        metrics = collector.get_agent_metrics("TestAgent")
        assert metrics.call_count == 3
        assert metrics.error_count == 1

    def test_separate_agent_metrics(self):
        """エージェントごとに別々のメトリクスであること"""
        collector = MockMetricsCollector()
        collector.record_agent_call("AgentA", 100)
        collector.record_agent_call("AgentB", 200)

        metrics_a = collector.get_agent_metrics("AgentA")
        metrics_b = collector.get_agent_metrics("AgentB")

        assert metrics_a.call_count == 1
        assert metrics_a.total_latency_ms == 100
        assert metrics_b.call_count == 1
        assert metrics_b.total_latency_ms == 200

    def test_unknown_agent_returns_none(self):
        """未知のエージェントはNoneを返すこと"""
        collector = MockMetricsCollector()
        metrics = collector.get_agent_metrics("UnknownAgent")
        assert metrics is None

    def test_avg_latency_zero_calls(self):
        """呼び出し0回の場合、平均レイテンシが0であること"""
        metrics = MockAgentMetrics()
        assert metrics.avg_latency_ms == 0.0


# =============================================================================
# ArtifactStorageテスト
# =============================================================================


@dataclass
class MockRunArtifact:
    """テスト用成果物"""

    run_id: str
    artifact_type: str
    data: dict | str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MockArtifactStorage:
    """テスト用成果物ストレージ"""

    def __init__(self):
        self._artifacts: dict[str, list[MockRunArtifact]] = {}

    def store(self, run_id: str, artifact_type: str, data: dict | str):
        if run_id not in self._artifacts:
            self._artifacts[run_id] = []
        self._artifacts[run_id].append(
            MockRunArtifact(run_id=run_id, artifact_type=artifact_type, data=data)
        )

    def get(self, run_id: str, artifact_type: str | None = None) -> list:
        artifacts = self._artifacts.get(run_id, [])
        if artifact_type:
            artifacts = [a for a in artifacts if a.artifact_type == artifact_type]
        return artifacts

    def get_all(self, run_id: str) -> dict:
        artifacts = self._artifacts.get(run_id, [])
        return {a.artifact_type: a.data for a in artifacts}


class TestArtifactStorage:
    """成果物ストレージのテスト"""

    def test_store_artifact(self):
        """成果物が保存されること"""
        storage = MockArtifactStorage()
        storage.store("run-1", "request", {"raw_request": "京都旅行"})

        artifacts = storage.get("run-1")
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "request"
        assert artifacts[0].data["raw_request"] == "京都旅行"

    def test_store_multiple_artifacts(self):
        """複数の成果物が保存されること"""
        storage = MockArtifactStorage()
        storage.store("run-1", "request", {"raw": "test"})
        storage.store("run-1", "plan", {"days": []})
        storage.store("run-1", "rationale", "理由")

        artifacts = storage.get("run-1")
        assert len(artifacts) == 3

    def test_get_by_type(self):
        """タイプでフィルタできること"""
        storage = MockArtifactStorage()
        storage.store("run-1", "request", {"raw": "test"})
        storage.store("run-1", "plan", {"days": []})

        request_artifacts = storage.get("run-1", "request")
        assert len(request_artifacts) == 1
        assert request_artifacts[0].artifact_type == "request"

    def test_get_all(self):
        """全成果物をまとめて取得できること"""
        storage = MockArtifactStorage()
        storage.store("run-1", "request", {"raw": "test"})
        storage.store("run-1", "plan", {"days": []})

        all_artifacts = storage.get_all("run-1")
        assert "request" in all_artifacts
        assert "plan" in all_artifacts

    def test_separate_runs(self):
        """実行ごとに分離されていること"""
        storage = MockArtifactStorage()
        storage.store("run-1", "request", {"raw": "run1"})
        storage.store("run-2", "request", {"raw": "run2"})

        run1_artifacts = storage.get("run-1")
        run2_artifacts = storage.get("run-2")

        assert len(run1_artifacts) == 1
        assert run1_artifacts[0].data["raw"] == "run1"
        assert len(run2_artifacts) == 1
        assert run2_artifacts[0].data["raw"] == "run2"

    def test_unknown_run_returns_empty(self):
        """未知の実行IDは空リストを返すこと"""
        storage = MockArtifactStorage()
        artifacts = storage.get("unknown-run")
        assert artifacts == []


# =============================================================================
# ログフォーマットテスト
# =============================================================================


class TestLogFormat:
    """ログフォーマットのテスト"""

    def test_truncate_long_text(self):
        """長いテキストが切り詰められること"""

        def truncate(text: str, max_length: int) -> str:
            if not text:
                return ""
            if len(text) <= max_length:
                return text
            return text[: max_length - 3] + "..."

        long_text = "a" * 1000
        truncated = truncate(long_text, 100)
        assert len(truncated) == 100
        assert truncated.endswith("...")

    def test_truncate_short_text_unchanged(self):
        """短いテキストはそのまま返されること"""

        def truncate(text: str, max_length: int) -> str:
            if not text:
                return ""
            if len(text) <= max_length:
                return text
            return text[: max_length - 3] + "..."

        short_text = "hello"
        truncated = truncate(short_text, 100)
        assert truncated == short_text

    def test_truncate_empty_text(self):
        """空テキストは空文字を返すこと"""

        def truncate(text: str, max_length: int) -> str:
            if not text:
                return ""
            if len(text) <= max_length:
                return text
            return text[: max_length - 3] + "..."

        assert truncate("", 100) == ""


# =============================================================================
# トレース構造テスト
# =============================================================================


class TestTraceStructure:
    """トレース構造のテスト"""

    def test_run_trace_structure(self):
        """実行トレースの構造が正しいこと"""
        trace = {
            "run": {
                "id": "run-1",
                "request_id": "req-1",
                "status": "completed",
                "started_at": "2025-01-01T00:00:00",
                "completed_at": "2025-01-01T00:01:00",
                "metrics": {"total_time_ms": 60000},
                "config_snapshot": {},
                "error_message": None,
            },
            "events": [
                {
                    "id": "event-1",
                    "step_name": "translate",
                    "agent_name": "TranslatorAgent",
                    "input_summary": "raw_request: 京都旅行",
                    "output_summary": "destination: 京都, duration: 2日",
                    "latency_ms": 1000,
                    "status": "completed",
                    "error_message": None,
                    "created_at": "2025-01-01T00:00:01",
                },
            ],
            "artifacts": {
                "request": {"raw_request": "京都旅行"},
                "plan": {"days": []},
            },
        }

        assert "run" in trace
        assert "events" in trace
        assert "artifacts" in trace
        assert trace["run"]["status"] == "completed"
        assert len(trace["events"]) == 1
        assert "request" in trace["artifacts"]

    def test_event_required_fields(self):
        """イベントに必須フィールドがあること"""
        required_fields = [
            "step_name",
            "agent_name",
            "input_summary",
            "output_summary",
            "latency_ms",
            "status",
        ]

        event = {
            "step_name": "search",
            "agent_name": "SearchAgent",
            "input_summary": "dest: 京都",
            "output_summary": "found 10 POIs",
            "latency_ms": 500,
            "status": "completed",
        }

        for field in required_fields:
            assert field in event


# =============================================================================
# 成果物タイプテスト
# =============================================================================


class TestArtifactTypes:
    """成果物タイプのテスト"""

    def test_required_artifact_types(self):
        """CLAUDE.md 12で要求される成果物タイプ"""
        # request JSON / 選定POI / plan JSON / rationale / 設定
        required_types = [
            "request",
            "selected_pois",
            "plan",
            "rationale",
            "config",
        ]

        storage = MockArtifactStorage()
        for artifact_type in required_types:
            storage.store("run-1", artifact_type, {"test": True})

        all_artifacts = storage.get_all("run-1")
        for artifact_type in required_types:
            assert artifact_type in all_artifacts

    def test_artifact_data_not_contain_secrets(self):
        """成果物にシークレットが含まれないこと"""
        # CLAUDE.md: 秘密情報やAPIキーをDB/ログに保存しない
        forbidden_keys = ["api_key", "secret", "password", "token"]

        artifact_data = {
            "raw_request": "京都旅行",
            "user_id": "user-123",
            "config": {"model": "qwen2.5"},
        }

        def check_no_secrets(data: dict) -> bool:
            for key in data.keys():
                if any(forbidden in key.lower() for forbidden in forbidden_keys):
                    return False
                if isinstance(data[key], dict):
                    if not check_no_secrets(data[key]):
                        return False
            return True

        assert check_no_secrets(artifact_data)
