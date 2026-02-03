"""
Search Agents

CLAUDE.md セクション8.7に基づくエラーハンドリング:
- 1-2エージェント失敗: 残りの結果で続行
- 全エージェント失敗: エラーを報告

検索を担当するエージェント群（I/O主体）。
- ActivitySearchAgent: 体験・観光の検索
- FoodSearchAgent: 食・レストランの検索
- HotelSearchAgent: 宿泊先の検索
- TransportationSearchAgent: 交通・アクセスの検索

4体を非同期で並列実行可能。

SearchReasoningLoop: 推論→検索→検証の自律ループ（各カテゴリ1つ）
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import SearchAllFailedError
from app.schemas.travel_planning import (
    CrossCategoryEvaluation,
    POICategory,
    POISearchResult,
    SearchQuery,
    SearchResult,
    SearchVerdict,
    TravelConstraints,
    TravelWishes,
)
from app.services.tavily_client import tavily_client

logger = logging.getLogger(__name__)


@dataclass
class SearchStatus:
    """検索ステータス"""

    total_categories: int = 0
    successful_categories: list[str] = field(default_factory=list)
    failed_categories: list[str] = field(default_factory=list)
    total_results: int = 0
    partial_failure: bool = False
    all_failed: bool = False
    error_messages: dict[str, str] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_categories == 0:
            return 0.0
        return len(self.successful_categories) / self.total_categories

    def to_dict(self) -> dict:
        """辞書に変換"""
        return {
            "total_categories": self.total_categories,
            "successful_categories": self.successful_categories,
            "failed_categories": self.failed_categories,
            "total_results": self.total_results,
            "partial_failure": self.partial_failure,
            "all_failed": self.all_failed,
            "success_rate": self.success_rate,
        }


class BaseSearchAgent(ABC):
    """検索エージェントの基底クラス"""

    def __init__(self, category: POICategory):
        self.category = category

    @abstractmethod
    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """検索キーワードを構築"""
        pass

    @abstractmethod
    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果からPOI情報を抽出"""
        pass

    async def search(self, query: SearchQuery) -> SearchResult:
        """
        検索を実行

        Args:
            query: 検索クエリ

        Returns:
            検索結果
        """
        start_time = time.time()

        keywords = self._build_keywords(query)

        try:
            raw_results = await tavily_client.search_for_travel(
                destination=query.destination,
                category=self.category.value,
                keywords=keywords,
                max_results=15,
            )

            items = []
            for result in raw_results.get("results", []):
                poi = self._extract_poi_from_result(result)
                if poi:
                    items.append(poi)

            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"{self.__class__.__name__} search completed: "
                f"destination={query.destination} "
                f"results={len(items)} "
                f"time={elapsed_ms}ms"
            )

            return SearchResult(
                category=self.category,
                query=f"{query.destination} {' '.join(keywords)}",
                items=items,
                source="tavily",
                search_time_ms=elapsed_ms,
            )

        except Exception as e:
            logger.error(f"{self.__class__.__name__} search failed: {e}")
            return SearchResult(
                category=self.category,
                query=f"{query.destination} {' '.join(keywords)}",
                items=[],
                source="tavily",
                search_time_ms=int((time.time() - start_time) * 1000),
            )


