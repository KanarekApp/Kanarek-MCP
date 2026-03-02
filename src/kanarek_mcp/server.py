"""Kanarek MCP server — air quality tools for AI assistants."""

import asyncio
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from kanarek_mcp.api_client import KanarekClient
from kanarek_mcp.formatters import (
    format_air_quality,
    format_calendar,
    format_comparison,
    format_config,
    format_history,
    format_ranking_details,
    format_rankings_list,
    format_station_details,
    format_stations,
)

mcp = FastMCP("kanarek")
_client: KanarekClient | None = None


def _get_client() -> KanarekClient:
    global _client
    if _client is None or _client.is_closed:
        _client = KanarekClient()
    return _client


def _error_response(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Not found. Check the ID or search term and try again."
        if status == 422:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            return f"Invalid request: {detail}"
        return f"API error (HTTP {status}). Please try again later."
    if isinstance(e, httpx.ConnectError):
        return "Cannot reach the Kanarek API. Check your internet connection."
    return f"Error: {e}"


async def _search_city_coords(client: KanarekClient, city: str) -> dict[str, float] | None:
    """Search for a city and return coordinates of the top result."""
    data = await client.get("/search/stations", params={"q": city})
    if not data:
        return None
    results = data.get("results") or []
    if not results:
        return None
    loc = results[0].get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    if lat is not None and lng is not None:
        return {"lat": lat, "lng": lng}
    return None


async def _resolve_station_id(client: KanarekClient, city: str) -> str | None:
    """Resolve a city name to a station ID, preferring GIOŚ stations."""
    data = await client.get("/search/stations", params={"q": city})
    if not data:
        return None
    results = data.get("results") or []
    # Prefer GIOŚ station for reliable history data
    for r in results:
        if r.get("provider_name") == "gios":
            return r.get("id")
    # Fall back to first result
    return results[0].get("id") if results else None


@mcp.tool()
async def get_air_quality(
    city: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 10,
    pollutant: str | None = None,
) -> str:
    """Get current air quality for a location. Provide either a city name or coordinates.

    Args:
        city: City name to search for (e.g. "Warsaw", "Kraków")
        latitude: Latitude of the location
        longitude: Longitude of the location
        radius_km: Search radius in km (default: 10)
        pollutant: Filter to specific pollutant (pm25, pm10, no2, o3, so2, co)
    """
    try:
        client = _get_client()
        if city:
            coords = await _search_city_coords(client, city)
            if not coords:
                return f"No stations found for \"{city}\". Try a different spelling or use coordinates."
        elif latitude is not None and longitude is not None:
            coords = {"lat": latitude, "lng": longitude}
        else:
            return "Please provide either a city name or latitude+longitude coordinates."

        data = await client.get(
            "/stations/nearby",
            params={**coords, "radius_km": radius_km, "include_averages": "true"},
        )
        if not data or not data.get("stations"):
            return f"No stations found within {radius_km} km of the location."
        return format_air_quality(data, pollutant)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
async def compare_air_quality(
    cities: list[str],
    pollutant: str = "pm25",
) -> str:
    """Compare air quality across multiple cities (2-5).

    Args:
        cities: List of city names to compare (2-5 cities)
        pollutant: Pollutant to compare (default: pm25). Options: pm25, pm10, no2, o3, so2, co
    """
    if len(cities) < 2:
        return "Please provide at least 2 cities to compare."
    if len(cities) > 5:
        return "Please provide at most 5 cities to compare."

    try:
        client = _get_client()

        async def fetch_city(city: str) -> tuple[str, dict[str, Any] | None]:
            coords = await _search_city_coords(client, city)
            if not coords:
                return city, None
            data = await client.get(
                "/stations/nearby",
                params={**coords, "radius_km": 10, "include_averages": "true"},
            )
            return city, data

        results = await asyncio.gather(*[fetch_city(c) for c in cities])
        city_results = dict(results)
        return format_comparison(city_results, pollutant)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
async def get_air_quality_history(
    pollutant: str = "pm25",
    period: str = "7d",
    city: str | None = None,
    station_id: str | None = None,
    year: int | None = None,
) -> str:
    """Get historical air quality data for a station.

    Args:
        pollutant: Measurement type (default: pm25). Options: pm25, pm10, no2, o3, so2, co
        period: Time period — "24h", "7d", "30d", or "year" (requires year param)
        city: City name — will resolve to best available station
        station_id: Specific station ID (use find_stations to discover IDs)
        year: Year for calendar view (e.g. 2025). Sets period to "year" automatically.
    """
    try:
        client = _get_client()

        if year:
            period = "year"

        # Resolve station ID
        sid = station_id
        if not sid:
            if city:
                sid = await _resolve_station_id(client, city)
                if not sid:
                    return f"No stations found for \"{city}\"."
            else:
                return "Please provide either a city name or a station_id."

        # Fetch station info for context
        station_info = await client.get(f"/stations/{sid}")

        if period == "year":
            if not year:
                year = 2025
            data = await client.get(
                f"/stations/{sid}/calendar",
                params={"measurement_type": pollutant, "year": year},
            )
            if not data:
                return "No calendar data available for this station."
            return format_calendar(data, station_info)
        else:
            data = await client.get(
                f"/stations/{sid}/history",
                params={"measurement_type": pollutant, "period": period},
            )
            if not data:
                return "No history data available for this station."
            return format_history(data, station_info)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
async def get_air_quality_rankings(
    ranking_type: str = "city",
    pollutant: str = "pm25",
    period: str = "24h",
    limit: int = 10,
    identifier: str | None = None,
) -> str:
    """Get air quality rankings by city or station.

    Args:
        ranking_type: "city" or "station" (default: city)
        pollutant: Pollutant to rank by (default: pm25). Options: pm25, pm10, no2, o3
        period: Time period — "1h", "8h", or "24h" (default: 24h)
        limit: Number of results (default: 10, max: 50)
        identifier: City or station identifier for detail view (e.g. "Warszawa-POL")
    """
    try:
        client = _get_client()

        if identifier:
            data = await client.get(
                f"/rankings/{ranking_type}/{identifier}/details",
                params={"substance": pollutant, "period": period},
            )
            if not data:
                return f"No ranking details found for \"{identifier}\"."
            return format_ranking_details(data)
        else:
            data = await client.get(
                "/rankings",
                params={
                    "type": ranking_type,
                    "substance": pollutant,
                    "period": period,
                    "limit": limit,
                },
            )
            if not data:
                return "No rankings available."
            return format_rankings_list(data)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
async def find_stations(
    query: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 10,
    provider: str | None = None,
    limit: int = 10,
) -> str:
    """Find air quality monitoring stations by name/city or location.

    Args:
        query: Search term (city name, street, station name)
        latitude: Latitude for location-based search
        longitude: Longitude for location-based search
        radius_km: Search radius in km (default: 10, only for coordinate search)
        provider: Filter by provider (gios, luftdaten, looko2, blebox, airly)
        limit: Max results (default: 10)
    """
    try:
        client = _get_client()

        if query:
            params: dict[str, Any] = {"q": query, "limit": limit}
            if provider:
                params["provider"] = provider
            data = await client.get("/search/stations", params=params)
        elif latitude is not None and longitude is not None:
            params = {"lat": latitude, "lng": longitude, "radius_km": radius_km, "limit": limit}
            if provider:
                params["provider"] = provider
            data = await client.get("/stations/nearby", params=params)
        else:
            return "Please provide either a search query or latitude+longitude coordinates."

        if not data:
            return "No stations found."
        return format_stations(data)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
async def get_station_details(station_id: str) -> str:
    """Get detailed information and current measurements for a specific station.

    Args:
        station_id: Station UUID (use find_stations to discover IDs)
    """
    try:
        client = _get_client()
        data = await client.get(
            f"/stations/{station_id}", params={"include_24h_avg": "true"}
        )
        if not data:
            return f"Station \"{station_id}\" not found."
        return format_station_details(data)
    except Exception as e:
        return _error_response(e)


@mcp.resource("kanarek://config")
async def config_resource() -> str:
    """Reference data: measurement types, WHO guidelines, and data providers."""
    try:
        client = _get_client()
        data = await client.get("/config")
        if not data:
            return "Config not available."
        return format_config(data)
    except Exception as e:
        return _error_response(e)


def main() -> None:
    """Entry point for the kanarek-mcp server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
