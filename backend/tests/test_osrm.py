"""OSRM クライアント テスト"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.osrm_client import OSRMClient


@pytest.fixture
def osrm():
    return OSRMClient(base_url="http://localhost:5000")


def _mock_response(json_data, status_code=200):
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://localhost:5000/route/v1/driving/"),
    )
    return response


@pytest.mark.asyncio
async def test_route_success(osrm):
    """正常なルート計算"""
    mock_data = {
        "code": "Ok",
        "routes": [
            {
                "distance": 5432.1,
                "duration": 720.5,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[139.65, 35.67], [139.70, 35.68]],
                },
            }
        ],
    }

    with patch("app.services.osrm_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(mock_data))
        mock_client_cls.return_value = mock_client

        result = await osrm.route([(35.67, 139.65), (35.68, 139.70)])

    assert result is not None
    assert result["distance"] == 5432.1
    assert result["duration"] == 720.5
    assert result["geometry"]["type"] == "LineString"


@pytest.mark.asyncio
async def test_route_insufficient_coordinates(osrm):
    """座標が2点未満の場合はNone"""
    result = await osrm.route([(35.67, 139.65)])
    assert result is None

    result = await osrm.route([])
    assert result is None


@pytest.mark.asyncio
async def test_route_no_route_found(osrm):
    """ルートが見つからない場合"""
    mock_data = {"code": "NoRoute", "routes": []}

    with patch("app.services.osrm_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(mock_data))
        mock_client_cls.return_value = mock_client

        result = await osrm.route([(35.67, 139.65), (35.68, 139.70)])

    assert result is None


@pytest.mark.asyncio
async def test_route_connection_error(osrm):
    """接続エラー時はNone"""
    with patch("app.services.osrm_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client_cls.return_value = mock_client

        result = await osrm.route([(35.67, 139.65), (35.68, 139.70)])

    assert result is None


@pytest.mark.asyncio
async def test_table_success(osrm):
    """正常な距離行列計算"""
    mock_data = {
        "code": "Ok",
        "durations": [[0, 300], [300, 0]],
        "distances": [[0, 5000], [5000, 0]],
    }

    with patch("app.services.osrm_client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(mock_data))
        mock_client_cls.return_value = mock_client

        result = await osrm.table([(35.67, 139.65), (35.68, 139.70)])

    assert result is not None
    assert len(result["durations"]) == 2
    assert len(result["distances"]) == 2


@pytest.mark.asyncio
async def test_table_insufficient_coordinates(osrm):
    """座標が2点未満はNone"""
    result = await osrm.table([(35.67, 139.65)])
    assert result is None
