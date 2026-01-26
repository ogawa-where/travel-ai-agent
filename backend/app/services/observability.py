"""
Observability Service

CLAUDE.md セクション12の要件:
- 各エージェントステップでログを残す（入力要約、出力要約、処理時間）
- 各実行の成果物をDBに保存（request JSON / 選定POI / plan JSON / rationale）
- フルの生プロンプトをデフォルトで保存しない

責務:
- 構造化ロギング
- メトリクス収集
- トレース管理
- 成果物の保存・取得
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PlanRun, SessionEvent

logger = logging.getLogger(__name__)


# =============================================================================
# 構造化ログフォーマッタ
# =============================================================================


class StructuredLogFormatter(logging.Formatter):
    """JSON形式の構造化ログフォーマッタ"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 追加フィールドがあれば含める
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def setup_structured_logging(log_level: str = "INFO"):
    """構造化ロギングをセットアップ"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 既存ハンドラをクリア
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 構造化フォーマッタを追加
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    root_logger.addHandler(handler)


# =============================================================================
# ステップトレーサー
# =============================================================================


@dataclass
class StepContext:
    """ステップ実行コンテキスト"""

    step_name: str
    agent_name: str
    plan_run_id: str | None = None
    start_time: float = field(default_factory=time.time)
    input_summary: str = ""
    output_summary: str = ""
    status: str = "running"
    error_message: str | None = None
    metrics: dict = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> int:
        return int((time.time() - self.start_time) * 1000)


class StepTracer:
    """エージェントステップのトレーサー"""

    def __init__(self):
        self._active_contexts: dict[str, StepContext] = {}

    @asynccontextmanager
    async def trace_step(
        self,
        db: AsyncSession | None,
        step_name: str,
        agent_name: str,
        plan_run_id: str | None = None,
        input_summary: str = "",
    ):
        """
        ステップをトレース

        Usage:
            async with tracer.trace_step(db, "search", "SearchAgent", run_id) as ctx:
                result = await search()
                ctx.output_summary = f"Found {len(result)} items"

        Args:
            db: データベースセッション（Noneの場合はログのみ）
            step_name: ステップ名
            agent_name: エージェント名
            plan_run_id: PlanRunのID
            input_summary: 入力の要約
        """
        ctx = StepContext(
            step_name=step_name,
            agent_name=agent_name,
            plan_run_id=plan_run_id,
            input_summary=input_summary,
        )

        context_key = f"{plan_run_id}:{step_name}" if plan_run_id else step_name
        self._active_contexts[context_key] = ctx

        logger.info(
            f"Step started: {step_name}",
            extra={
                "extra_data": {
                    "step_name": step_name,
                    "agent_name": agent_name,
                    "plan_run_id": plan_run_id,
                    "input_summary": input_summary[:200] if input_summary else "",
                }
            },
        )

        try:
            yield ctx
            ctx.status = "completed"
        except Exception as e:
            ctx.status = "failed"
            ctx.error_message = str(e)
            logger.error(
                f"Step failed: {step_name}",
                extra={
                    "extra_data": {
                        "step_name": step_name,
                        "agent_name": agent_name,
                        "error": str(e),
                        "elapsed_ms": ctx.elapsed_ms,
                    }
                },
            )
            raise
        finally:
            # DBに記録
            if db and plan_run_id:
                await self._save_event(db, ctx)

            # ログ出力
            logger.info(
                f"Step completed: {step_name}",
                extra={
                    "extra_data": {
                        "step_name": step_name,
                        "agent_name": agent_name,
                        "status": ctx.status,
                        "elapsed_ms": ctx.elapsed_ms,
                        "output_summary": ctx.output_summary[:200] if ctx.output_summary else "",
                    }
                },
            )

            # コンテキストをクリーンアップ
            self._active_contexts.pop(context_key, None)

    async def _save_event(self, db: AsyncSession, ctx: StepContext):
        """イベントをDBに保存"""
        event = SessionEvent(
            plan_run_id=ctx.plan_run_id,
            step_name=ctx.step_name,
            agent_name=ctx.agent_name,
            input_summary=self._truncate(ctx.input_summary, 1000),
            output_summary=self._truncate(ctx.output_summary, 1000),
            latency_ms=ctx.elapsed_ms,
            status=ctx.status,
            error_message=ctx.error_message,
        )
        db.add(event)
        await db.flush()

    def _truncate(self, text: str, max_length: int) -> str:
        """テキストを指定長で切り詰め"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."


# =============================================================================
# メトリクスコレクター
# =============================================================================


@dataclass
class AgentMetrics:
    """エージェントのメトリクス"""

    call_count: int = 0
    total_latency_ms: int = 0
    error_count: int = 0
    last_called: datetime | None = None

    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_latency_ms / self.call_count


