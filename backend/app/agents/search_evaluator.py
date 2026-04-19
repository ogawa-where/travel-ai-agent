"""
Search Evaluator Agent (Phase 2)

オーケストレーター横断評価エージェント。
4カテゴリの検索結果を横断的に評価し、
十分/不足カテゴリを判定する。

Heavy LLM（gpu-heavy）を使用。
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

    日程数に応じた必要POI数を計算し、十分性を判定する。
    """

    def _calculate_required_pois(self, duration_days: int | None) -> dict[str, int]:
        """日程数に応じた必要POI数を計算

        目安:
        - activity: 1日あたり2〜3件 → 日数 × 2.5（選択肢用に1.5倍）
        - food: 1日あたり2〜3件（朝は省略可） → 日数 × 2.5
        - hotel: 泊数分 + 選択肢 → (日数-1) × 1.5 + 1
        - transportation: 主要アクセス2〜3件 → 固定3件
        """
        days = duration_days or 2  # デフォルト2日

        return {
            "activity": max(5, int(days * 2.5 * 1.5)),  # 最低5件
            "food": max(4, int(days * 2.5 * 1.5)),      # 最低4件
            "hotel": max(2, int((days - 1) * 1.5) + 1), # 最低2件
            "transportation": 3,                         # 固定3件
        }

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
        # 日程数に応じた必要POI数を計算
        required_pois = self._calculate_required_pois(constraints.duration_days)

        # 結果サマリーを構築
        category_summaries = {}
        for category, result in search_results.items():
            items_info = []
            for item in result.items[:15]:  # 評価用に15件まで表示
                items_info.append({
                    "name": item.name,
                    "description": (item.description or "")[:80],
                    "tags": (item.tags or [])[:3],
                })
            category_summaries[category.value] = {
                "count": len(result.items),
                "required": required_pois.get(category.value, 5),
                "items": items_info,
            }

        prompt = f"""あなたは旅行計画の品質管理エキスパートです。
以下の4カテゴリの検索結果を横断的に評価してください。

## 旅行条件
- 目的地: {constraints.destination}
- 日数: {constraints.duration_days or '未定'}日間
- 予算: {constraints.budget_total or '未定'}円
- 人数: {constraints.num_people}人
- 移動手段制約: {constraints.transportation or 'なし'}

## 希望
{json.dumps(wishes.model_dump(), ensure_ascii=False, default=str)}

## 検索結果サマリー（現在の件数 / 必要件数）
{json.dumps(category_summaries, ensure_ascii=False, indent=2)}

## 評価基準（日程数ベース）
各カテゴリについて以下を評価:

1. **数量チェック**: 現在の件数が必要件数（required）を満たしているか
   - activity: {required_pois['activity']}件以上必要（{constraints.duration_days or 2}日間の旅程用）
   - food: {required_pois['food']}件以上必要
   - hotel: {required_pois['hotel']}件以上必要
   - transportation: {required_pois['transportation']}件以上必要

2. **多様性チェック**: 希望に合った多様な選択肢があるか
   - 同じような場所ばかりでないか
   - 価格帯や雰囲気のバリエーションがあるか

3. **整合性チェック**: 旅程全体として成り立つか
   - 交通とアクティビティの接続
   - 食事と観光の時間帯整合

## 出力形式（JSON）
{{
  "sufficient_categories": ["十分なカテゴリ名"],
  "insufficient_categories": [
    {{
      "category": "不足カテゴリ名",
      "reason": "不足の理由（数量不足 or 多様性不足 or 整合性問題）",
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
