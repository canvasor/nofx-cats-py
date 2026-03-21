from __future__ import annotations

from typing import Any


class UniverseBuilder:
    def build(self, ai500_payload: dict[str, Any], ai300_payload: dict[str, Any]) -> list[str]:
        symbols: list[str] = []

        coins = ai500_payload.get("data", {}).get("coins", [])
        for item in coins:
            pair = item.get("pair")
            if isinstance(pair, str):
                symbols.append(pair)

        ai300_coins = ai300_payload.get("data", {}).get("coins", [])
        for item in ai300_coins:
            symbol = item.get("symbol")
            if isinstance(symbol, str) and not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"
            if isinstance(symbol, str):
                symbols.append(symbol)

        seen: set[str] = set()
        deduped: list[str] = []
        for symbol in symbols:
            if symbol not in seen:
                deduped.append(symbol)
                seen.add(symbol)
        return deduped
