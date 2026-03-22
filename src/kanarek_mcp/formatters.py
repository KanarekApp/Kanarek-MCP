"""Format API responses into concise text for LLMs."""

from datetime import datetime, timezone
from typing import Any

# WHO 2021 daily guidelines (µg/m³)
WHO_GUIDELINES: dict[str, float] = {
    "pm25": 15.0,
    "pm10": 45.0,
    "no2": 25.0,
    "o3": 100.0,
}

UNITS: dict[str, str] = {
    "pm25": "µg/m³",
    "pm10": "µg/m³",
    "no2": "µg/m³",
    "o3": "µg/m³",
    "so2": "µg/m³",
    "co": "µg/m³",
    "no": "µg/m³",
    "nox": "µg/m³",
    "benzene": "µg/m³",
    "temperature": "°C",
    "humidity": "%",
    "pressure": "hPa",
}


def _unit(measurement_type: str) -> str:
    return UNITS.get(measurement_type, "µg/m³")


def _who_comparison(measurement_type: str, value: float) -> str:
    guideline = WHO_GUIDELINES.get(measurement_type)
    if guideline is None:
        return ""
    ratio = value / guideline
    if ratio <= 1.0:
        return f" (within WHO guideline of {guideline} {_unit(measurement_type)})"
    return f" ({ratio:.1f}x WHO guideline of {guideline} {_unit(measurement_type)})"


