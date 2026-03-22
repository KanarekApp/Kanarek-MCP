"""Unit tests for kanarek-mcp tools with mocked HTTP responses."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from kanarek_mcp.server import (
    compare_air_quality,
    find_stations,
    get_air_quality,
    get_air_quality_history,
    get_air_quality_rankings,
    get_station_details,
)

# --- Fixtures / sample data ---

PLACE_SEARCH_RESPONSE = {
    "query": "Warsaw",
    "results": [
        {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "name": "Warszawa",
            "slug": "warszawa-pol",
            "level": "city",
            "country_code": "POL",
        }
    ],
    "count": 1,
    "timestamp": "2026-03-02T12:00:00",
}

PLACE_RESPONSE = {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "name": "Warszawa",
    "slug": "warszawa-pol",
    "level": "city",
    "country_code": "POL",
    "parent": {"id": "pppppppp-0000-0000-0000-000000000000", "name": "Mazowieckie", "slug": "mazowieckie-pol", "level": "state"},
    "station_count": 160,
    "hierarchy": [
        {"id": "pppppppp-0000-0000-0000-000000000000", "name": "Mazowieckie", "slug": "mazowieckie-pol", "level": "state"},
        {"id": "cccccccc-0000-0000-0000-000000000000", "name": "Polska", "slug": "polska", "level": "country"},
    ],
    "air_quality": {"pm25_avg": 12.1, "pm10_avg": 25.4, "station_count": 45},
    "ranking": {"rank": 223, "total": 466, "substance": "pm25", "period": "24h", "average_value": 12.1},
}

SEARCH_RESPONSE = {
    "query": "Warsaw",
    "results": [
        {
            "id": "1f8138aa-3092-4bb4-9ee0-23b0638de32b",
            "name": "Polska, Warszawa, aleja Niepodległości 229",
            "provider_name": "gios",
            "provider_station_id": "530",
            "location": {"latitude": 52.2193, "longitude": 21.00472, "geohash": "u3qcjfppm"},
            "city": "Warszawa",
            "country_code": "POL",
            "district": "Śródmieście",
            "street": "aleja Niepodległości",
            "match_type": "city",
            "match_score": 0.5,
        }
    ],
    "count": 1,
    "timestamp": "2026-03-02T12:00:00",
}

NEARBY_RESPONSE = {
    "location": {"latitude": 52.2193, "longitude": 21.00472},
    "radius_km": 10.0,
    "stations": [
        {
            "id": "1f8138aa-3092-4bb4-9ee0-23b0638de32b",
            "name": "Polska, Warszawa, aleja Niepodległości 229",
            "provider_name": "gios",
            "provider_station_id": "530",
            "location": {"latitude": 52.2193, "longitude": 21.00472},
            "address": {"country_code": "POL", "city": "Warszawa", "district": "Śródmieście"},
            "distance_km": 0.5,
            "latest_measurements": {"pm25": 15.2, "pm10": 32.1},
            "last_updated": "2026-03-02T12:00:00Z",
        },
        {
            "id": "c3861181-ee16-4e45-8921-faa8d1fd02e8",
            "name": "Polska, Warszawa, plac Grzybowski 14",
            "provider_name": "luftdaten",
            "provider_station_id": "17261",
            "location": {"latitude": 52.236, "longitude": 21.002},
            "address": {"country_code": "POL", "city": "Warszawa", "district": "Śródmieście"},
            "distance_km": 1.8,
            "latest_measurements": {"pm25": 8.5, "pm10": 18.0},
            "last_updated": "2026-03-02T11:50:00Z",
        },
    ],
    "count": 2,
    "weighted_averages": {"pm25": 12.1, "pm10": 25.4},
    "average_station_count": 2,
    "timestamp": "2026-03-02T12:00:00",
}

STATION_DETAIL_RESPONSE = {
    "id": "1f8138aa-3092-4bb4-9ee0-23b0638de32b",
    "provider_name": "gios",
    "name": "Polska, Warszawa, aleja Niepodległości 229",
    "location": {"latitude": 52.2193, "longitude": 21.00472, "geohash": "u3qcjfppm"},
    "address": {
        "country_code": "POL",
        "city": "Warszawa",
        "district": "Śródmieście",
        "street": "aleja Niepodległości",
        "house_number": "229",
    },
    "latest_measurements": {},
    "last_updated": "2026-03-02T12:00:00Z",
    "measurements_24h_avg": {"pm25": 14.3, "pm10": 35.8},
    "measurements_latest": {
        "pm25": {"value": 23.4, "timestamp": "2026-03-02T12:00:00+00:00"},
        "pm10": {"value": 54.4, "timestamp": "2026-03-02T12:00:00+00:00"},
    },
    "provider_station_id": "530",
    "created_at": "2026-01-09T05:35:18.928439Z",
}

HISTORY_RESPONSE = {
    "station_id": "1f8138aa-3092-4bb4-9ee0-23b0638de32b",
    "measurement_type": "pm25",
    "period": "7d",
    "data_points": [
        {"timestamp": "2026-02-24T00:00:00Z", "value": 10.4, "avg_value": 10.4, "min_value": 10.4, "max_value": 10.4},
        {"timestamp": "2026-02-24T01:00:00Z", "value": 11.8, "avg_value": 11.8, "min_value": 11.8, "max_value": 11.8},
        {"timestamp": "2026-02-24T02:00:00Z", "value": 15.0, "avg_value": 15.0, "min_value": 15.0, "max_value": 15.0},
        {"timestamp": "2026-02-24T03:00:00Z", "value": 8.2, "avg_value": 8.2, "min_value": 8.2, "max_value": 8.2},
    ],
}

STATION_CALENDAR_RESPONSE = {
    "station_id": "1f8138aa-3092-4bb4-9ee0-23b0638de32b",
    "measurement_type": "pm25",
    "year": 2025,
    "days": [
        {"date": "2025-01-01", "avg_value": 44.0},
        {"date": "2025-01-02", "avg_value": 19.0},
        {"date": "2025-01-03", "avg_value": 10.0},
        {"date": "2025-02-01", "avg_value": 30.0},
        {"date": "2025-02-02", "avg_value": 12.0},
    ],
    "count": 5,
}

PLACE_CALENDAR_RESPONSE = {
    "place": {"id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "name": "Warszawa", "slug": "warszawa-pol", "level": "city"},
    "year": 2025,
    "substance": "pm25",
    "station_count": 45,
    "days": [
        {"date": "2025-01-01", "avg_value": 38.0},
        {"date": "2025-01-02", "avg_value": 22.0},
        {"date": "2025-01-03", "avg_value": 14.0},
        {"date": "2025-02-01", "avg_value": 28.0},
        {"date": "2025-02-02", "avg_value": 10.0},
    ],
}

RANKINGS_RESPONSE = {
    "type": "city",
    "substance": "pm25",
    "period": "24h",
    "rankings": [
        {
            "rank": 1,
            "name": "Kraków",
            "identifier": "Kraków-POL",
            "place_id": "11111111-1111-1111-1111-111111111111",
            "place_slug": "krakow-pol",
            "country_code": "POL",
            "average_value": 45.5,
            "station_count": 20,
            "station_values": [60.0, 50.0, 40.0, 30.0],
        },
        {
            "rank": 2,
            "name": "Warszawa",
            "identifier": "Warszawa-POL",
            "place_id": "22222222-2222-2222-2222-222222222222",
            "place_slug": "warszawa-pol",
            "country_code": "POL",
            "average_value": 25.0,
            "station_count": 160,
            "station_values": [30.0, 25.0, 20.0],
        },
    ],
    "total_calculated": 2,
    "returned_count": 2,
    "timestamp": "2026-03-02T12:00:00",
}

PLACE_DETAIL_RESPONSE = {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "name": "Warszawa",
    "slug": "warszawa-pol",
    "level": "city",
    "country_code": "POL",
    "parent": {"id": "pppppppp-0000-0000-0000-000000000000", "name": "Mazowieckie", "slug": "mazowieckie-pol", "level": "state"},
    "station_count": 160,
    "hierarchy": [
        {"id": "pppppppp-0000-0000-0000-000000000000", "name": "Mazowieckie", "slug": "mazowieckie-pol", "level": "state"},
        {"id": "cccccccc-0000-0000-0000-000000000000", "name": "Polska", "slug": "polska", "level": "country"},
    ],
    "air_quality": {"pm25_avg": 11.3, "pm10_avg": 25.4, "station_count": 45},
    "ranking": {"rank": 223, "total": 466, "substance": "pm25", "period": "24h", "average_value": 11.3},
}


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "https://test.example.com"),
    )


def _mock_client(side_effects: list) -> AsyncMock:
    """Create a mock KanarekClient with sequential get() responses."""
    mock = AsyncMock()
    mock.get = AsyncMock(side_effect=side_effects)
    return mock


# --- Tests ---


@pytest.fixture(autouse=True)
def reset_client():
    """Reset the global client before each test."""
    import kanarek_mcp.server as srv
    srv._client = None
    yield
    srv._client = None


class TestGetAirQuality:
    @pytest.mark.asyncio
    async def test_city_via_places(self):
        """Test city name → places search → place detail."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([PLACE_SEARCH_RESPONSE, PLACE_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality(city="Warsaw")

            assert "Warszawa" in result
            assert "12.1" in result  # pm25_avg
            assert "25.4" in result  # pm10_avg
            assert "PM2.5" in result
            assert "PM10" in result
            assert "#223" in result  # ranking
            assert client.get.call_count == 2
            # Verify calls: places/search then places/{id}
            assert "/places/search" in str(client.get.call_args_list[0])
            assert "/places/" in str(client.get.call_args_list[1])

    @pytest.mark.asyncio
    async def test_coordinates_flow(self):
        """Test direct coordinate lookup still uses nearby stations."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([NEARBY_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality(latitude=52.23, longitude=21.01)

            assert "pm25" in result
            assert "Area average" in result
            assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_no_params(self):
        result = await get_air_quality()
        assert "provide" in result.lower()

    @pytest.mark.asyncio
    async def test_city_not_found(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([{"query": "xyz", "results": [], "count": 0}])
            mock_gc.return_value = client

            result = await get_air_quality(city="NonexistentCity")
            assert "No location found" in result

    @pytest.mark.asyncio
    async def test_api_connection_error(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = AsyncMock()
            client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_gc.return_value = client

            result = await get_air_quality(city="Warsaw")
            assert "Cannot reach" in result


class TestCompareAirQuality:
    @pytest.mark.asyncio
    async def test_two_cities(self):
        """Test places-based comparison."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            # Each city: places/search + places/{id} = 4 calls
            krakow_place_search = {
                "query": "Kraków",
                "results": [{"id": "kk-id", "name": "Kraków", "slug": "krakow-pol", "level": "city", "country_code": "POL"}],
                "count": 1,
            }
            krakow_place = {
                "id": "kk-id",
                "name": "Kraków",
                "slug": "krakow-pol",
                "level": "city",
                "country_code": "POL",
                "station_count": 20,
                "hierarchy": [],
                "air_quality": {"pm25_avg": 45.5, "pm10_avg": 60.0, "station_count": 20},
                "ranking": {"rank": 1, "total": 466, "substance": "pm25", "period": "24h", "average_value": 45.5},
            }
            client = _mock_client([
                PLACE_SEARCH_RESPONSE, PLACE_RESPONSE,
                krakow_place_search, krakow_place,
            ])
            mock_gc.return_value = client

            result = await compare_air_quality(cities=["Warsaw", "Kraków"])

            assert "comparison" in result.lower()
            assert "pm25" in result
            assert "Kraków" in result
            assert "Warszawa" in result
            assert "Rank #" in result

    @pytest.mark.asyncio
    async def test_too_few_cities(self):
        result = await compare_air_quality(cities=["Warsaw"])
        assert "at least 2" in result

    @pytest.mark.asyncio
    async def test_too_many_cities(self):
        result = await compare_air_quality(cities=["a", "b", "c", "d", "e", "f"])
        assert "at most 5" in result


