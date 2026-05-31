"""Coinbase public market data. Port of TradeSim/Services/MarketDataService.swift.

Uses Coinbase's public (no-auth) endpoints for the product universe, bulk 24h
stats, and historical candles. This is read-only; it never touches funds.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import requests

from . import config

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "TradeSim-Server/1.0"})
_TIMEOUT = 20

EXCHANGE = "https://api.exchange.coinbase.com"
BROKERAGE_SPOT = "https://api.coinbase.com/v2/prices"


@dataclass
class Product:
    id: str
    base: str
    quote: str
    status: str
    trading_disabled: bool


@dataclass
class MarketStat:
    product_id: str
    base: str
    open: float
    high: float
    low: float
    last: float
    volume: float  # 24h volume in base units

    @property
    def change_pct(self) -> float:
        return (self.last - self.open) / self.open * 100 if self.open > 0 else 0.0

    @property
    def volume_usd(self) -> float:
        return self.volume * self.last


def fetch_usd_products() -> List[Product]:
    """All online, tradable USD products (stablecoins filtered out)."""
    r = _SESSION.get(f"{EXCHANGE}/products", timeout=_TIMEOUT)
    r.raise_for_status()
    out: List[Product] = []
    for d in r.json():
        if (
            d.get("quote_currency") == config.QUOTE_CURRENCY
            and d.get("status") == "online"
            and not d.get("trading_disabled", False)
            and d.get("base_currency") not in config.STABLECOINS
        ):
            out.append(
                Product(
                    id=d["id"],
                    base=d["base_currency"],
                    quote=d["quote_currency"],
                    status=d["status"],
                    trading_disabled=bool(d.get("trading_disabled", False)),
                )
            )
    return out


def fetch_stats(products: List[Product]) -> List[MarketStat]:
    """24h stats for every product in a single request; filtered to `products`."""
    r = _SESSION.get(f"{EXCHANGE}/products/stats", timeout=_TIMEOUT)
    r.raise_for_status()
    raw = r.json()
    by_base = {p.id: p.base for p in products}
    out: List[MarketStat] = []
    for product_id, dto in raw.items():
        base = by_base.get(product_id)
        if base is None:
            continue
        w = (dto or {}).get("stats_24hour") or {}
        last = _to_float(w.get("last"))
        if last is None or last <= 0:
            continue
        out.append(
            MarketStat(
                product_id=product_id,
                base=base,
                open=_to_float(w.get("open")) or last,
                high=_to_float(w.get("high")) or last,
                low=_to_float(w.get("low")) or last,
                last=last,
                volume=_to_float(w.get("volume")) or 0.0,
            )
        )
    return out


def fetch_candles(product_id: str, granularity: int = config.GRANULARITY) -> List[List[float]]:
    """Recent candles, oldest-first. Each row: [time, low, high, open, close, volume]."""
    r = _SESSION.get(
        f"{EXCHANGE}/products/{product_id}/candles",
        params={"granularity": granularity},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    rows = [row for row in r.json() if isinstance(row, list) and len(row) >= 6]
    rows.sort(key=lambda row: row[0])  # oldest first
    return rows


def fetch_closes_for(product_ids: List[str], granularity: int = config.GRANULARITY) -> Dict[str, List[float]]:
    """Closing-price series keyed by product id (sequential; the candidate set is small)."""
    out: Dict[str, List[float]] = {}
    for pid in product_ids:
        try:
            rows = fetch_candles(pid, granularity)
            out[pid] = [row[4] for row in rows]  # close is index 4
        except Exception:
            continue
    return out


def fetch_spot(product_id: str) -> Optional[float]:
    try:
        r = _SESSION.get(f"{BROKERAGE_SPOT}/{product_id}/spot", timeout=_TIMEOUT)
        r.raise_for_status()
        return float(r.json()["data"]["amount"])
    except Exception:
        return None


def _to_float(v) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
