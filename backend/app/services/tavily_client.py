"""
Tavily検索サービス

外部検索API (Tavily) との連携を担当。
CLAUDE.md セクション7のコンプライアンス要件を遵守。
"""

import asyncio
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


class TavilyClient:
    """Tavily検索APIクライアント"""

    def __init__(self):
        self.api_key = os.getenv("TAVILY_API_KEY", "")
        self._rate_limit_delay = 1.0  # レート制限（秒）
        self._last_request_time = 0.0
        self._timeout = 30.0  # タイムアウト（秒）

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 10,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Tavily APIで検索を実行

        Args:
            query: 検索クエリ
            search_depth: 検索深度 ("basic" or "advanced")
            max_results: 最大結果数
            include_domains: 含めるドメインリスト
            exclude_domains: 除外するドメインリスト

        Returns:
            検索結果
        """
        if not self.api_key:
            logger.warning("TAVILY_API_KEY not set, returning empty results")
            return {"results": [], "query": query, "error": "API key not configured"}

        # レート制限
        await self._apply_rate_limit()

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                payload = {
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": search_depth,
                    "max_results": max_results,
                    "include_answer": False,
                    "include_raw_content": False,
                }

                if include_domains:
                    payload["include_domains"] = include_domains
                if exclude_domains:
                    payload["exclude_domains"] = exclude_domains

                response = await client.post(TAVILY_API_URL, json=payload)
                response.raise_for_status()

                result = response.json()
                elapsed_ms = int((time.time() - start_time) * 1000)

                logger.info(
                    f"Tavily search completed: query='{query[:50]}...' "
                    f"results={len(result.get('results', []))} "
                    f"time={elapsed_ms}ms"
                )

                return {
                    "results": result.get("results", []),
                    "query": query,
                    "search_time_ms": elapsed_ms,
                }

        except httpx.TimeoutException:
            logger.error(f"Tavily search timeout: query='{query}'")
            return {"results": [], "query": query, "error": "Search timeout"}
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Tavily API error: {e.response.status_code} - {e.response.text}"
            )
            return {
                "results": [],
                "query": query,
                "error": f"API error: {e.response.status_code}",
            }
        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return {"results": [], "query": query, "error": str(e)}

    async def search_for_travel(
        self,
        destination: str,
        category: str,
        keywords: list[str] | None = None,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """
        旅行関連の検索を実行

        Args:
            destination: 目的地
            category: カテゴリ (activity, food, hotel)
            keywords: 追加キーワード
            max_results: 最大結果数

        Returns:
            検索結果
        """
        # カテゴリに応じたクエリ構築
        category_terms = {
            "activity": "観光 体験 アクティビティ おすすめ",
            "food": "グルメ レストラン 食事 おすすめ",
            "hotel": "ホテル 宿泊 旅館 おすすめ",
            "transportation": "交通 アクセス 移動手段 電車 バス タクシー レンタカー",
        }

        base_terms = category_terms.get(category, "観光")
        keyword_str = " ".join(keywords) if keywords else ""

        query = f"{destination} {base_terms} {keyword_str}".strip()

        # 旅行系ドメインを優先
        include_domains = [
            "tripadvisor.jp",
            "jalan.net",
            "ikyu.com",
            "travel.rakuten.co.jp",
            "rurubu.travel",
            "jtb.co.jp",
        ]

        return await self.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_domains=include_domains,
        )

    async def _apply_rate_limit(self):
        """レート制限を適用"""
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)

        self._last_request_time = time.time()


# Singleton instance
tavily_client = TavilyClient()
