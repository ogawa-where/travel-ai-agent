"""OSRM (Open Source Routing Machine) クライアント"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

OSRM_BASE_URL = os.getenv("OSRM_BASE_URL", "http://osrm:5000")


class OSRMClient:
    """OSRM APIクライアント（ルート計算・距離行列）"""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or OSRM_BASE_URL).rstrip("/")

    async def route(
        self, coordinates: list[tuple[float, float]]
    ) -> dict | None:
        """座標列からルートを計算する

        Args:
            coordinates: [(lat, lon), ...] 最低2点

        Returns:
            {
                "distance": float (meters),
                "duration": float (seconds),
                "geometry": GeoJSON dict
            }
            or None if route not found / error
        """
        if len(coordinates) < 2:
            logger.warning("Route requires at least 2 coordinates, got %d", len(coordinates))
            return None

        # OSRM expects lon,lat order
        coords_str = ";".join(
            f"{lon},{lat}" for lat, lon in coordinates
        )
        url = f"{self.base_url}/route/v1/driving/{coords_str}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={
                        "overview": "full",
                        "geometries": "geojson",
                    },
                )
                response.raise_for_status()
                data = response.json()

            if data.get("code") != "Ok" or not data.get("routes"):
                logger.warning("OSRM route not found: %s", data.get("code"))
                return None

            route = data["routes"][0]
            return {
                "distance": route["distance"],  # meters
                "duration": route["duration"],  # seconds
                "geometry": route["geometry"],  # GeoJSON LineString
            }

        except (httpx.HTTPError, KeyError, ValueError, IndexError) as e:
            logger.warning("OSRM route request failed: %s", e)
            return None

    async def table(
        self, coordinates: list[tuple[float, float]]
    ) -> dict | None:
        """座標列間の距離・時間行列を計算する

        Args:
            coordinates: [(lat, lon), ...] 最低2点

        Returns:
            {
                "durations": [[float, ...], ...] (seconds),
                "distances": [[float, ...], ...] (meters)
            }
            or None if error
        """
        if len(coordinates) < 2:
            return None

        coords_str = ";".join(
            f"{lon},{lat}" for lat, lon in coordinates
        )
        url = f"{self.base_url}/table/v1/driving/{coords_str}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    params={"annotations": "duration,distance"},
                )
                response.raise_for_status()
                data = response.json()

            if data.get("code") != "Ok":
                logger.warning("OSRM table failed: %s", data.get("code"))
                return None

            return {
                "durations": data.get("durations", []),
                "distances": data.get("distances", []),
            }

        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning("OSRM table request failed: %s", e)
            return None