class MetricsCollector:
    """メトリクス収集器"""

    def __init__(self):
        self._agent_metrics: dict[str, AgentMetrics] = {}
        self._run_metrics: dict[str, dict] = {}

    def record_agent_call(
        self,
        agent_name: str,
        latency_ms: int,
        success: bool = True,
    ):
        """エージェント呼び出しを記録"""
        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = AgentMetrics()

        metrics = self._agent_metrics[agent_name]
        metrics.call_count += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_called = datetime.now(UTC)
        if not success:
            metrics.error_count += 1

    def record_run_metric(
        self,
        run_id: str,
        key: str,
        value: Any,
    ):
        """実行メトリクスを記録"""
        if run_id not in self._run_metrics:
            self._run_metrics[run_id] = {}
        self._run_metrics[run_id][key] = value

    def get_agent_metrics(self, agent_name: str) -> AgentMetrics | None:
        """エージェントのメトリクスを取得"""
        return self._agent_metrics.get(agent_name)

    def get_all_agent_metrics(self) -> dict[str, dict]:
        """全エージェントのメトリクスを取得"""
        return {
            name: {
                "call_count": m.call_count,
                "avg_latency_ms": m.avg_latency_ms,
                "error_count": m.error_count,
                "error_rate": m.error_count / m.call_count if m.call_count > 0 else 0,
                "last_called": m.last_called.isoformat() if m.last_called else None,
            }
            for name, m in self._agent_metrics.items()
        }

    def get_run_metrics(self, run_id: str) -> dict:
        """実行メトリクスを取得"""
        return self._run_metrics.get(run_id, {})


# =============================================================================
# 成果物ストレージ
# =============================================================================


@dataclass
class RunArtifact:
    """実行成果物"""

    run_id: str
    artifact_type: str  # request, selected_pois, plan, rationale, config
    data: dict | str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ArtifactStorage:
    """成果物ストレージ"""

    def __init__(self):
        # インメモリストレージ（将来的にはDBやファイルシステムに移行可能）
        self._artifacts: dict[str, list[RunArtifact]] = {}

    def store(
        self,
        run_id: str,
        artifact_type: str,
        data: dict | str,
    ):
        """成果物を保存"""
        if run_id not in self._artifacts:
            self._artifacts[run_id] = []

        artifact = RunArtifact(
            run_id=run_id,
            artifact_type=artifact_type,
            data=data,
        )
        self._artifacts[run_id].append(artifact)

        logger.debug(
            f"Artifact stored: {artifact_type}",
            extra={
                "extra_data": {
                    "run_id": run_id,
                    "artifact_type": artifact_type,
                }
            },
        )

    def get(self, run_id: str, artifact_type: str | None = None) -> list[RunArtifact]:
        """成果物を取得"""
        artifacts = self._artifacts.get(run_id, [])
        if artifact_type:
            artifacts = [a for a in artifacts if a.artifact_type == artifact_type]
        return artifacts

    def get_all(self, run_id: str) -> dict[str, Any]:
        """全成果物をまとめて取得"""
        artifacts = self._artifacts.get(run_id, [])
        return {a.artifact_type: a.data for a in artifacts}


# =============================================================================
# トレースビューア（API用）
# =============================================================================


class TraceViewer:
    """トレース閲覧サービス"""

    async def get_run_trace(
        self,
        db: AsyncSession,
        run_id: str,
    ) -> dict | None:
        """
        実行のトレースを取得

        Returns:
            {
                "run": {...},
                "events": [...],
                "artifacts": {...}
            }
        """
        # PlanRunを取得
        result = await db.execute(
            select(PlanRun).where(PlanRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return None

        # SessionEventsを取得
        result = await db.execute(
            select(SessionEvent)
            .where(SessionEvent.plan_run_id == run_id)
            .order_by(SessionEvent.created_at)
        )
        events = list(result.scalars().all())

        # 成果物を取得
        artifacts = artifact_storage.get_all(run_id)

        return {
            "run": {
                "id": run.id,
                "request_id": run.request_id,
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "metrics": run.metrics,
                "config_snapshot": run.config_snapshot,
                "error_message": run.error_message,
            },
            "events": [
                {
                    "id": e.id,
                    "step_name": e.step_name,
                    "agent_name": e.agent_name,
                    "input_summary": e.input_summary,
                    "output_summary": e.output_summary,
                    "latency_ms": e.latency_ms,
                    "status": e.status,
                    "error_message": e.error_message,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
            "artifacts": artifacts,
        }

    async def list_runs(
        self,
        db: AsyncSession,
        request_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """実行一覧を取得"""
        query = select(PlanRun).order_by(PlanRun.started_at.desc())

        if request_id:
            query = query.where(PlanRun.request_id == request_id)
        if status:
            query = query.where(PlanRun.status == status)

        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        runs = list(result.scalars().all())

        return [
            {
                "id": r.id,
                "request_id": r.request_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "duration_ms": (
                    int((r.completed_at - r.started_at).total_seconds() * 1000)
                    if r.completed_at and r.started_at
                    else None
                ),
            }
            for r in runs
        ]


# =============================================================================
# デコレーター
# =============================================================================


def trace_agent_call(agent_name: str):
    """
    エージェント呼び出しをトレースするデコレーター

    Usage:
        @trace_agent_call("TranslatorAgent")
        async def translate(self, input: TranslateInput):
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                return await func(*args, **kwargs)
            except Exception:
                success = False
                raise
            finally:
                elapsed_ms = int((time.time() - start_time) * 1000)
                metrics_collector.record_agent_call(agent_name, elapsed_ms, success)

        return wrapper

    return decorator


# =============================================================================
# シングルトンインスタンス
# =============================================================================

step_tracer = StepTracer()
metrics_collector = MetricsCollector()
artifact_storage = ArtifactStorage()
trace_viewer = TraceViewer()
