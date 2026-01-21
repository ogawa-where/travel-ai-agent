"""
Travel Planning Orchestrator

旅行企画モードの全体フローを管理する司令塔。
CLAUDE.md セクション4.1の責務を実装。
"""

import logging
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.explainer import explainer_agent
from app.agents.planner import planner_agent
from app.agents.rerank import rerank_agent
from app.agents.search_agents import search_all_categories
from app.agents.translator import translator_agent
from app.domain.models import PlanRun, SessionEvent, TravelPlan, TravelPlanRequest
from app.schemas.travel_planning import (
    ExplainerInput,
    PlannerInput,
    POICategory,
    RerankInput,
    TranslateRequestInput,
    TravelConstraints,
    TravelWishes,
)
from app.services.normalizer import normalizer_deduper
from app.services.observability import artifact_storage

logger = logging.getLogger(__name__)


class TravelPlanningOrchestrator:
    """旅行企画の全体フローを管理"""

    async def execute(
        self,
        db: AsyncSession,
        request: TravelPlanRequest,
        user_profile_summary: str = "",
        preference_signals: list[dict] | None = None,
    ) -> TravelPlan:
        """
        旅行企画フローを実行

        Args:
            db: データベースセッション
            request: 旅行企画リクエスト
            user_profile_summary: ユーザープロフィール要約
            preference_signals: ユーザー嗜好シグナル

        Returns:
            生成された旅行プラン
        """
        preference_signals = preference_signals or []
        start_time = time.time()

        # PlanRunを作成（トレース用）
        plan_run = PlanRun(
            request_id=request.id,
            status="running",
            config_snapshot={
                "user_profile_summary_length": len(user_profile_summary),
                "preference_signals_count": len(preference_signals),
            },
        )
        db.add(plan_run)
        await db.flush()

        try:
            # 成果物: リクエスト情報を保存
            artifact_storage.store(
                plan_run.id,
                "request",
                {
                    "raw_request": request.raw_request,
                    "user_profile_summary_length": len(user_profile_summary),
                    "preference_signals_count": len(preference_signals),
                },
            )

            # ステップ1: 要求の構造化（Translator Agent）
            translate_result = await self._step_translate(
                db,
                plan_run.id,
                request.raw_request,
                user_profile_summary,
                preference_signals,
            )
            constraints = translate_result.constraints
            wishes = translate_result.wishes

            # リクエストに構造化結果を保存
            request.constraints = constraints.model_dump()
            request.wishes = wishes.model_dump()
            request.status = "processing"
            await db.flush()

            # 成果物: 構造化されたリクエストを保存
            artifact_storage.store(
                plan_run.id,
                "structured_request",
                {
                    "constraints": constraints.model_dump(),
                    "wishes": wishes.model_dump(),
                },
            )

            # ステップ2: 検索（Search Agents x3 並列実行）
            search_results = await self._step_search(
                db,
                plan_run.id,
                constraints,
                wishes,
            )

            # ステップ3: 正規化・重複排除（Normalizer/Deduper）
            normalized_pois = await self._step_normalize(
                db,
                plan_run.id,
                search_results,
            )

            # ステップ4: リランク（Rerank Agent）
            ranked_pois = await self._step_rerank(
                db,
                plan_run.id,
                normalized_pois,
                user_profile_summary,
                preference_signals,
                wishes,
            )

            # 成果物: 選定されたPOIを保存
            artifact_storage.store(
                plan_run.id,
                "selected_pois",
                {
                    category.value: [
                        {"name": poi.name, "category": poi.category.value, "final_score": poi.final_score}
                        for poi in pois[:10]  # 上位10件のみ
                    ]
                    for category, pois in ranked_pois.items()
                },
            )

            # ステップ5: 旅程生成（Planner Agent）
            planner_result = await self._step_plan(
                db,
                plan_run.id,
                constraints,
                wishes,
                ranked_pois,
                user_profile_summary,
            )

            # ステップ6: 説明生成（Explainer Agent）
            explainer_result = await self._step_explain(
                db,
                plan_run.id,
                planner_result.itinerary,
                user_profile_summary,
                preference_signals,
                wishes,
            )

            # TravelPlanを作成
            travel_plan = TravelPlan(
                request_id=request.id,
                itinerary=planner_result.itinerary.model_dump(),
                rationale=explainer_result.rationale,
                score=planner_result.score,
                score_breakdown=planner_result.score_breakdown,
            )
            db.add(travel_plan)

            # 成果物: プランと根拠を保存
            artifact_storage.store(
                plan_run.id,
                "plan",
                {
                    "itinerary": planner_result.itinerary.model_dump(),
                    "score": planner_result.score,
                    "score_breakdown": planner_result.score_breakdown,
                },
            )
            artifact_storage.store(
                plan_run.id,
                "rationale",
                explainer_result.rationale,
            )

            # リクエストとPlanRunを完了
            request.status = "completed"
            plan_run.status = "completed"
            plan_run.completed_at = datetime.utcnow()
            plan_run.metrics = {
                "total_time_ms": int((time.time() - start_time) * 1000),
                "search_results_count": sum(
                    len(pois) for pois in normalized_pois.values()
                ),
                "plan_score": planner_result.score,
            }

            await db.commit()
            await db.refresh(travel_plan)

            logger.info(
                f"Travel planning completed: request_id={request.id} "
                f"plan_id={travel_plan.id} "
                f"time={plan_run.metrics['total_time_ms']}ms"
            )

            return travel_plan

        except Exception as e:
            logger.error(f"Travel planning failed: {e}")
            request.status = "failed"
            plan_run.status = "failed"
            plan_run.completed_at = datetime.utcnow()
            plan_run.error_message = str(e)
            await db.commit()
            raise

    async def _step_translate(
        self,
        db: AsyncSession,
        plan_run_id: str,
        raw_request: str,
        user_profile_summary: str,
        preference_signals: list[dict],
    ):
        """ステップ1: 要求の構造化"""
        start_time = time.time()

        result = await translator_agent.translate(
            TranslateRequestInput(
                raw_request=raw_request,
                user_profile_summary=user_profile_summary,
                preference_signals=preference_signals,
            )
        )

        await self._record_event(
            db,
            plan_run_id,
            step_name="translate",
            agent_name="TranslatorAgent",
            input_summary=f"raw_request: {raw_request[:100]}...",
            output_summary=f"destination: {result.constraints.destination}, "
            f"duration: {result.constraints.duration_days}日",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return result

    async def _step_search(
        self,
        db: AsyncSession,
        plan_run_id: str,
        constraints: TravelConstraints,
        wishes: TravelWishes,
    ):
        """ステップ2: 検索（3カテゴリ並列）

        CLAUDE.md 8.7: 1-2エージェント失敗時は残りの結果で続行
        """
        start_time = time.time()

        # キーワードを構築
        keywords = {
            "activity": wishes.activities + wishes.experiences,
            "food": wishes.food_preferences,
            "hotel": [constraints.accommodation_type]
            if constraints.accommodation_type
            else [],
        }

        search_result = await search_all_categories(
            destination=constraints.destination,
            constraints=constraints.model_dump(),
            keywords=keywords,
            raise_on_all_failed=True,  # 全失敗時は例外
        )

        # ステータスに応じた出力サマリーを作成
        status = search_result.status
        output_parts = [f"total_results: {status.total_results}"]
        if status.partial_failure:
            output_parts.append(f"partial_failure: {status.failed_categories}")

        await self._record_event(
            db,
            plan_run_id,
            step_name="search",
            agent_name="SearchAgents",
            input_summary=f"destination: {constraints.destination}",
            output_summary=", ".join(output_parts),
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return search_result.results

    async def _step_normalize(
        self,
        db: AsyncSession,
        plan_run_id: str,
        search_results,
    ):
        """ステップ3: 正規化・重複排除"""
        start_time = time.time()

        # SearchResultからPOIリストを抽出
        pois_by_category = {
            category: result.items for category, result in search_results.items()
        }

        normalized = normalizer_deduper.process_by_category(pois_by_category)

        before_count = sum(len(pois) for pois in pois_by_category.values())
        after_count = sum(len(pois) for pois in normalized.values())

        await self._record_event(
            db,
            plan_run_id,
            step_name="normalize",
            agent_name="NormalizerDeduper",
            input_summary=f"before: {before_count} POIs",
            output_summary=f"after: {after_count} POIs",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return normalized

    async def _step_rerank(
        self,
        db: AsyncSession,
        plan_run_id: str,
        normalized_pois,
        user_profile_summary: str,
        preference_signals: list[dict],
        wishes: TravelWishes,
    ):
        """ステップ4: リランク"""
        start_time = time.time()

        ranked = {}
        for category, pois in normalized_pois.items():
            if not pois:
                ranked[category] = []
                continue

            result = await rerank_agent.rerank(
                RerankInput(
                    candidates=pois,
                    user_profile_summary=user_profile_summary,
                    preference_signals=preference_signals,
                    wishes=wishes,
                ),
                db=db,  # 体験キャッシュ用にDBセッションを渡す
            )
            ranked[category] = result.ranked_items

        await self._record_event(
            db,
            plan_run_id,
            step_name="rerank",
            agent_name="RerankAgent",
            input_summary=f"categories: {list(normalized_pois.keys())}",
            output_summary=f"ranked: {sum(len(r) for r in ranked.values())} POIs",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return ranked

    async def _step_plan(
        self,
        db: AsyncSession,
        plan_run_id: str,
        constraints: TravelConstraints,
        wishes: TravelWishes,
        ranked_pois,
        user_profile_summary: str,
    ):
        """ステップ5: 旅程生成"""
        start_time = time.time()

        result = await planner_agent.plan(
            PlannerInput(
                constraints=constraints,
                wishes=wishes,
                activities=ranked_pois.get(POICategory.ACTIVITY, []),
                foods=ranked_pois.get(POICategory.FOOD, []),
                hotels=ranked_pois.get(POICategory.HOTEL, []),
                user_profile_summary=user_profile_summary,
            )
        )

        await self._record_event(
            db,
            plan_run_id,
            step_name="plan",
            agent_name="PlannerAgent",
            input_summary=f"constraints: {constraints.destination}, {constraints.duration_days}日",
            output_summary=f"itinerary: {len(result.itinerary.days)}日, score={result.score:.2f}",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return result

    async def _step_explain(
        self,
        db: AsyncSession,
        plan_run_id: str,
        itinerary,
        user_profile_summary: str,
        preference_signals: list[dict],
        wishes: TravelWishes,
    ):
        """ステップ6: 説明生成"""
        start_time = time.time()

        result = await explainer_agent.explain(
            ExplainerInput(
                itinerary=itinerary,
                user_profile_summary=user_profile_summary,
                preference_signals=preference_signals,
                wishes=wishes,
            )
        )

        await self._record_event(
            db,
            plan_run_id,
            step_name="explain",
            agent_name="ExplainerAgent",
            input_summary=f"itinerary: {itinerary.title}",
            output_summary=f"rationale: {len(result.rationale)} chars, "
            f"highlights: {len(result.highlights)}",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return result

    async def _record_event(
        self,
        db: AsyncSession,
        plan_run_id: str,
        step_name: str,
        agent_name: str,
        input_summary: str,
        output_summary: str,
        latency_ms: int,
        status: str = "completed",
        error_message: str | None = None,
    ):
        """イベントを記録"""
        event = SessionEvent(
            plan_run_id=plan_run_id,
            step_name=step_name,
            agent_name=agent_name,
            input_summary=input_summary,
            output_summary=output_summary,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
        )
        db.add(event)
        await db.flush()

        logger.debug(f"Step {step_name}: {output_summary} ({latency_ms}ms)")


# Singleton instance
travel_orchestrator = TravelPlanningOrchestrator()
