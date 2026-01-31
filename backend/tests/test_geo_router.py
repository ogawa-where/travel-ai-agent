"""Geo ルーター エンドポイント テスト"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_geocode_endpoint(client):
    """POST /api/geo/geocode - 正常系"""
    with patch(
        "app.routers.geo._geocoder.geocode_poi",
        new_callable=AsyncMock,
        return_value=(35.6762, 139.6503),
    ):
        response = client.post(
            "/api/geo/geocode",
            json={
                "poi_name": "東京タワー",
                "location": "港区",
                "destination": "東京",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert abs(data["latitude"] - 35.6762) < 0.001
    assert abs(data["longitude"] - 139.6503) < 0.001


def test_geocode_not_found(client):
    """POST /api/geo/geocode - 見つからない場合"""
    with patch(
        "app.routers.geo._geocoder.geocode_poi",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.post(
            "/api/geo/geocode",
            json={"poi_name": "存在しない場所"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is False
    assert data["latitude"] is None


def test_route_endpoint(client):
    """POST /api/geo/route - 正常系"""
    with patch(
        "app.routers.geo._osrm.route",
        new_callable=AsyncMock,
        return_value={
            "distance": 5432.1,
            "duration": 720.5,
            "geometry": {
                "type": "LineString",
                "coordinates": [[139.65, 35.67], [139.70, 35.68]],
            },
        },
    ):
        response = client.post(
            "/api/geo/route",
            json={"coordinates": [[35.67, 139.65], [35.68, 139.70]]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["distance_km"] == 5.43
    assert data["duration_minutes"] == 12.0
    assert data["geometry"]["type"] == "LineString"


def test_enrich_itinerary_endpoint(client):
    """POST /api/geo/enrich-itinerary - 旅程ジオ情報付与"""
    itinerary = {
        "title": "東京2日間の旅",
        "summary": "東京の魅力を体験",
        "days": [
            {
                "day_number": 1,
                "items": [
                    {
                        "time_start": "09:00",
                        "time_end": "11:00",
                        "poi": {
                            "name": "浅草寺",
                            "category": "activity",
                            "location": "台東区浅草",
                            "description": "東京最古の寺院",
                        },
                        "notes": "",
                    },
                    {
                        "time_start": "12:00",
                        "time_end": "13:00",
                        "poi": {
                            "name": "月島もんじゃストリート",
                            "category": "food",
                            "location": "中央区月島",
                            "description": "もんじゃ焼きの名所",
                        },
                        "notes": "",
                    },
                ],
                "accommodation": None,
            }
        ],
    }

    with (
        patch(
            "app.routers.geo._geocoder.geocode_poi",
            new_callable=AsyncMock,
            side_effect=[
                (35.7148, 139.7967),  # 浅草寺
                (35.6625, 139.7822),  # 月島
            ],
        ),
        patch(
            "app.routers.geo._osrm.route",
            new_callable=AsyncMock,
            return_value={
                "distance": 7200.0,
                "duration": 1200.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [139.7967, 35.7148],
                        [139.7822, 35.6625],
                    ],
                },
            },
        ),
    ):
        response = client.post(
            "/api/geo/enrich-itinerary",
            json={"itinerary": itinerary, "destination": "東京"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["days"]) == 1

    day1 = data["days"][0]
    assert day1["day_number"] == 1
    assert len(day1["pois"]) == 2

    # POI にlat/lonが付与されている
    assert day1["pois"][0]["latitude"] is not None
    assert day1["pois"][0]["longitude"] is not None
    assert day1["pois"][1]["latitude"] is not None

    # ルートが計算されている
    assert day1["route_geometry"] is not None
    assert day1["total_distance_km"] == 7.2
    assert day1["total_duration_minutes"] == 20.0


def test_enrich_itinerary_partial_geocode(client):
    """一部POIのジオコーディングが失敗した場合もgraceful"""
    itinerary = {
        "days": [
            {
                "day_number": 1,
                "items": [
                    {
                        "poi": {
                            "name": "Known Place",
                            "category": "activity",
                            "location": "Tokyo",
                            "description": "",
                        },
                    },
                    {
                        "poi": {
                            "name": "Unknown Place",
                            "category": "activity",
                            "location": "",
                            "description": "",
                        },
                    },
                ],
                "accommodation": None,
            }
        ],
    }

    with (
        patch(
            "app.routers.geo._geocoder.geocode_poi",
            new_callable=AsyncMock,
            side_effect=[
                (35.6762, 139.6503),  # Known Place
                None,  # Unknown Place
            ],
        ),
        patch(
            "app.routers.geo._osrm.route",
            new_callable=AsyncMock,
            return_value=None,  # 1点しかないのでルートなし
        ),
    ):
        response = client.post(
            "/api/geo/enrich-itinerary",
            json={"itinerary": itinerary, "destination": "東京"},
        )

    assert response.status_code == 200
    data = response.json()
    day1 = data["days"][0]
    # 1つ目は見つかった
    assert day1["pois"][0]["latitude"] is not None
    # 2つ目は見つからなかった
    assert day1["pois"][1]["latitude"] is None
