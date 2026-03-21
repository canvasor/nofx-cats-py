from __future__ import annotations

import time
from typing import Any, Mapping

import httpx

from .auth import sign_params


class BinanceRestClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://fapi.binance.com",
        recv_window_ms: int = 5000,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.recv_window_ms = recv_window_ms
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            headers={"X-MBX-APIKEY": api_key},
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: Mapping[str, Any] | None = None,
        signed: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = dict(params or {})
        if signed:
            payload["timestamp"] = int(time.time() * 1000)
            payload["recvWindow"] = self.recv_window_ms
            payload["signature"] = sign_params(self.api_secret, payload)

        response = await self.client.request(method, path, params=payload)
        response.raise_for_status()
        json_payload = response.json()
        if not isinstance(json_payload, (dict, list)):
            raise TypeError("Binance response must be dict or list")
        return {"data": json_payload}

    async def get_exchange_info(self) -> dict[str, Any]:
        return await self._request("GET", "/fapi/v1/exchangeInfo")

    async def get_leverage_brackets(self, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return await self._request("GET", "/fapi/v1/leverageBracket", params=params, signed=True)

    async def get_position_risk(self, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return await self._request("GET", "/fapi/v3/positionRisk", params=params, signed=True)

    async def get_api_trading_status(self, symbol: str | None = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return await self._request("GET", "/fapi/v1/apiTradingStatus", params=params, signed=True)

    async def start_user_stream(self) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/listenKey")

    async def keepalive_user_stream(self) -> dict[str, Any]:
        return await self._request("PUT", "/fapi/v1/listenKey")

    async def new_order(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/fapi/v1/order", params=params, signed=True)

    async def new_algo_order(self, params: Mapping[str, Any]) -> dict[str, Any]:
        algo_params = {"algoType": "CONDITIONAL", **params}
        return await self._request("POST", "/fapi/v1/algoOrder", params=algo_params, signed=True)

    async def countdown_cancel_all(self, symbol: str, countdown_ms: int) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/fapi/v1/countdownCancelAll",
            params={"symbol": symbol, "countdownTime": countdown_ms},
            signed=True,
        )

    async def close(self) -> None:
        await self.client.aclose()
