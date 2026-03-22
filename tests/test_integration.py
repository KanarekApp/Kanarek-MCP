"""Integration tests — live API calls. Run with KANAREK_INTEGRATION_TEST=1."""

import os

import pytest

from kanarek_mcp.server import (
    find_stations,
    get_air_quality,
    get_air_quality_rankings,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("KANAREK_INTEGRATION_TEST") != "1",
    reason="Set KANAREK_INTEGRATION_TEST=1 to run integration tests",
)


@pytest.mark.asyncio
async def test_get_air_quality_warsaw():
    result = await get_air_quality(city="Warsaw")
    assert "PM2.5" in result or "PM10" in result
    assert "station" in result.lower()


@pytest.mark.asyncio
async def test_find_stations_krakow():
    result = await find_stations(query="Kraków")
    assert "Kraków" in result or "Krakow" in result
    assert "ID:" in result


@pytest.mark.asyncio
async def test_rankings():
    result = await get_air_quality_rankings()
    assert "pm25" in result.lower()
    assert "Rankings" in result
