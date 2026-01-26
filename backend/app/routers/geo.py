"""ジオコーディング・ルーティング API エンドポイント"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.geocoder import NominatimGeocoder
from app.services.osrm_client import OSRMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/geo", tags=["geo"])

# サービスインスタンス（シングルトン：キャッシュ共有のため）
_geocoder = NominatimGeocoder()
_osrm = OSRMClient()


# =============================================================================
# リクエスト/レスポンススキーマ
# =============================================================================


class GeocodeRequest(BaseModel):
    """ジオコーディングリクエスト"""

    poi_name: str
    location: str = ""
    destination: str = ""


class GeocodeResponse(BaseModel):
    """ジオコーディングレスポンス"""

    poi_name: str
    latitude: float | None = None
    longitude: float | None = None
    found: bool = False


class RouteRequest(BaseModel):
    """ルート計算リクエスト"""

    coordinates: list[list[float]] = Field(
        ..., description="[[lat, lon], ...] 最低2点"
    )


class RouteResponse(BaseModel):
    """ルート計算レスポンス"""

    distance_km: float | None = None
    duration_minutes: float | None = None
    geometry: dict | None = None  # GeoJSON LineString


class GeoEnrichedPOI(BaseModel):
    """ジオ情報付きPOI"""

    name: str
    category: str
    latitude: float | None = None
    longitude: float | None = None
    description: str = ""


class GeoEnrichedDay(BaseModel):
    """ジオ情報付き1日分"""

    day_number: int
    pois: list[GeoEnrichedPOI] = Field(default_factory=list)
    route_geometry: dict | None = None  # GeoJSON LineString
    total_distance_km: float | None = None
    total_duration_minutes: float | None = None


class GeoEnrichedItinerary(BaseModel):
    """ジオ情報付き旅程"""

    days: list[GeoEnrichedDay] = Field(default_factory=list)


class EnrichItineraryRequest(BaseModel):
    """旅程ジオ情報付与リクエスト"""

    itinerary: dict  # Itinerary JSON
    destination: str = ""


# =============================================================================
# エンドポイント
# =============================================================================


@router.post("/geocode", response_model=GeocodeResponse)
async def geocode_poi(request: GeocodeRequest) -> GeocodeResponse:
    """単一POIのジオコーディング"""
    result = await _geocoder.geocode_poi(
        poi_name=request.poi_name,
        location=request.location,
        destination=request.destination,
    )
    if result:
        return GeocodeResponse(
            poi_name=request.poi_name,
            latitude=result[0],
            longitude=result[1],
            found=True,
        )
    return GeocodeResponse(poi_name=request.poi_name, found=False)


@router.post("/route", response_model=RouteResponse)
async def calculate_route(request: RouteRequest) -> RouteResponse:
    """座標列のルート計算"""
    coords = [(c[0], c[1]) for c in request.coordinates]
    result = await _osrm.route(coords)
    if result:
        return RouteResponse(
            distance_km=round(result["distance"] / 1000, 2),
            duration_minutes=round(result["duration"] / 60, 1),
            geometry=result["geometry"],
        )
    return RouteResponse()


@router.post("/enrich-itinerary", response_model=GeoEnrichedItinerary)
async def enrich_itinerary(request: EnrichItineraryRequest) -> GeoEnrichedItinerary:
    """旅程全体にジオ情報（緯度経度・ルート）を付与する

    1. 全POIをジオコーディング
    2. 日ごとにOSRMルート計算
    """
    itinerary = request.itinerary
    destination = request.destination
    enriched_days: list[GeoEnrichedDay] = []

    days = itinerary.get("days", [])
    for day in days:
        day_number = day.get("day_number", 0)
        items = day.get("items", [])
        accommodation = day.get("accommodation")

        # 全POIを収集（items + accommodation）
        pois_to_geocode: list[dict] = []
        for item in items:
            poi = item.get("poi", {})
            if poi:
                pois_to_geocode.append(poi)
        if accommodation:
            pois_to_geocode.append(accommodation)

        # ジオコーディング
        enriched_pois: list[GeoEnrichedPOI] = []
        coords_for_route: list[tuple[float, float]] = []

        for poi in pois_to_geocode:
            name = poi.get("name", "")
            location = poi.get("location", "")
            category = poi.get("category", "")
            description = poi.get("description", "")

            # 既にlat/lonがある場合はそのまま使う
            lat = poi.get("latitude")
            lon = poi.get("longitude")

            if lat is None or lon is None:
                result = await _geocoder.geocode_poi(
                    poi_name=name,
                    location=location,
                    destination=destination,
                )
                if result:
                    lat, lon = result

            enriched_poi = GeoEnrichedPOI(
                name=name,
                category=category,
                latitude=lat,
                longitude=lon,
                description=description,
            )
            enriched_pois.append(enriched_poi)

            if lat is not None and lon is not None:
                coords_for_route.append((lat, lon))

        # ルート計算（2点以上ある場合のみ）
        route_geometry = None
        total_distance_km = None
        total_duration_minutes = None

        if len(coords_for_route) >= 2:
            route_result = await _osrm.route(coords_for_route)
            if route_result:
                route_geometry = route_result["geometry"]
                total_distance_km = round(route_result["distance"] / 1000, 2)
                total_duration_minutes = round(route_result["duration"] / 60, 1)

        enriched_days.append(
            GeoEnrichedDay(
                day_number=day_number,
                pois=enriched_pois,
                route_geometry=route_geometry,
                total_distance_km=total_distance_km,
                total_duration_minutes=total_duration_minutes,
            )
        )

    return GeoEnrichedItinerary(days=enriched_days)