def _freshness(timestamp_str: str | None) -> str:
    if not timestamp_str:
        return ""
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - ts
        minutes = int(age.total_seconds() / 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except (ValueError, TypeError):
        return ""


def format_air_quality(data: dict[str, Any], pollutant: str | None = None) -> str:
    """Format nearby stations response into air quality summary."""
    lines: list[str] = []
    location = data.get("location", {})
    lat = location.get("latitude", "?")
    lng = location.get("longitude", "?")
    radius = data.get("radius_km", "?")

    averages = data.get("weighted_averages") or {}
    stations = data.get("stations") or []

    if averages:
        lines.append("Area average (distance-weighted):")
        for mt, val in sorted(averages.items()):
            if pollutant and mt != pollutant:
                continue
            lines.append(f"  {mt}: {val:.1f} {_unit(mt)}{_who_comparison(mt, val)}")
        lines.append(f"  Based on {data.get('average_station_count', len(stations))} stations within {radius} km")
        lines.append("")

    if stations:
        lines.append("Nearby stations:")
        display = stations[:10]
        for s in display:
            dist = s.get("distance_km", 0)
            name = s.get("name", "Unknown")
            provider = s.get("provider_name", "")
            freshness = _freshness(s.get("last_updated"))
            measurements = s.get("latest_measurements") or {}

            if pollutant and pollutant in measurements:
                val = measurements[pollutant]
                lines.append(f"  {name} ({provider}, {dist:.1f} km) — {pollutant}: {val} {_unit(pollutant)}{_who_comparison(pollutant, val)} [{freshness}]")
            else:
                parts = [f"{k}: {v} {_unit(k)}" for k, v in sorted(measurements.items())]
                meas_str = ", ".join(parts) if parts else "no data"
                lines.append(f"  {name} ({provider}, {dist:.1f} km) — {meas_str} [{freshness}]")

        remaining = len(stations) - len(display)
        if remaining > 0:
            lines.append(f"  ...and {remaining} more stations")

    if not averages and not stations:
        lines.append(f"No stations found within {radius} km of ({lat}, {lng}).")

    return "\n".join(lines)


def format_comparison(
    city_results: dict[str, dict[str, Any] | None], pollutant: str
) -> str:
    """Format multi-city comparison sorted worst-first."""
    lines: list[str] = []
    entries: list[tuple[str, float, int]] = []
    not_found: list[str] = []

    for city, data in city_results.items():
        if data is None:
            not_found.append(city)
            continue
        averages = data.get("weighted_averages") or {}
        val = averages.get(pollutant)
        if val is not None:
            station_count = data.get("average_station_count", 0)
            entries.append((city, val, station_count))
        else:
            not_found.append(city)

    entries.sort(key=lambda x: x[1], reverse=True)

    lines.append(f"Air quality comparison — {pollutant} ({_unit(pollutant)}):")
    lines.append("")
    for i, (city, val, count) in enumerate(entries, 1):
        lines.append(f"  {i}. {city}: {val:.1f} {_unit(pollutant)}{_who_comparison(pollutant, val)} ({count} stations)")
    if not_found:
        lines.append(f"\n  No data for: {', '.join(not_found)}")

    return "\n".join(lines)


def format_history(data: dict[str, Any], station_info: dict[str, Any] | None = None) -> str:
    """Format history response with trend analysis."""
    lines: list[str] = []
    mt = data.get("measurement_type", "?")
    period = data.get("period", "?")
    points = data.get("data_points") or []

    station_name = ""
    if station_info:
        station_name = station_info.get("name", "")

    if station_name:
        lines.append(f"History for {station_name}")
    lines.append(f"Measurement: {mt} ({_unit(mt)}), period: {period}")
    lines.append("")

    if not points:
        lines.append("No data available for this period.")
        return "\n".join(lines)

    values = [p["value"] for p in points if p.get("value") is not None]
    if values:
        avg = sum(values) / len(values)
        mn, mx = min(values), max(values)
        lines.append(f"Summary: avg {avg:.1f}, min {mn:.1f}, max {mx:.1f} {_unit(mt)}{_who_comparison(mt, avg)}")

        # Trend: compare first third vs last third
        third = max(1, len(values) // 3)
        first_avg = sum(values[:third]) / third
        last_avg = sum(values[-third:]) / third
        diff = last_avg - first_avg
        if abs(diff) < 0.5:
            lines.append("Trend: stable")
        elif diff > 0:
            lines.append(f"Trend: increasing (+{diff:.1f})")
        else:
            lines.append(f"Trend: decreasing ({diff:.1f})")
        lines.append(f"Data points: {len(values)}")
        lines.append("")

    # Show recent points (last 12)
    recent = points[-12:]
    lines.append("Recent readings:")
    for p in recent:
        ts = p.get("timestamp", "")
        val = p.get("value")
        if val is not None:
            ts_short = ts[5:16].replace("T", " ") if len(ts) >= 16 else ts
            lines.append(f"  {ts_short}: {val:.1f} {_unit(mt)}")

    return "\n".join(lines)


def format_calendar(data: dict[str, Any], station_info: dict[str, Any] | None = None) -> str:
    """Format calendar (yearly daily averages) with monthly summaries."""
    lines: list[str] = []
    mt = data.get("measurement_type", "?")
    year = data.get("year", "?")
    days = data.get("days") or []

    station_name = ""
    if station_info:
        station_name = station_info.get("name", "")

    if station_name:
        lines.append(f"Calendar for {station_name}")
    lines.append(f"Measurement: {mt} ({_unit(mt)}), year: {year}")
    lines.append("")

    if not days:
        lines.append("No data available for this year.")
        return "\n".join(lines)

    # Group by month
    months: dict[str, list[float]] = {}
    all_values: list[tuple[str, float]] = []
    for d in days:
        date = d.get("date", "")
        val = d.get("avg_value")
        if val is not None:
            month_key = date[:7]  # YYYY-MM
            months.setdefault(month_key, []).append(val)
            all_values.append((date, val))

    if all_values:
        vals = [v for _, v in all_values]
        avg = sum(vals) / len(vals)
        lines.append(f"Year summary: avg {avg:.1f}, min {min(vals):.1f}, max {max(vals):.1f} {_unit(mt)}{_who_comparison(mt, avg)}")
        lines.append(f"Days with data: {len(all_values)}")

        guideline = WHO_GUIDELINES.get(mt)
        if guideline:
            exceedances = sum(1 for v in vals if v > guideline)
            lines.append(f"Days exceeding WHO guideline: {exceedances}/{len(vals)}")
        lines.append("")

    lines.append("Monthly averages:")
    for month_key in sorted(months.keys()):
        vals = months[month_key]
        avg = sum(vals) / len(vals)
        lines.append(f"  {month_key}: {avg:.1f} {_unit(mt)} ({len(vals)} days)")

    # Worst/best days
    if len(all_values) >= 2:
        sorted_days = sorted(all_values, key=lambda x: x[1], reverse=True)
        lines.append("")
        lines.append("Worst days:")
        for date, val in sorted_days[:5]:
            lines.append(f"  {date}: {val:.1f} {_unit(mt)}")
        lines.append("Best days:")
        for date, val in sorted_days[-5:]:
            lines.append(f"  {date}: {val:.1f} {_unit(mt)}")

    return "\n".join(lines)


def format_rankings_list(data: dict[str, Any]) -> str:
    """Format rankings list as a ranked table."""
    lines: list[str] = []
    ranking_type = data.get("type", "?")
    substance = data.get("substance", "?")
    period = data.get("period", "?")
    rankings = data.get("rankings") or []

    lines.append(f"Rankings — {substance} ({_unit(substance)}), {ranking_type}, period: {period}")
    lines.append("")

    if not rankings:
        lines.append("No rankings available.")
        return "\n".join(lines)

    for r in rankings:
        rank = r.get("rank", "?")
        name = r.get("name", "?")
        country = r.get("country_code", "")
        avg = r.get("average_value", 0)
        count = r.get("station_count", 0)
        place_id = r.get("place_id", "")
        lines.append(f"  {rank}. {name} ({country}) — {avg:.1f} {_unit(substance)}{_who_comparison(substance, avg)} [{count} stations] place_id: {place_id}")

    total = data.get("total_calculated")
    if total:
        lines.append(f"\nShowing {len(rankings)} of {total} entries.")

    return "\n".join(lines)


def format_place_details(data: dict[str, Any]) -> str:
    """Format place detail view with air quality and ranking info."""
    lines: list[str] = []
    name = data.get("name", "?")
    level = data.get("level", "?")
    country = data.get("country_code", "")
    station_count = data.get("station_count", 0)

    lines.append(f"{name} ({level}{', ' + country if country else ''})")
    lines.append(f"Stations: {station_count}")

    # Hierarchy
    hierarchy = data.get("hierarchy") or []
    if hierarchy:
        path = " > ".join(h.get("name", "?") for h in reversed(hierarchy))
        lines.append(f"Location: {path}")

    lines.append("")

    # Air quality
    aq = data.get("air_quality")
    if aq:
        lines.append("Current air quality:")
        pm25 = aq.get("pm25_avg")
        pm10 = aq.get("pm10_avg")
        if pm25 is not None:
            lines.append(f"  PM2.5: {pm25:.1f} {_unit('pm25')}{_who_comparison('pm25', pm25)}")
        if pm10 is not None:
            lines.append(f"  PM10: {pm10:.1f} {_unit('pm10')}{_who_comparison('pm10', pm10)}")
        aq_stations = aq.get("station_count")
        if aq_stations:
            lines.append(f"  Based on {aq_stations} stations")
        lines.append("")

    # Ranking
    ranking = data.get("ranking")
    if ranking:
        substance = ranking.get("substance", "?")
        period = ranking.get("period", "?")
        avg = ranking.get("average_value", 0)
        rank = ranking.get("rank", "?")
        total = ranking.get("total", "?")
        lines.append(f"Ranking ({substance}, {period}):")
        lines.append(f"  Average: {avg:.1f} {_unit(substance)}{_who_comparison(substance, avg)}")
        lines.append(f"  Rank: {rank} of {total}")

    return "\n".join(lines)


def format_stations(data: dict[str, Any]) -> str:
    """Format station search or nearby results as a list with IDs."""
    lines: list[str] = []

    # Handle search results
    results = data.get("results") or data.get("stations") or []

    if data.get("query"):
        lines.append(f"Search results for \"{data['query']}\":")
    elif data.get("location"):
        loc = data["location"]
        lines.append(f"Stations near ({loc.get('latitude')}, {loc.get('longitude')}):")
    else:
        lines.append("Stations:")
    lines.append("")

    if not results:
        lines.append("No stations found.")
        return "\n".join(lines)

    display = results[:15]
    for s in display:
        sid = s.get("id", "?")
        name = s.get("name", "?")
        provider = s.get("provider_name", "?")
        city = s.get("city") or (s.get("address") or {}).get("city", "")
        dist = s.get("distance_km")

        parts = [f"ID: {sid}", f"provider: {provider}"]
        if city:
            parts.append(f"city: {city}")
        if dist is not None:
            parts.append(f"{dist:.1f} km")

        lines.append(f"  {name}")
        lines.append(f"    {', '.join(parts)}")

    remaining = len(results) - len(display)
    if remaining > 0:
        lines.append(f"  ...and {remaining} more stations")

    count = data.get("count", len(results))
    lines.append(f"\nTotal: {count}")

    return "\n".join(lines)


def format_station_details(data: dict[str, Any]) -> str:
    """Format single station details with all measurements."""
    lines: list[str] = []
    name = data.get("name", "?")
    provider = data.get("provider_name", "?")
    address = data.get("address") or {}
    location = data.get("location") or {}

    lines.append(f"Station: {name}")
    lines.append(f"Provider: {provider}")

    addr_parts = []
    for key in ["street", "house_number", "city", "district", "state"]:
        if address.get(key):
            addr_parts.append(address[key])
    if addr_parts:
        lines.append(f"Address: {', '.join(addr_parts)}")

    lat = location.get("latitude")
    lng = location.get("longitude")
    if lat and lng:
        lines.append(f"Coordinates: {lat}, {lng}")

    freshness = _freshness(data.get("last_updated"))
    if freshness:
        lines.append(f"Last updated: {freshness}")
    lines.append("")

    # Latest measurements
    latest = data.get("measurements_latest") or {}
    avg_24h = data.get("measurements_24h_avg") or {}

    if latest or avg_24h:
        lines.append("Measurements:")
        all_types = sorted(set(list(latest.keys()) + list(avg_24h.keys())))
        for mt in all_types:
            parts = []
            if mt in latest:
                entry = latest[mt]
                val = entry.get("value") if isinstance(entry, dict) else entry
                parts.append(f"current: {val} {_unit(mt)}")
            if mt in avg_24h:
                parts.append(f"24h avg: {avg_24h[mt]} {_unit(mt)}")

            who = ""
            val_for_who = avg_24h.get(mt) or (latest.get(mt, {}).get("value") if isinstance(latest.get(mt), dict) else latest.get(mt))
            if val_for_who is not None:
                who = _who_comparison(mt, val_for_who)

            lines.append(f"  {mt}: {', '.join(parts)}{who}")
    else:
        lines.append("No measurements available.")

    return "\n".join(lines)


def format_config(data: dict[str, Any]) -> str:
    """Format config/reference data as text."""
    lines: list[str] = []

    # Measurement types
    mt = data.get("measurement_types") or {}
    if mt:
        lines.append("Measurement types:")
        for key, info in sorted(mt.items()):
            name = info.get("display_name", key)
            unit = info.get("unit", "")
            cat = info.get("category", "")
            lines.append(f"  {key}: {name} ({unit}) [{cat}]")
        lines.append("")

    # WHO norms
    norms = data.get("norms") or {}
    who = norms.get("who_2021") or {}
    if who:
        lines.append(f"WHO 2021 guidelines:")
        limits = who.get("limits") or {}
        for substance, periods in sorted(limits.items()):
            if isinstance(periods, dict):
                parts = [f"{p}: {v}" for p, v in periods.items()]
                lines.append(f"  {substance}: {', '.join(parts)}")
        lines.append("")

    # Providers
    providers = data.get("providers") or []
    if providers:
        lines.append("Data providers:")
        for p in providers:
            name = p.get("display_name") or p.get("name", "?")
            count = p.get("station_count", 0)
            active = "active" if p.get("is_active") else "inactive"
            lines.append(f"  {name}: {count} stations ({active})")

    return "\n".join(lines)
