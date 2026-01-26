"""
Search Evaluator Agent (Phase 2)

オーケストレーター横断評価エージェント。
4カテゴリの検索結果を横断的に評価し、
十分/不足カテゴリを判定する。

Heavy LLM（nubia）を使用。
"""

import json
import logging

from app.schemas.travel_planning import (
    CrossCategoryEvaluation,
    InsufficientCategory,
    POICategory,
    SearchResult,
    TravelConstraints,
    TravelWishes,
)
from app.services.llm_gateway import ModelTier, llm_gateway

logger = logging.getLogger(__name__)


class SearchEvaluatorAgent:
    """Phase 2: 横断評価エージェント

    4カテゴリの検索結果を横断的に評価し、
    sufficient/insufficient判定とhintsを出力する。
    """

    async def evaluate(
        self,
        search_results: dict[POICategory, SearchResult],
        constraints: TravelConstraints,
        wishes: TravelWishes,
    ) -> CrossCategoryEvaluation:
        """
        4カテゴリの検索結果を横断評価

        Args:
            search_results: カテゴリごとの検索結果
            constraints: 旅行制約
            wishes: 旅行希望

        Returns:
            CrossCategoryEvaluation: 横断評価結果
        """
        # 結果サマリーを構築
        category_summaries = {}
        for category, result in search_results.items():
            items_info = []
            for item in result.items[:10]:
                items_info.append({
                    "name": item.name,
                    "description": (item.description or "")[:80],
                    "tags": (item.tags or [])[:3],
                })
            category_summaries[category.value] = {
                "count": len(result.items),
                "items": items_info,
            }

        prompt = f"""あなたは旅行計画の品質管理エキスパートです。
以下の4カテゴリの検索結果を横断的に評価してください。

## 旅行条件
- 目的地: {constraints.destination}
- 日数: {constraints.duration_days or '未定'}
- 予算: {constraints.budget_total or '未定'}円
- 人数: {constraints.num_people}
- 移動手段制約: {constraints.transportation or 'なし'}

## 希望
{json.dumps(wishes.model_dump(), ensure_ascii=False, default=str)}

## 検索結果サマリー
{json.dumps(category_summaries, ensure_ascii=False)}

## 評価基準
各カテゴリについて以下を評価:
1. 候補数は旅程作成に十分か（activity: 5件以上、food: 3件以上、hotel: 2件以上、transportation: 1件以上）
2. 希望に合った多様な選択肢があるか
3. 旅程全体として整合性があるか（例：交通とアクティビティの接続）

## 出力形式（JSON）
{{
  "sufficient_categories": ["十分なカテゴリ名"],
  "insufficient_categories": [
    {{
      "category": "不足カテゴリ名",
      "reason": "不足の理由",
      "hints": ["追加検索のヒント1", "追加検索のヒント2"]
    }}
  ]
}}"""

        try:
            result = await llm_gateway.generate_json(
                prompt=prompt,
                tier=ModelTier.HEAVY,
                agent_name="search_evaluator",
                temperature=0.3,
            )

            # パース
            sufficient = result.get("sufficient_categories", [])
            insufficient_raw = result.get("insufficient_categories", [])

            insufficient = []
            for item in insufficient_raw:
                if isinstance(item, dict):
                    insufficient.append(InsufficientCategory(
                        category=item.get("category", ""),
                        reason=item.get("reason", ""),
                        hints=item.get("hints", []),
                    ))

            evaluation = CrossCategoryEvaluation(
                sufficient_categories=sufficient,
                insufficient_categories=insufficient,
            )

            logger.info(
                f"Cross-category evaluation: "
                f"sufficient={sufficient}, "
                f"insufficient={[ic.category for ic in insufficient]}"
            )

            return evaluation

        except Exception as e:
            logger.warning(f"Cross-category evaluation failed: {e}")
            # 評価失敗時は全て十分として続行
            all_categories = [cat.value for cat in search_results.keys()]
            return CrossCategoryEvaluation(
                sufficient_categories=all_categories,
                insufficient_categories=[],
            )


# Singleton instance
search_evaluator_agent = SearchEvaluatorAgent()
