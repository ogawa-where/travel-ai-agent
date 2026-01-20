"""
Observability API Router

CLAUDE.md セクション12の要件:
- トレース/成果物の閲覧API

エンドポイント:
- GET /api/observability/runs - 実行一覧
- GET /api/observability/runs/{run_id} - 実行詳細とトレース
- GET /api/observability/metrics - エージェントメトリクス
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.observability import metrics_collector, trace_viewer

router = APIRouter(prefix="/api/observability", tags=["observability"])


# =============================================================================
# スキーマ
# =============================================================================


class RunSummary(BaseModel):
    """実行サマリー"""

    id: str
    request_id: str
    status: str
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None


class EventDetail(BaseModel):
    """イベント詳細"""

    id: str
    step_name: str
    agent_name: str
    input_summary: str
    output_summary: str
    latency_ms: int
    status: str
    error_message: str | None
    created_at: str | None


class RunDetail(BaseModel):
    """実行詳細"""

    id: str
    request_id: str
    status: str
    started_at: str | None
    completed_at: str | None
    metrics: dict
    config_snapshot: dict
    error_message: str | None


class RunTraceResponse(BaseModel):
    """実行トレースレスポンス"""

    run: RunDetail
    events: list[EventDetail]
    artifacts: dict


class AgentMetricsResponse(BaseModel):
    """エージェントメトリクスレスポンス"""

    call_count: int
    avg_latency_ms: float
    error_count: int
    error_rate: float
    last_called: str | None


class AllMetricsResponse(BaseModel):
    """全メトリクスレスポンス"""

    agents: dict[str, AgentMetricsResponse]


# =============================================================================
# エンドポイント
# =============================================================================


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    request_id: str | None = Query(None, description="リクエストIDでフィルタ"),
    status: str | None = Query(None, description="ステータスでフィルタ"),
    limit: int = Query(20, ge=1, le=100, description="取得件数"),
    offset: int = Query(0, ge=0, description="オフセット"),
    db: AsyncSession = Depends(get_db),
):
    """
    実行一覧を取得

    - request_id: 特定のリクエストの実行のみ取得
    - status: running, completed, failed でフィルタ
    """
    runs = await trace_viewer.list_runs(
        db,
        request_id=request_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return runs


@router.get("/runs/{run_id}", response_model=RunTraceResponse)
async def get_run_trace(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    実行の詳細トレースを取得

    - run: 実行情報
    - events: ステップごとのイベント（時系列順）
    - artifacts: 保存された成果物
    """
    trace = await trace_viewer.get_run_trace(db, run_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Run not found")
    return trace


@router.get("/metrics", response_model=AllMetricsResponse)
async def get_metrics():
    """
    エージェントメトリクスを取得

    - 各エージェントの呼び出し回数、平均レイテンシ、エラー率
    """
    agent_metrics = metrics_collector.get_all_agent_metrics()
    return {"agents": agent_metrics}


@router.get("/metrics/{agent_name}")
async def get_agent_metrics(agent_name: str):
    """
    特定エージェントのメトリクスを取得
    """
    metrics = metrics_collector.get_agent_metrics(agent_name)
    if not metrics:
        return {
            "call_count": 0,
            "avg_latency_ms": 0,
            "error_count": 0,
            "error_rate": 0,
            "last_called": None,
        }

    return {
        "call_count": metrics.call_count,
        "avg_latency_ms": metrics.avg_latency_ms,
        "error_count": metrics.error_count,
        "error_rate": metrics.error_count / metrics.call_count if metrics.call_count > 0 else 0,
        "last_called": metrics.last_called.isoformat() if metrics.last_called else None,
    }
