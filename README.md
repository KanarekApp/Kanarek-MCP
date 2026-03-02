<h1 align="center">kanarek-mcp</h1>

<p align="center">
  <strong>Real-time air quality data for AI assistants</strong><br>
  An <a href="https://modelcontextprotocol.io">MCP</a> server that connects Claude, Cursor, VS Code, and other AI tools<br>to live readings from <strong>15,000+ monitoring stations</strong> across Poland and Europe.
</p>

<p align="center">
  <a href="https://github.com/KanarekApp/Kanarek-MCP"><img src="https://img.shields.io/github/stars/KanarekApp/Kanarek-MCP" alt="GitHub stars"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python versions">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-CC%20BY--NC--ND%204.0-blue" alt="License"></a>
</p>

---

## Why kanarek-mcp?

Ask your AI assistant about air quality and get **real answers with real data** — not a disclaimer about not having internet access.

```
You:    "Is it safe to go jogging in Kraków right now?"

Claude: Based on current readings from 45 stations in Kraków, PM2.5 is at
        38.2 µg/m³ (2.5x the WHO guideline of 15 µg/m³). I'd recommend
        moving your run indoors or waiting — air quality has been improving
        over the past few hours and should drop below guidelines by evening.
```

**No API keys. No configuration. Just install and ask.**

---

## Features

- **Current readings** — PM2.5, PM10, NO2, O3, SO2, CO, and weather data from nearby stations
- **City comparisons** — side-by-side air quality across up to 5 cities
- **Historical trends** — hourly data (24h/7d/30d) with trend analysis, or yearly calendar view
- **Pollution rankings** — worst/best cities and stations ranked by any pollutant
- **Station search** — find stations by city, street name, or GPS coordinates
- **WHO guidelines** — every reading compared against WHO 2021 air quality guidelines
- **Multiple data providers** — GIOŚ (government), Airly, Luftdaten, LookO2, BleBox, and more

---

## Installation

### Claude Desktop

Add to your config file:

| OS | Config path |
|----|-------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "kanarek": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/KanarekApp/Kanarek-MCP.git", "kanarek-mcp"]
    }
  }
}
```

### Claude Code (CLI)

Run in your project directory:

```bash
claude mcp add kanarek -- uvx --from "git+https://github.com/KanarekApp/Kanarek-MCP.git" kanarek-mcp
```

### VS Code

Add to your `.vscode/mcp.json` (create the file if it doesn't exist):

```json
{
  "servers": {
    "kanarek": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/KanarekApp/Kanarek-MCP.git", "kanarek-mcp"]
    }
  }
}
```

### Cursor

Open **Settings** > **MCP Servers** > **Add Server**, then use:

```json
{
  "kanarek": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/KanarekApp/Kanarek-MCP.git", "kanarek-mcp"]
  }
}
```

### Other MCP clients

kanarek-mcp works with any client that supports the [Model Context Protocol](https://modelcontextprotocol.io). It runs locally via **stdio** transport — just point your client to:

```
uvx --from "git+https://github.com/KanarekApp/Kanarek-MCP.git" kanarek-mcp
```

---

## What can you ask?

Once installed, just talk to your AI assistant naturally. Here are some examples:

### Current air quality

> "What's the air quality in Warsaw?"
>
> "Is it safe to take my kids to the park in Wrocław?"
>
> "What are the PM2.5 levels near latitude 52.23, longitude 21.01?"

Uses `get_air_quality` — returns distance-weighted area average, WHO guideline comparisons, and readings from individual stations.

### City comparisons

> "Compare air quality between Kraków, Warsaw, and Gdańsk"
>
> "Which city has cleaner air — Poznań or Łódź?"

Uses `compare_air_quality` — fetches data for all cities concurrently and ranks them worst-first.

### Historical trends

> "Show me PM2.5 trends for the past week in Kraków"
>
> "How was air quality in Warsaw throughout 2025?"
>
> "What was the worst air quality day in Wrocław last year?"

Uses `get_air_quality_history` — returns summary statistics (min/max/avg), trend direction, and for yearly views: monthly averages, worst/best days, and WHO exceedance counts.

### Pollution rankings

> "Which cities have the worst air quality right now?"
>
> "Show me the top 20 most polluted cities by PM10"
>
> "How does Warsaw rank compared to other cities?"

Uses `get_air_quality_rankings` — supports ranking by city or station, for PM2.5, PM10, NO2, or O3, over 1h/8h/24h periods.

### Finding stations

> "Find air quality stations near me" *(with coordinates)*
>
> "Are there any GIOŚ stations on Marszałkowska street?"
>
> "List monitoring stations in Katowice"

Uses `find_stations` — search by name, city, street, or coordinates. Filter by provider (gios, airly, luftdaten, looko2, blebox).

### Station details

> "Show me all measurements from station 1f8138aa-3092-4bb4-9ee0-23b0638de32b"

Uses `get_station_details` — returns current and 24h average readings for every measurement type at the station.

---

## Tools reference

| Tool | Description | Key parameters |
|------|-------------|----------------|
| `get_air_quality` | Current air quality for a location | `city` or `latitude`+`longitude`, `radius_km`, `pollutant` |
| `compare_air_quality` | Compare 2–5 cities side by side | `cities`, `pollutant` |
| `get_air_quality_history` | Historical readings or yearly calendar | `city` or `station_id`, `pollutant`, `period`, `year` |
| `get_air_quality_rankings` | Ranked cities/stations by pollution | `ranking_type`, `pollutant`, `period`, `limit`, `identifier` |
| `find_stations` | Search for monitoring stations | `query` or `latitude`+`longitude`, `provider`, `limit` |
| `get_station_details` | Full measurements for one station | `station_id` |

The server also exposes a `kanarek://config` **resource** with reference data — measurement types, WHO guidelines, and provider metadata.

---

## Configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `KANAREK_API_URL` | `https://backend.kanarek.app/api/v1` | API base URL |

No API keys or authentication required.

---

## Development

```bash
# Clone and install
git clone https://github.com/KanarekApp/Kanarek-MCP.git
cd Kanarek-MCP
uv sync

# Run unit tests
uv run pytest tests/test_tools.py

# Run integration tests (hits the live API)
KANAREK_INTEGRATION_TEST=1 uv run pytest tests/test_integration.py

# Test interactively with MCP Inspector
uv run mcp dev src/kanarek_mcp/server.py
```

---

## How it works

kanarek-mcp follows an **outcome-oriented** design — one tool call produces one complete answer. Behind the scenes, each tool orchestrates multiple API calls:

```
"What's the air quality in Warsaw?"

  1. Search stations for "Warsaw"     → GET /search/stations?q=Warsaw
  2. Get nearby readings + averages   → GET /stations/nearby?lat=...&lng=...
  3. Format with WHO comparisons      → concise text response
```

Responses are formatted as **concise text** (not raw JSON), optimized for LLM consumption — most important data first, always with units, WHO comparisons, and data freshness timestamps.

---

## Data sources

Data is provided by the [Kanarek](https://kanarek.app) platform, aggregating readings from multiple monitoring networks:

| Provider | Type | Coverage |
|----------|------|----------|
| **GIOŚ** | Government (Chief Inspectorate of Environmental Protection) | Poland |
| **Airly** | Commercial sensor network | Poland, Europe |
| **Luftdaten / sensor.community** | Community-driven sensors | Europe-wide |
| **LookO2** | Consumer sensors | Poland |
| **BleBox** | Consumer sensors | Poland |

---

## License

[CC BY-NC-ND 4.0](LICENSE)

---

<p align="center">
  Powered by <a href="https://kanarek.app">kanarek.app</a>
</p>