class TestGetAirQualityHistory:
    @pytest.mark.asyncio
    async def test_city_history_period(self):
        """Test city + period still uses station-based history."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([SEARCH_RESPONSE, STATION_DETAIL_RESPONSE, HISTORY_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality_history(city="Warsaw", period="7d")

            assert "pm25" in result
            assert "Summary" in result
            assert "Trend" in result

    @pytest.mark.asyncio
    async def test_city_yearly_calendar_via_places(self):
        """Test city + year uses place calendar for city-wide data."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([PLACE_SEARCH_RESPONSE, PLACE_CALENDAR_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality_history(city="Warsaw", year=2025)

            assert "2025" in result
            assert "Warszawa" in result
            assert "Monthly" in result
            assert "Stations contributing data: 45" in result
            assert client.get.call_count == 2
            # Verify it called places/search then places/{id}/calendar
            assert "/places/search" in str(client.get.call_args_list[0])
            assert "/calendar" in str(client.get.call_args_list[1])

    @pytest.mark.asyncio
    async def test_station_calendar(self):
        """Test station_id + year uses station calendar."""
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([STATION_DETAIL_RESPONSE, STATION_CALENDAR_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality_history(
                station_id="1f8138aa-3092-4bb4-9ee0-23b0638de32b",
                year=2025,
            )

            assert "2025" in result
            assert "Monthly" in result
            assert "Worst" in result

    @pytest.mark.asyncio
    async def test_no_station_or_city(self):
        result = await get_air_quality_history()
        assert "provide" in result.lower()


class TestGetAirQualityRankings:
    @pytest.mark.asyncio
    async def test_list_rankings(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([RANKINGS_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality_rankings()

            assert "Kraków" in result
            assert "Warszawa" in result
            assert "45.5" in result
            assert "place_id:" in result

    @pytest.mark.asyncio
    async def test_place_detail(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([PLACE_DETAIL_RESPONSE])
            mock_gc.return_value = client

            result = await get_air_quality_rankings(place_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

            assert "Warszawa" in result
            assert "223" in result
            assert "11.3" in result
            assert "city" in result


class TestFindStations:
    @pytest.mark.asyncio
    async def test_search_by_query(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([SEARCH_RESPONSE])
            mock_gc.return_value = client

            result = await find_stations(query="Warsaw")

            assert "Niepodległości" in result
            assert "1f8138aa" in result  # station ID shown

    @pytest.mark.asyncio
    async def test_search_by_coords(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([NEARBY_RESPONSE])
            mock_gc.return_value = client

            result = await find_stations(latitude=52.23, longitude=21.01)

            assert "Stations" in result

    @pytest.mark.asyncio
    async def test_no_params(self):
        result = await find_stations()
        assert "provide" in result.lower()


class TestGetStationDetails:
    @pytest.mark.asyncio
    async def test_station_details(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([STATION_DETAIL_RESPONSE])
            mock_gc.return_value = client

            result = await get_station_details(station_id="1f8138aa-3092-4bb4-9ee0-23b0638de32b")

            assert "Niepodległości" in result
            assert "gios" in result
            assert "pm25" in result
            assert "24h avg" in result

    @pytest.mark.asyncio
    async def test_station_not_found(self):
        with patch("kanarek_mcp.server._get_client") as mock_gc:
            client = _mock_client([None])
            mock_gc.return_value = client

            result = await get_station_details(station_id="nonexistent")
            assert "not found" in result.lower()
