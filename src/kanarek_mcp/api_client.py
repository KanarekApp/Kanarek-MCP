"""HTTP client for the Kanarek air quality API."""

import asyncio
import os
from typing import Any

import httpx


class KanarekClient:
    """Async HTTP client for backend.kanarek.app.

    Lazily creates an httpx.AsyncClient bound to the current event loop,
    and recreates it if the loop changes (e.g. between test cases).
    """

    def __init__(self) -> None:
        self._base_url = os.environ.get(
            "KANAREK_API_URL", "https://backend.kanarek.app/api/v1"
        )
        self._client: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _ensure_client(self) -> httpx.AsyncClient:
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"User-Agent": "kanarek-mcp/1.1.0"},
                timeout=30.0,
            )
            self._loop = loop
        return self._client

    @property
    def is_closed(self) -> bool:
        return self._client is not None and self._client.is_closed

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Make a GET request. Returns parsed JSON, None on 404."""
        client = self._ensure_client()
        response = await client.get(path, params=params)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def __aenter__(self) -> "KanarekClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
