"""Nominatim (OSM) ジオコーディングクライアント"""

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "travel-ai-agent/1.0")
# Nominatim usage policy: max 1 request per second
RATE_LIMIT_SECONDS = 1.1


class NominatimGeocoder:
    """Nominatim APIを使ったジオコーディング（レート制限・キャッシュ付き）"""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, float]] = {}
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def _rate_limit(self) -> None:
        """Nominatim利用規約に従い、リクエスト間隔を制限する"""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_SECONDS:
                await asyncio.sleep(RATE_LIMIT_SECONDS - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()

    async def geocode(
        self, query: str, country_codes: str = "jp"
    ) -> tuple[float, float] | None:
        """住所・名称から緯度経度を取得する

        Args:
            query: 検索クエリ（住所、施設名など）
            country_codes: 国コード（デフォルト: jp）

        Returns:
            (latitude, longitude) or None if not found
        """
        if query in self._cache:
            return self._cache[query]

        await self._rate_limit()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    NOMINATIM_BASE_URL,
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 1,
                        "countrycodes": country_codes,
                    },
                    headers={"User-Agent": NOMINATIM_USER_AGENT},
                )
                response.raise_for_status()
                results = response.json()

            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                self._cache[query] = (lat, lon)
                logger.debug("Geocoded '%s' -> (%f, %f)", query, lat, lon)
                return (lat, lon)

            logger.debug("No geocoding result for '%s'", query)
            return None

        except (httpx.HTTPError, KeyError, ValueError, IndexError) as e:
            logger.warning("Geocoding failed for '%s': %s", query, e)
            return None

    async def geocode_poi(
        self, poi_name: str, location: str, destination: str
    ) -> tuple[float, float] | None:
        """POI情報から段階的にジオコーディングを試行する

        試行順序:
        1. "{poi_name} {location}"
        2. "{poi_name} {destination}"
        3. "{location} {destination}"

        Args:
            poi_name: POI名
            location: POIの所在地
            destination: 旅行先の地域名

        Returns:
            (latitude, longitude) or None if all queries fail
        """
        queries = []
        if poi_name and location:
            queries.append(f"{poi_name} {location}")
        if poi_name and destination:
            queries.append(f"{poi_name} {destination}")
        if location and destination:
            queries.append(f"{location} {destination}")
        # fallback: name only
        if poi_name:
            queries.append(poi_name)

        for query in queries:
            result = await self.geocode(query)
            if result is not None:
                return result

        logger.info(
            "All geocoding attempts failed for POI: %s (location=%s, dest=%s)",
            poi_name,
            location,
            destination,
        )
        return None
