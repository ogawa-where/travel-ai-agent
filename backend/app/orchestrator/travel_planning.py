"""
Travel Planning Orchestrator

旅行企画モードの全体フローを管理する司令塔。
CLAUDE.md セクション4.1の責務を実装。
"""

import logging
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

# 進捗コールバックの型
ProgressCallback = Callable[[str, int], Awaitable[None]]


def _utcnow() -> datetime:
    """timezone-naive な UTC 現在時刻（TIMESTAMP WITHOUT TIME ZONE 用）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.explainer import explainer_agent
from app.agents.planner import planner_agent
from app.agents.rerank import rerank_agent
from app.agents.search_agents import search_all_categories, search_with_reasoning, SearchAllResult
from app.agents.search_evaluator import search_evaluator_agent
from app.agents.translator import translator_agent
from app.domain.models import PlanRun, POICache, SessionEvent, TravelPlan, TravelPlanRequest
from app.schemas.travel_planning import (
    ExplainerInput,
    PlannerInput,
    POICategory,
    RerankInput,
    SearchResult,
    TranslateRequestInput,
    TravelConstraints,
    TravelWishes,
)
from app.agents.search_agents import SearchStatus
from app.services.normalizer import normalizer_deduper
from app.services.observability import artifact_storage
from app.services.poi_repository import poi_repository

logger = logging.getLogger(__name__)


class TravelPlanningOrchestrator:
    """旅行企画の全体フローを管理"""

    async def execute(
        self,
        db: AsyncSession,
        request: TravelPlanRequest,
        user_profile_summary: str = "",
        preference_signals: list[dict] | None = None,
        pre_constraints: TravelConstraints | None = None,
        pre_wishes: TravelWishes | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> TravelPlan:
        """
        旅行企画フローを実行

        Args:
            db: データベースセッション
            request: 旅行企画リクエスト
            user_profile_summary: ユーザープロフィール要約
            preference_signals: ユーザー嗜好シグナル
            pre_constraints: フォームから直接変換された制約（指定時はTranslatorスキップ）
            pre_wishes: フォームのfree_textから抽出された希望（任意）
            on_progress: 進捗コールバック (phase_name, progress_percent)

        Returns:
            生成された旅行プラン
        """
        # 進捗通知ヘルパー
        async def notify_progress(phase: str, percent: int):
            if on_progress:
                await on_progress(phase, percent)
        preference_signals = preference_signals or []
        start_time = time.time()

        # PlanRunを作成（トレース用）
        plan_run = PlanRun(
            request_id=request.id,
            status="running",
            config_snapshot={
                "user_profile_summary_length": len(user_profile_summary),
                "preference_signals_count": len(preference_signals),
                "form_input": pre_constraints is not None,
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
                    "form_input": pre_constraints is not None,
                },
            )

            # ステップ1: 要求の構造化（pre_constraintsがある場合はTranslatorスキップ）
            await notify_progress("translate", 0)
            if pre_constraints is not None:
                constraints = pre_constraints
                wishes = pre_wishes or TravelWishes()
                logger.info(
                    f"Using pre-built constraints (form input): "
                    f"destination={constraints.destination}, "
                    f"duration={constraints.duration_days}日"
                )
                await self._record_event(
                    db,
                    plan_run.id,
                    step_name="translate",
                    agent_name="FormInput",
                    input_summary="form-based constraints (Translator skipped)",
                    output_summary=f"destination: {constraints.destination}, "
                    f"duration: {constraints.duration_days}日",
                    latency_ms=0,
                    status="skipped",
                )
            else:
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
            await notify_progress("search", 16)
            search_results = await self._step_search(
                db,
                plan_run.id,
                constraints,
                wishes,
            )

            # ステップ3: 正規化・重複排除（Normalizer/Deduper）
            await notify_progress("normalize", 33)
            normalized_pois = await self._step_normalize(
                db,
                plan_run.id,
                search_results,
            )

            # ステップ3.5: POI DBに保存（PTSアーキテクチャ）
            poi_cache_map = await self._step_save_pois_to_db(
                db,
                plan_run.id,
                constraints.destination,
                normalized_pois,
            )

            # ステップ4: リランク（Rerank Agent）
            await notify_progress("rerank", 50)
            ranked_pois = await self._step_rerank(
                db,
                plan_run.id,
                normalized_pois,
                user_profile_summary,
                preference_signals,
                wishes,
            )

            # ステップ4.5: TravelSearchResultにリンク（PTSアーキテクチャ）
            await self._step_link_pois_to_request(
                db,
                plan_run.id,
                request.id,
                ranked_pois,
                poi_cache_map,
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
            await notify_progress("plan", 66)
            planner_result = await self._step_plan(
                db,
                plan_run.id,
                constraints,
                wishes,
                ranked_pois,
                user_profile_summary,
            )

            # ステップ5.5: 選択されたPOIをマーク（PTSアーキテクチャ）
            await self._step_mark_selected_pois(
                db,
                plan_run.id,
                request.id,
                planner_result.itinerary,
            )

            # ステップ6: 説明生成（Explainer Agent）
            await notify_progress("explain", 83)
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

            # 完了を通知
            await notify_progress("complete", 100)

            # リクエストとPlanRunを完了
            request.status = "completed"
            plan_run.status = "completed"
            plan_run.completed_at = _utcnow()
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
            plan_run.completed_at = _utcnow()
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
        """ステップ2: ハイブリッド2段階検索（4カテゴリ並列 + 横断評価）

        Phase 1: 4サーバー並列 SearchReasoningLoop（各最大2イテレーション）
        Phase 2: オーケストレーター横断評価（Heavy LLM）
        不足カテゴリがあれば再検索（最大1回の追加ラウンド）

        CLAUDE.md 8.7: 1-2エージェント失敗時は残りの結果で続行
        """
        start_time = time.time()

        # Phase 1: 4カテゴリ並列の推論ループ検索
        logger.info(f"Phase 1: Starting parallel reasoning search for {constraints.destination}")
        phase1_result = await search_with_reasoning(
            destination=constraints.destination,
            constraints=constraints,
            wishes=wishes,
            max_iterations=2,
        )

        await self._record_event(
            db,
            plan_run_id,
            step_name="search_phase1",
            agent_name="SearchReasoningLoop",
            input_summary=f"destination: {constraints.destination}, categories: 4",
            output_summary=f"total_results: {phase1_result.status.total_results}, "
            f"failed: {phase1_result.status.failed_categories}",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        # Phase 2: 横断評価
        phase2_start = time.time()
        logger.info("Phase 2: Cross-category evaluation")
        evaluation = await search_evaluator_agent.evaluate(
            search_results=phase1_result.results,
            constraints=constraints,
            wishes=wishes,
        )

        await self._record_event(
            db,
            plan_run_id,
            step_name="search_phase2_evaluate",
            agent_name="SearchEvaluatorAgent",
            input_summary=f"categories: {list(phase1_result.results.keys())}",
            output_summary=f"sufficient: {evaluation.sufficient_categories}, "
            f"insufficient: {[ic.category for ic in evaluation.insufficient_categories]}",
            latency_ms=int((time.time() - phase2_start) * 1000),
        )

        # 不足カテゴリの再検索（日程数に応じて最大3ラウンドまで）
        max_supplement_rounds = min(3, max(1, (constraints.duration_days or 2) // 3))
        supplement_round = 0

        while evaluation.has_insufficient and supplement_round < max_supplement_rounds:
            supplement_round += 1
            supplement_start = time.time()
            insufficient_categories = []
            hints_per_category = {}

            for ic in evaluation.insufficient_categories:
                try:
                    cat = POICategory(ic.category)
                    insufficient_categories.append(cat)
                    hints_per_category[ic.category] = ic.hints
                except ValueError:
                    logger.warning(f"Unknown category in evaluation: {ic.category}")

            if not insufficient_categories:
                break

            logger.info(
                f"Phase 2 supplement round {supplement_round}/{max_supplement_rounds}: "
                f"re-searching {[c.value for c in insufficient_categories]}"
            )
            supplemental_result = await search_with_reasoning(
                destination=constraints.destination,
                constraints=constraints,
                wishes=wishes,
                categories=insufficient_categories,
                hints_per_category=hints_per_category,
                max_iterations=2,  # 追加検索でも2イテレーション
            )

            # 結果をマージ
            phase1_result = self._merge_search_results(phase1_result, supplemental_result)

            await self._record_event(
                db,
                plan_run_id,
                step_name=f"search_phase2_supplement_round{supplement_round}",
                agent_name="SearchReasoningLoop",
                input_summary=f"re-search: {[c.value for c in insufficient_categories]}",
                output_summary=f"supplemental_results: {supplemental_result.status.total_results}",
                latency_ms=int((time.time() - supplement_start) * 1000),
            )

            # 追加検索後に再評価（最終ラウンド以外）
            if supplement_round < max_supplement_rounds:
                evaluation = await search_evaluator_agent.evaluate(
                    search_results=phase1_result.results,
                    constraints=constraints,
                    wishes=wishes,
                )
                logger.info(
                    f"Re-evaluation after round {supplement_round}: "
                    f"sufficient={evaluation.sufficient_categories}, "
                    f"insufficient={[ic.category for ic in evaluation.insufficient_categories]}"
                )

        # 最終ログ
        total_time = int((time.time() - start_time) * 1000)
        status = phase1_result.status
        output_parts = [f"total_results: {status.total_results}"]
        if status.partial_failure:
            output_parts.append(f"partial_failure: {status.failed_categories}")

        await self._record_event(
            db,
            plan_run_id,
            step_name="search",
            agent_name="HybridSearchPipeline",
            input_summary=f"destination: {constraints.destination}",
            output_summary=", ".join(output_parts),
            latency_ms=total_time,
        )

        return phase1_result.results

    def _merge_search_results(
        self,
        primary: SearchAllResult,
        supplemental: SearchAllResult,
    ) -> SearchAllResult:
        """2つの検索結果をマージ（supplementalで不足カテゴリを補完）"""
        merged_results = dict(primary.results)

        for category, result in supplemental.results.items():
            if category in merged_results:
                existing = merged_results[category]
                # 既存のアイテム名のセット
                existing_names = {item.name for item in existing.items}
                # 重複しないアイテムを追加
                new_items = [
                    item for item in result.items
                    if item.name not in existing_names
                ]
                merged_items = existing.items + new_items
                merged_results[category] = SearchResult(
                    category=category,
                    query=f"{existing.query} + supplement",
                    items=merged_items,
                    source="tavily+reasoning",
                    search_time_ms=existing.search_time_ms + result.search_time_ms,
                )
            else:
                merged_results[category] = result

        # ステータスを再計算
        merged_status = SearchStatus(total_categories=len(merged_results))
        for category, result in merged_results.items():
            cat_name = category.value
            if result.items:
                merged_status.successful_categories.append(cat_name)
            else:
                # 結果が空でも成功とみなす（検索自体は成功）
                merged_status.successful_categories.append(cat_name)
            merged_status.total_results += len(result.items)

        merged_status.all_failed = merged_status.total_results == 0
        merged_status.partial_failure = (
            len(primary.status.failed_categories) > 0
            and not merged_status.all_failed
        )

        return SearchAllResult(results=merged_results, status=merged_status)

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

    async def _step_save_pois_to_db(
        self,
        db: AsyncSession,
        plan_run_id: str,
        destination: str,
        normalized_pois: dict,
    ) -> dict:
        """ステップ3.5: POI DBに保存（PTSアーキテクチャ）

        検索結果をpoi_cacheに保存し、後のPlannerで参照可能にする。
        同じ(destination, category, name)の組み合わせは上書き。

        Returns:
            POI名 -> POICache IDのマッピング
        """
        start_time = time.time()
        poi_cache_map: dict[str, str] = {}
        total_saved = 0

        for category, pois in normalized_pois.items():
            if not pois:
                continue

            saved_pois = await poi_repository.save_search_results(
                db=db,
                destination=destination,
                category=category,
                pois=pois,
            )

            for poi_cache in saved_pois:
                poi_cache_map[poi_cache.name] = poi_cache.id
                total_saved += 1

        await self._record_event(
            db,
            plan_run_id,
            step_name="save_pois_to_db",
            agent_name="POIRepository",
            input_summary=f"destination: {destination}",
            output_summary=f"saved: {total_saved} POIs to DB",
            latency_ms=int((time.time() - start_time) * 1000),
        )

        return poi_cache_map

    async def _step_link_pois_to_request(
        self,
        db: AsyncSession,
        plan_run_id: str,
        request_id: str,
        ranked_pois: dict,
        poi_cache_map: dict[str, str],
    ) -> None:
        """ステップ4.5: TravelSearchResultにリンク（PTSアーキテクチャ）

        リランク済みPOIをTravelPlanRequestに紐付け、
        スコアを保存してPlannerが参照できるようにする。
        """
        start_time = time.time()
        total_linked = 0

        for category, pois in ranked_pois.items():
            poi_scores = []
            for poi in pois:
                poi_id = poi_cache_map.get(poi.name)
                if not poi_id:
                    continue

                # POIからスコアを取得
                rerank_score = getattr(poi, "final_score", 0.5)
                constraint_score = getattr(poi, "relevance_score", 0.5)

                # POICacheオブジェクトを取得
                poi_cache = await db.get(POICache, poi_id)
                if poi_cache:
                    poi_scores.append((poi_cache, rerank_score, constraint_score))

            if poi_scores:
                await poi_repository.link_pois_to_request(
                    db=db,
                    request_id=request_id,
                    poi_scores=poi_scores,
                )
                total_linked += len(poi_scores)

        await self._record_event(
            db,
            plan_run_id,
            step_name="link_pois_to_request",
            agent_name="POIRepository",
            input_summary=f"request: {request_id}",
            output_summary=f"linked: {total_linked} POIs",
            latency_ms=int((time.time() - start_time) * 1000),
        )

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
                transportation=ranked_pois.get(POICategory.TRANSPORTATION, []),
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

    async def _step_mark_selected_pois(
        self,
        db: AsyncSession,
        plan_run_id: str,
        request_id: str,
        itinerary,
    ) -> None:
        """ステップ5.5: 選択されたPOIをマーク（PTSアーキテクチャ）

        Plannerが選んだPOIをTravelSearchResultでis_selected=Trueに設定。
        後のExplainerや分析に利用。
        """
        start_time = time.time()

        # 旅程から選択されたPOI名を抽出
        selected_poi_names: set[str] = set()
        for day in itinerary.days:
            for item in day.items:
                if item.poi and item.poi.name:
                    selected_poi_names.add(item.poi.name)
            if day.accommodation and day.accommodation.name:
                selected_poi_names.add(day.accommodation.name)

        # TravelSearchResultを更新
        from sqlalchemy import select, and_
        from app.domain.models import TravelSearchResult

        result = await db.execute(
            select(TravelSearchResult).where(
                and_(
                    TravelSearchResult.request_id == request_id,
                    TravelSearchResult.poi.has(
                        POICache.name.in_(selected_poi_names)
                    ),
                )
            )
        )
        search_results = result.scalars().all()

        for sr in search_results:
            sr.is_selected = True

        await db.flush()

        await self._record_event(
            db,
            plan_run_id,
            step_name="mark_selected_pois",
            agent_name="POIRepository",
            input_summary=f"request: {request_id}",
            output_summary=f"marked: {len(search_results)} POIs as selected",
            latency_ms=int((time.time() - start_time) * 1000),
        )

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