class ActivitySearchAgent(BaseSearchAgent):
    """体験・観光検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.ACTIVITY)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """体験・観光用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        # 制約から追加キーワードを抽出
        constraints = query.constraints
        if constraints.get("activities"):
            keywords.extend(constraints["activities"])
        if constraints.get("experiences"):
            keywords.extend(constraints["experiences"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果からアクティビティPOIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        # 基本情報を抽出
        return POISearchResult(
            name=title,
            category=POICategory.ACTIVITY,
            location="",  # 後で正規化時に抽出
            description=content[:300] if content else "",
            price_range="",
            duration_minutes=None,
            opening_hours="",
            rating=None,
            tags=self._extract_tags_from_content(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_tags_from_content(self, content: str) -> list[str]:
        """コンテンツからタグを抽出"""
        tags = []
        tag_keywords = [
            "自然",
            "文化",
            "歴史",
            "体験",
            "アウトドア",
            "インドア",
            "家族",
            "カップル",
            "グループ",
            "ソロ",
            "絶景",
            "パワースポット",
            "温泉",
            "神社",
            "寺院",
            "美術館",
            "博物館",
        ]
        content_lower = content.lower() if content else ""
        for keyword in tag_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]  # 最大5個


class FoodSearchAgent(BaseSearchAgent):
    """食・レストラン検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.FOOD)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """食・レストラン用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        # Note: query.constraints には wishes の情報も含まれる（呼び出し元で統合）
        data = query.constraints
        if data.get("food_preferences"):
            keywords.extend(data["food_preferences"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果から食POIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        return POISearchResult(
            name=title,
            category=POICategory.FOOD,
            location="",
            description=content[:300] if content else "",
            price_range=self._extract_price_range(content),
            duration_minutes=60,  # デフォルト1時間
            opening_hours="",
            rating=None,
            tags=self._extract_food_tags(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_price_range(self, content: str) -> str:
        """価格帯を抽出"""
        if not content:
            return ""
        # 簡易的な価格帯抽出
        if "高級" in content or "贅沢" in content:
            return "¥10,000~"
        if "リーズナブル" in content or "お手頃" in content:
            return "~¥2,000"
        return ""

    def _extract_food_tags(self, content: str) -> list[str]:
        """食関連のタグを抽出"""
        tags = []
        food_keywords = [
            "和食",
            "洋食",
            "中華",
            "イタリアン",
            "フレンチ",
            "寿司",
            "ラーメン",
            "居酒屋",
            "カフェ",
            "スイーツ",
            "郷土料理",
            "海鮮",
            "肉料理",
            "野菜",
            "ヴィーガン",
            "ベジタリアン",
        ]
        content_lower = content.lower() if content else ""
        for keyword in food_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]


class HotelSearchAgent(BaseSearchAgent):
    """宿泊先検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.HOTEL)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """宿泊先用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        # Note: query.constraints には wishes の情報も含まれる（呼び出し元で統合）
        data = query.constraints
        if data.get("accommodation_type"):
            keywords.append(data["accommodation_type"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果から宿泊POIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        return POISearchResult(
            name=title,
            category=POICategory.HOTEL,
            location="",
            description=content[:300] if content else "",
            price_range=self._extract_hotel_price(content),
            duration_minutes=None,
            opening_hours="",
            rating=None,
            tags=self._extract_hotel_tags(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_hotel_price(self, content: str) -> str:
        """宿泊料金を抽出"""
        if not content:
            return ""
        if "高級" in content or "ラグジュアリー" in content:
            return "¥30,000~/泊"
        if "リーズナブル" in content or "格安" in content:
            return "~¥10,000/泊"
        return ""

    def _extract_hotel_tags(self, content: str) -> list[str]:
        """宿泊関連のタグを抽出"""
        tags = []
        hotel_keywords = [
            "温泉",
            "露天風呂",
            "旅館",
            "ホテル",
            "民宿",
            "ゲストハウス",
            "オーシャンビュー",
            "山の景色",
            "朝食付き",
            "夕食付き",
            "素泊まり",
            "ペット可",
            "駐車場",
            "Wi-Fi",
        ]
        content_lower = content.lower() if content else ""
        for keyword in hotel_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]


class TransportationSearchAgent(BaseSearchAgent):
    """交通・アクセス検索エージェント"""

    def __init__(self):
        super().__init__(POICategory.TRANSPORTATION)

    def _build_keywords(self, query: SearchQuery) -> list[str]:
        """交通・アクセス用のキーワードを構築"""
        keywords = list(query.keywords) if query.keywords else []

        constraints = query.constraints
        if constraints.get("transportation"):
            keywords.append(constraints["transportation"])

        return keywords

    def _extract_poi_from_result(self, result: dict) -> POISearchResult | None:
        """検索結果から交通POIを抽出"""
        title = result.get("title", "")
        url = result.get("url", "")
        content = result.get("content", "")

        if not title:
            return None

        return POISearchResult(
            name=title,
            category=POICategory.TRANSPORTATION,
            location="",
            description=content[:300] if content else "",
            price_range=self._extract_transport_price(content),
            duration_minutes=None,
            opening_hours="",
            rating=None,
            tags=self._extract_transport_tags(content),
            source_url=url,
            relevance_score=result.get("score", 0.5),
            source_name="tavily",
        )

    def _extract_transport_price(self, content: str) -> str:
        """交通料金を抽出"""
        if not content:
            return ""
        if "高速" in content and "バス" in content:
            return "¥2,000~5,000"
        if "新幹線" in content:
            return "¥5,000~20,000"
        if "レンタカー" in content:
            return "¥5,000~/日"
        return ""

    def _extract_transport_tags(self, content: str) -> list[str]:
        """交通関連のタグを抽出"""
        tags = []
        transport_keywords = [
            "電車",
            "バス",
            "タクシー",
            "レンタカー",
            "新幹線",
            "飛行機",
            "フェリー",
            "徒歩",
            "自転車",
            "空港",
            "駅",
            "高速バス",
            "路線バス",
            "シャトルバス",
        ]
        content_lower = content.lower() if content else ""
        for keyword in transport_keywords:
            if keyword in content_lower:
                tags.append(keyword)
        return tags[:5]


# =============================================================================
# 検索推論ループ（Phase 1）
# =============================================================================


def _load_search_routing() -> dict:
    """search_routing設定をollama_workers.jsonから読み込み"""
    config_paths = [
        Path("config/ollama_workers.json"),
        Path("/app/config/ollama_workers.json"),
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                return config.get("search_routing", {})
            except Exception:
                pass
    return {}


class SearchReasoningLoop:
    """推論→検索→検証の自律ループ（各カテゴリ1つ）

    Phase 1 のエージェント自律ループを実装。
    各カテゴリに対して REASON → SEARCH → VERIFY のサイクルを
    最大 max_iterations 回繰り返す。
    """

    def __init__(self):
        # 遅延インポート（循環参照回避）
        self._gateway = None

    def _get_gateway(self):
        if self._gateway is None:
            from app.services.llm_gateway import llm_gateway
            self._gateway = llm_gateway
        return self._gateway

    async def execute(
        self,
        category: POICategory,
        destination: str,
        constraints: TravelConstraints,
        wishes: TravelWishes,
        worker_host: str,
        model: str,
        hints: list[str] | None = None,
        max_iterations: int = 2,
    ) -> SearchResult:
        """
        推論→検索→検証の自律ループを実行

        Args:
            category: 検索カテゴリ
            destination: 目的地
            constraints: 旅行制約
            wishes: 旅行希望
            worker_host: LLM実行先ホスト
            model: 使用モデル名
            hints: Phase 2からの追加検索ヒント
            max_iterations: 最大ループ回数

        Returns:
            SearchResult: 検索結果
        """
        hints = hints or []
        all_items: list[POISearchResult] = []
        start_time = time.time()

        for iteration in range(max_iterations):
            try:
                # 1. REASON: 検索クエリをLLMで生成
                queries = await self._reason(
                    category=category,
                    destination=destination,
                    constraints=constraints,
                    wishes=wishes,
                    existing_items=all_items,
                    hints=hints,
                    worker_host=worker_host,
                    model=model,
                    iteration=iteration,
                )

                # 2. SEARCH: Tavily検索 + LLM POI抽出
                new_items = await self._search(
                    category=category,
                    destination=destination,
                    queries=queries,
                    worker_host=worker_host,
                    model=model,
                )
                all_items.extend(new_items)

                # 3. VERIFY: 結果をLLMで評価（最終イテレーションではスキップ）
                if iteration < max_iterations - 1:
                    verdict = await self._verify(
                        category=category,
                        destination=destination,
                        constraints=constraints,
                        wishes=wishes,
                        items=all_items,
                        hints=hints,
                        worker_host=worker_host,
                        model=model,
                    )

                    logger.info(
                        f"SearchReasoningLoop [{category.value}] iteration={iteration + 1}: "
                        f"items={len(all_items)}, sufficient={verdict.sufficient}"
                    )

                    if verdict.sufficient:
                        break
                else:
                    logger.info(
                        f"SearchReasoningLoop [{category.value}] iteration={iteration + 1}: "
                        f"items={len(all_items)}, final iteration (verify skipped)"
                    )

            except Exception as e:
                logger.warning(
                    f"SearchReasoningLoop [{category.value}] iteration={iteration + 1} "
                    f"error: {e}"
                )
                # エラーでもこれまでの結果は保持して続行
                break

        elapsed_ms = int((time.time() - start_time) * 1000)

        return SearchResult(
            category=category,
            query=f"{destination} {category.value}",
            items=all_items,
            source="tavily+reasoning",
            search_time_ms=elapsed_ms,
        )

    async def _reason(
        self,
        category: POICategory,
        destination: str,
        constraints: TravelConstraints,
        wishes: TravelWishes,
        existing_items: list[POISearchResult],
        hints: list[str],
        worker_host: str,
        model: str,
        iteration: int,
    ) -> list[str]:
        """LLMで検索クエリを生成"""
        existing_names = [item.name for item in existing_items[:10]]

        hints_text = ""
        if hints:
            hints_text = f"\n追加の検索ヒント: {', '.join(hints)}"

        existing_text = ""
        if existing_names:
            existing_text = f"\n既に見つかった候補: {', '.join(existing_names)}"
            existing_text += "\n上記と重複しない新しい候補を見つけるクエリを生成してください。"

        prompt = f"""あなたは旅行検索の専門家です。
以下の条件で「{category.value}」カテゴリの検索クエリを生成してください。

目的地: {destination}
カテゴリ: {category.value}
日数: {constraints.duration_days or '未定'}
予算: {constraints.budget_total or '未定'}
人数: {constraints.num_people}
希望: {json.dumps(wishes.model_dump(), ensure_ascii=False, default=str)}
イテレーション: {iteration + 1}回目
{hints_text}{existing_text}

JSON形式で2〜3個の検索クエリを出力してください。
{{"queries": ["クエリ1", "クエリ2", "クエリ3"]}}"""

        try:
            gateway = self._get_gateway()
            result = await gateway.generate_json(
                prompt=prompt,
                tier=self._get_tier_for_model(model),
                worker_host=worker_host,
                model_override=model,
                temperature=0.5,
                agent_name="search_reasoner",
            )
            queries = result.get("queries", [])
            if not queries:
                # フォールバック: デフォルトクエリ
                queries = [f"{destination} {category.value} おすすめ"]
            return queries
        except Exception as e:
            logger.warning(f"Reason step failed for {category.value}: {e}")
            return [f"{destination} {category.value} おすすめ"]

    async def _search(
        self,
        category: POICategory,
        destination: str,
        queries: list[str],
        worker_host: str = "",
        model: str = "",
    ) -> list[POISearchResult]:
        """Tavily検索を並列実行し、LLMでPOIをバッチ抽出"""
        agent = _get_agent_for_category(category)

        # 1. 全クエリのTavily検索を並列実行
        tavily_tasks = [
            tavily_client.search_for_travel(
                destination=destination,
                category=category.value,
                keywords=query_text.split(),
                max_results=10,
            )
            for query_text in queries
        ]
        raw_results_list = await asyncio.gather(*tavily_tasks, return_exceptions=True)

        # 2. 全結果を結合（エラーはスキップ）
        combined_results: list[dict] = []
        for i, raw in enumerate(raw_results_list):
            if isinstance(raw, Exception):
                logger.warning(f"Search query failed: {queries[i]}: {raw}")
                continue
            combined_results.extend(raw.get("results", []))

        if not combined_results:
            return []

        # 3. LLMベースPOI抽出をバッチで1回実行
        if worker_host and model:
            try:
                llm_pois = await self._extract_pois_with_llm(
                    raw_results=combined_results[:20],
                    category=category,
                    destination=destination,
                    worker_host=worker_host,
                    model=model,
                )
                if llm_pois:
                    return llm_pois
            except Exception as e:
                logger.warning(
                    f"LLM POI extraction failed for {category.value}, "
                    f"falling back to rule-based: {e}"
                )

        # 4. フォールバック: 従来のルールベース抽出
        all_items: list[POISearchResult] = []
        for result in combined_results:
            poi = agent._extract_poi_from_result(result)
            if poi:
                all_items.append(poi)

        return all_items

    async def _extract_pois_with_llm(
        self,
        raw_results: list[dict],
        category: POICategory,
        destination: str,
        worker_host: str,
        model: str,
    ) -> list[POISearchResult]:
        """LLMを使用して検索結果から実際のPOI情報を抽出

        記事タイトルではなく、実際の施設名・場所名を抽出する。
        目的地エリア外の場所は除外する。

        Args:
            raw_results: Tavilyの生の検索結果（最大10件）
            category: POIカテゴリ
            destination: 目的地
            worker_host: LLM実行先ホスト
            model: 使用モデル名

        Returns:
            抽出されたPOIリスト
        """
        # 検索結果を要約してプロンプトに渡す（バッチ対応: 最大20件）
        results_for_prompt = []
        for i, result in enumerate(raw_results[:20]):
            title = result.get("title", "")
            content = result.get("content", "")[:300]
            results_for_prompt.append(
                f"[{i}] タイトル: {title}\n    内容: {content}"
            )

        results_text = "\n".join(results_for_prompt)

        category_labels = {
            POICategory.ACTIVITY: "観光地・体験施設",
            POICategory.FOOD: "飲食店・レストラン",
            POICategory.HOTEL: "宿泊施設",
            POICategory.TRANSPORTATION: "交通手段・アクセス情報",
        }
        category_label = category_labels.get(category, category.value)

        prompt = f"""以下の検索結果から「{destination}」に存在する{category_label}の情報を抽出してください。

ルール:
- 記事タイトルではなく、実際の施設名・場所名を抽出すること
- 1つの記事から複数のPOIを抽出してもよい
- 「{destination}」エリア外の場所は除外すること
- source_indexは元の検索結果の番号[0]〜[{len(raw_results)-1}]を指定
- 可能な限り詳細な情報（評価、価格、営業時間等）を抽出すること

検索結果:
{results_text}

JSON形式で出力（PTS/RealTravel形式）:
{{
  "pois": [
    {{
      "name": "施設名（正式名称）",
      "location": "地区名・エリア名",
      "address": "詳細住所（わかれば）",
      "description": "施設の説明（100文字程度）",
      "rating": 4.5,  // 評価 1.0-5.0（不明ならnull）
      "review_count": 120,  // レビュー数（不明ならnull）
      "price_level": 2,  // 価格帯 1=安い 2=普通 3=高め 4=高級（不明ならnull）
      "price_range": "¥1,000〜2,000",  // 価格帯テキスト
      "budget_per_person": 1500,  // 1人あたり予算（円、不明ならnull）
      "hours": "9:00-18:00",  // 営業時間テキスト
      "duration_minutes": 60,  // 所要時間（分、不明ならnull）
      "features": ["WiFi", "駐車場", "クレジットカード可"],  // 施設の特徴
      "tags": ["観光名所", "歴史", "写真映え"],  // 一般的なタグ
      "source_index": 0
    }}
  ]
}}

注意:
- 情報が不明な場合はnullまたは空文字を使用
- 価格帯(price_level)は1〜4の整数で推定
- 特徴(features)は施設の設備やサービス
- タグ(tags)は体験や雰囲気に関するキーワード"""

        gateway = self._get_gateway()
        result = await gateway.generate_json(
            prompt=prompt,
            tier=self._get_tier_for_model(model),
            worker_host=worker_host,
            model_override=model,
            temperature=0.3,
            agent_name="search_poi_extractor",
        )

        pois_data = result.get("pois", [])
        extracted: list[POISearchResult] = []

        for poi_data in pois_data:
            name = poi_data.get("name", "")
            if not name:
                continue

            # source_indexから元の検索結果を参照
            source_idx = poi_data.get("source_index", 0)
            if 0 <= source_idx < len(raw_results):
                source = raw_results[source_idx]
                source_url = source.get("url", "")
                relevance_score = source.get("score", 0.5)
            else:
                source_url = ""
                relevance_score = 0.5

            # PTS形式のフィールドを抽出
            extracted.append(
                POISearchResult(
                    # 基本情報
                    name=name,
                    category=category,
                    description=poi_data.get("description", "")[:300],
                    # 位置情報
                    location=poi_data.get("location", ""),
                    address=poi_data.get("address", ""),
                    latitude=poi_data.get("latitude"),
                    longitude=poi_data.get("longitude"),
                    # 評価・レビュー情報（PTS形式）
                    rating=poi_data.get("rating"),
                    review_count=poi_data.get("review_count"),
                    # 価格情報
                    price_level=poi_data.get("price_level"),
                    price_range=poi_data.get("price_range", ""),
                    budget_per_person=poi_data.get("budget_per_person"),
                    # 時間情報
                    opening_hours=poi_data.get("hours", ""),
                    duration_minutes=poi_data.get("duration_minutes"),
                    # 特徴・タグ（PTS形式）
                    features=poi_data.get("features", []),
                    tags=poi_data.get("tags", []),
                    # ソース情報
                    source_url=source_url,
                    relevance_score=relevance_score,
                    source_name="tavily+llm",
                )
            )

        return extracted

    async def _verify(
        self,
        category: POICategory,
        destination: str,
        constraints: TravelConstraints,
        wishes: TravelWishes,
        items: list[POISearchResult],
        hints: list[str],
        worker_host: str,
        model: str,
    ) -> SearchVerdict:
        """LLMで検索結果を評価"""
        items_summary = []
        for item in items[:15]:
            items_summary.append({
                "name": item.name,
                "description": item.description[:100] if item.description else "",
                "tags": item.tags[:3] if item.tags else [],
            })

        hints_text = ""
        if hints:
            hints_text = f"\n注意すべき追加要件: {', '.join(hints)}"

        prompt = f"""以下の検索結果が「{category.value}」カテゴリとして十分かどうか評価してください。

目的地: {destination}
カテゴリ: {category.value}
日数: {constraints.duration_days or '未定'}
希望: {json.dumps(wishes.model_dump(), ensure_ascii=False, default=str)}
{hints_text}

検索結果 ({len(items)}件):
{json.dumps(items_summary, ensure_ascii=False)}

JSON形式で評価してください:
{{"sufficient": true/false, "reason": "理由", "missing_aspects": ["不足している観点"], "suggested_queries": ["追加の検索クエリ"]}}"""

        try:
            gateway = self._get_gateway()
            result = await gateway.generate_json(
                prompt=prompt,
                tier=self._get_tier_for_model(model),
                worker_host=worker_host,
                model_override=model,
                temperature=0.3,
                agent_name="search_verifier",
            )
            return SearchVerdict(**result)
        except Exception as e:
            logger.warning(f"Verify step failed for {category.value}: {e}")
            # エラー時はsufficient=Trueで続行（無限ループ防止）
            return SearchVerdict(sufficient=True, reason=f"Verification failed: {e}")

    @staticmethod
    def _get_tier_for_model(model: str) -> "ModelTier":
        """モデル名からティアを推定"""
        from app.services.llm_gateway import ModelTier
        if "32b" in model or "qwen" in model.lower():
            return ModelTier.HEAVY
        elif "embed" in model.lower() or "nomic" in model.lower():
            return ModelTier.EMBED
        return ModelTier.LIGHT


def _get_agent_for_category(category: POICategory) -> BaseSearchAgent:
    """カテゴリに対応するエージェントを取得"""
    agents = {
        POICategory.ACTIVITY: ActivitySearchAgent(),
        POICategory.FOOD: FoodSearchAgent(),
        POICategory.HOTEL: HotelSearchAgent(),
        POICategory.TRANSPORTATION: TransportationSearchAgent(),
    }
    return agents[category]


# =============================================================================
# 並列検索ヘルパー
# =============================================================================


@dataclass
class SearchAllResult:
    """全カテゴリ検索の結果"""

    results: dict  # POICategory -> SearchResult
    status: SearchStatus


async def search_all_categories(
    destination: str,
    constraints: dict | None = None,
    keywords: dict[str, list[str]] | None = None,
    raise_on_all_failed: bool = True,
) -> SearchAllResult:
    """
    4カテゴリを並列で検索（レガシー互換: SearchReasoningLoopを使わないシンプル版）

    CLAUDE.md 8.7: 1-2エージェント失敗時は残りの結果で続行

    Args:
        destination: 目的地
        constraints: 制約条件
        keywords: カテゴリごとのキーワード
        raise_on_all_failed: 全エージェント失敗時に例外を発生させるか

    Returns:
        SearchAllResult: 検索結果とステータス

    Raises:
        SearchAllFailedError: 全エージェントが失敗した場合（raise_on_all_failed=True時）
    """
    constraints = constraints or {}
    keywords = keywords or {}

    # クエリを構築
    categories_queries = [
        (POICategory.ACTIVITY, SearchQuery(
            category=POICategory.ACTIVITY,
            destination=destination,
            keywords=keywords.get("activity", []),
            constraints=constraints,
        )),
        (POICategory.FOOD, SearchQuery(
            category=POICategory.FOOD,
            destination=destination,
            keywords=keywords.get("food", []),
            constraints=constraints,
        )),
        (POICategory.HOTEL, SearchQuery(
            category=POICategory.HOTEL,
            destination=destination,
            keywords=keywords.get("hotel", []),
            constraints=constraints,
        )),
        (POICategory.TRANSPORTATION, SearchQuery(
            category=POICategory.TRANSPORTATION,
            destination=destination,
            keywords=keywords.get("transportation", []),
            constraints=constraints,
        )),
    ]

    # エージェントを作成して並列実行
    agents = {
        POICategory.ACTIVITY: ActivitySearchAgent(),
        POICategory.FOOD: FoodSearchAgent(),
        POICategory.HOTEL: HotelSearchAgent(),
        POICategory.TRANSPORTATION: TransportationSearchAgent(),
    }

    tasks = [
        agents[cat].search(query)
        for cat, query in categories_queries
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 結果を整理
    output = {}
    status = SearchStatus(total_categories=4)
    result_pairs = [
        (categories_queries[i][0], results[i])
        for i in range(len(categories_queries))
    ]

    for category, result in result_pairs:
        category_name = category.value
        if isinstance(result, Exception):
            logger.error(f"Search failed for {category_name}: {result}")
            status.failed_categories.append(category_name)
            status.error_messages[category_name] = str(result)
            output[category] = SearchResult(
                category=category,
                query=destination,
                items=[],
                source="tavily",
                search_time_ms=0,
            )
        else:
            # 結果が空でも成功とみなす（検索自体は成功）
            status.successful_categories.append(category_name)
            status.total_results += len(result.items)
            output[category] = result

    # ステータスを更新
    status.all_failed = len(status.failed_categories) == status.total_categories
    status.partial_failure = (
        len(status.failed_categories) > 0 and not status.all_failed
    )

    # ログ出力
    if status.all_failed:
        logger.error(
            f"All search agents failed for destination={destination}"
        )
        if raise_on_all_failed:
            raise SearchAllFailedError(
                details={
                    "destination": destination,
                    "errors": status.error_messages,
                }
            )
    elif status.partial_failure:
        logger.warning(
            f"Partial search failure for destination={destination}: "
            f"failed={status.failed_categories}, "
            f"successful={status.successful_categories}"
        )
    else:
        logger.info(
            f"All search agents succeeded for destination={destination}: "
            f"total_results={status.total_results}"
        )

    return SearchAllResult(results=output, status=status)


async def search_with_reasoning(
    destination: str,
    constraints: TravelConstraints,
    wishes: TravelWishes,
    categories: list[POICategory] | None = None,
    hints_per_category: dict[str, list[str]] | None = None,
    max_iterations: int = 2,
) -> SearchAllResult:
    """
    SearchReasoningLoopを使った4カテゴリ並列検索（Phase 1）

    各カテゴリに対して専用サーバーを割り当て、
    REASON → SEARCH → VERIFY のループを実行する。

    Args:
        destination: 目的地
        constraints: 旅行制約
        wishes: 旅行希望
        categories: 検索対象カテゴリ（None=全4カテゴリ）
        hints_per_category: カテゴリごとの追加ヒント（Phase 2からの指示）
        max_iterations: 最大ループ回数

    Returns:
        SearchAllResult: 検索結果とステータス
    """
    if categories is None:
        categories = [
            POICategory.ACTIVITY,
            POICategory.FOOD,
            POICategory.HOTEL,
            POICategory.TRANSPORTATION,
        ]
    hints_per_category = hints_per_category or {}

    # search_routing設定を読み込み
    search_routing = _load_search_routing()

    # デフォルトルーティング（設定がない場合）
    import os
    search_model = os.getenv("OLLAMA_MODEL_HEAVY", "qwen2.5:32b-instruct")
    default_routing = {
        "activity": {
            "host": os.getenv("OLLAMA_WORKER_HEAVY", "172.28.208.214:11434"),
            "model": search_model,
        },
        "food": {
            "host": os.getenv("OLLAMA_WORKER_LIGHT", "172.28.208.217:11434"),
            "model": search_model,
        },
        "hotel": {
            "host": os.getenv("OLLAMA_WORKER_EMBED", "172.28.208.218:11434"),
            "model": search_model,
        },
        "transportation": {
            "host": os.getenv("OLLAMA_WORKER_MAFU", "172.28.208.213:11434"),
            "model": search_model,
        },
    }

    reasoning_loop = SearchReasoningLoop()

    # 各カテゴリのタスクを作成
    tasks = []
    task_categories = []
    for category in categories:
        cat_key = category.value
        routing = search_routing.get(cat_key, default_routing.get(cat_key, {}))
        worker_host = routing.get("host", "localhost:11434")
        model = routing.get("model", "qwen2.5:32b-instruct")
        hints = hints_per_category.get(cat_key, [])

        tasks.append(
            reasoning_loop.execute(
                category=category,
                destination=destination,
                constraints=constraints,
                wishes=wishes,
                worker_host=worker_host,
                model=model,
                hints=hints,
                max_iterations=max_iterations,
            )
        )
        task_categories.append(category)

    # 並列実行
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 結果を整理
    output = {}
    status = SearchStatus(total_categories=len(categories))

    for i, category in enumerate(task_categories):
        result = results[i]
        category_name = category.value
        if isinstance(result, Exception):
            logger.error(f"Reasoning search failed for {category_name}: {result}")
            status.failed_categories.append(category_name)
            status.error_messages[category_name] = str(result)
            output[category] = SearchResult(
                category=category,
                query=destination,
                items=[],
                source="tavily+reasoning",
                search_time_ms=0,
            )
        else:
            status.successful_categories.append(category_name)
            status.total_results += len(result.items)
            output[category] = result

    status.all_failed = len(status.failed_categories) == status.total_categories
    status.partial_failure = (
        len(status.failed_categories) > 0 and not status.all_failed
    )

    if status.all_failed:
        logger.error(f"All reasoning search loops failed for destination={destination}")
    elif status.partial_failure:
        logger.warning(
            f"Partial reasoning search failure: failed={status.failed_categories}"
        )
    else:
        logger.info(
            f"All reasoning search loops succeeded: total_results={status.total_results}"
        )

    return SearchAllResult(results=output, status=status)


# Singleton instances
activity_search_agent = ActivitySearchAgent()
food_search_agent = FoodSearchAgent()
hotel_search_agent = HotelSearchAgent()
transportation_search_agent = TransportationSearchAgent()
