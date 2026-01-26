"""NominatimGeocoder テスト"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.geocoder import NominatimGeocoder


@pytest.fixture
def geocoder():
    return NominatimGeocoder()


def _mock_response(json_data, status_code=200):
    """httpx.Response モックを作成"""
    response = httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "https://nominatim.openstreetmap.org/search"),
    )
    return response


@pytest.mark.asyncio
async def test_geocode_success(geocoder):
    """正常なジオコーディング結果"""
    mock_result = [{"lat": "35.6762", "lon": "139.6503"}]

    with patch("app.services.geocoder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(mock_result))
        mock_client_cls.return_value = mock_client

        result = await geocoder.geocode("東京タワー")

    assert result is not None
    assert abs(result[0] - 35.6762) < 0.001
    assert abs(result[1] - 139.6503) < 0.001


@pytest.mark.asyncio
async def test_geocode_not_found(geocoder):
    """検索結果なしの場合"""
    with patch("app.services.geocoder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response([]))
        mock_client_cls.return_value = mock_client

        result = await geocoder.geocode("存在しない場所xyz123")

    assert result is None


@pytest.mark.asyncio
async def test_geocode_cache(geocoder):
    """キャッシュが効くこと"""
    mock_result = [{"lat": "35.6762", "lon": "139.6503"}]

    with patch("app.services.geocoder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(mock_result))
        mock_client_cls.return_value = mock_client

        # 1回目
        result1 = await geocoder.geocode("東京タワー")
        # 2回目（キャッシュから）
        result2 = await geocoder.geocode("東京タワー")

    assert result1 == result2
    # HTTP呼び出しは1回だけ
    assert mock_client.get.call_count == 1


@pytest.mark.asyncio
async def test_geocode_poi_staged_queries(geocoder):
    """段階的クエリ: 1つ目が失敗して2つ目で成功"""
    call_count = 0
    mock_result = [{"lat": "34.6937", "lon": "135.5023"}]

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        query = kwargs.get("params", {}).get("q", "")
        # 最初のクエリは結果なし、2つ目で見つかる
        if "大阪" in query and "城" not in query:
            return _mock_response(mock_result)
        return _mock_response([])

    with patch("app.services.geocoder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        mock_client_cls.return_value = mock_client

        result = await geocoder.geocode_poi(
            poi_name="某城",
            location="某所",
            destination="大阪",
        )

    assert result is not None


@pytest.mark.asyncio
async def test_geocode_http_error(geocoder):
    """HTTP エラー時は None"""
    with patch("app.services.geocoder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client_cls.return_value = mock_client

        result = await geocoder.geocode("東京タワー")

    assert result is None
