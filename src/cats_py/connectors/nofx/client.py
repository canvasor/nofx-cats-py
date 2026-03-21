from __future__ import annotations

from typing import Any, Mapping

import httpx


class NofxClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://nofxos.ai",
        auth_mode: str = "bearer",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.auth_mode = auth_mode
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        if self.auth_mode == "bearer":
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _build_params(self, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        merged = dict(params or {})
        if self.auth_mode == "query":
            merged["auth"] = self.api_key
        return merged

    async def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        response = await self.client.get(path, params=self._build_params(params))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("NOFX response must be a dict")
        return payload

    async def ai500_list(self, limit: int | None = None) -> dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return await self.get_json("/api/ai500/list", params)

    async def ai300_list(self, limit: int | None = None) -> dict[str, Any]:
        params = {"limit": limit} if limit is not None else None
        return await self.get_json("/api/ai300/list", params)

    async def coin(self, symbol: str, include: str | None = None) -> dict[str, Any]:
        params = {"include": include} if include else None
        return await self.get_json(f"/api/coin/{symbol}", params)

    async def funding_rate(self, symbol: str) -> dict[str, Any]:
        return await self.get_json(f"/api/funding-rate/{symbol}")

    async def heatmap_future(self, symbol: str) -> dict[str, Any]:
        return await self.get_json(f"/api/heatmap/future/{symbol}")

    async def query_rank(self, limit: int = 20) -> dict[str, Any]:
        return await self.get_json("/api/query-rank/list", {"limit": limit})

    async def close(self) -> None:
        await self.client.aclose()
