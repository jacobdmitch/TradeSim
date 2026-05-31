"""Order execution.

Two modes, selected per-run from the DB settings:
  - DRY  : paper fills, identical math to the iOS app's Simulator (fee per leg,
           single mark price). Never calls Coinbase order endpoints.
  - LIVE : real market orders via the Coinbase Advanced Trade API
           (coinbase-advanced-py). The API key MUST be scoped to Trade only.

Both modes update the same Portfolio bookkeeping so dry-run results are
directly comparable to what live would have done.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Optional

from . import config
from .db import Portfolio, Trade


@dataclass
class TradeResult:
    action: str            # BUY | SELL
    base: str
    price: float
    quantity: float
    cash_flow: float       # negative on buy, positive on sell
    realized_pnl: Optional[float]
    mode: str              # DRY | LIVE
    order_id: Optional[str] = None


class BrokerError(Exception):
    pass


class Broker:
    def __init__(self, dry_run: bool, fee_rate: float = config.FEE_RATE):
        self.dry_run = dry_run
        self.fee_rate = fee_rate
        self._client = None
        if not dry_run:
            self._client = self._make_client()

    # ---- Coinbase client ----
    @staticmethod
    def _make_client():
        if not config.COINBASE_API_KEY or not config.COINBASE_API_SECRET:
            raise BrokerError(
                "Live mode requires COINBASE_API_KEY and COINBASE_API_SECRET (Trade-only)."
            )
        from coinbase.rest import RESTClient  # imported lazily so dry-run needs no creds
        return RESTClient(api_key=config.COINBASE_API_KEY, api_secret=config.COINBASE_API_SECRET)

    # ---- Seeding (models coins already owned; no fee) ----
    def seed(self, pf: Portfolio, base: str, product_id: str, usd_value: float, price: float) -> None:
        if price <= 0 or usd_value <= 0:
            return
        pf.cash = 0.0
        pf.pos_base = base
        pf.pos_product_id = product_id
        pf.pos_quantity = usd_value / price
        pf.pos_cost_basis_usd = usd_value
        pf.pos_mark_price = price

    # ---- Enter: deploy all cash into `base` ----
    def enter(self, pf: Portfolio, base: str, product_id: str, price: float) -> Optional[TradeResult]:
        if pf.has_position or pf.cash <= 0.01 or price <= 0:
            return None

        if self.dry_run:
            spend = pf.cash
            invested = spend * (1 - self.fee_rate)
            qty = invested / price
            pf.cash = 0.0
            pf.pos_base = base
            pf.pos_product_id = product_id
            pf.pos_quantity = qty
            pf.pos_cost_basis_usd = invested
            pf.pos_mark_price = price
            return TradeResult("BUY", base, price, qty, -spend, None, "DRY")

        # LIVE: market buy using available USD as quote_size.
        spend = pf.cash
        quote_size = self._round_quote(product_id, spend)
        order_id = self._place_market(product_id, side="BUY", quote_size=quote_size)
        fill = self._fill(order_id)
        qty = fill["filled_size"]
        invested = fill["filled_value"] - fill["fees"]  # net cost basis (ex-fee)
        avg_price = fill["avg_price"] or price
        pf.cash = max(pf.cash - fill["filled_value"], 0.0)
        pf.pos_base = base
        pf.pos_product_id = product_id
        pf.pos_quantity = qty
        pf.pos_cost_basis_usd = invested
        pf.pos_mark_price = avg_price
        return TradeResult("BUY", base, avg_price, qty, -fill["filled_value"], None, "LIVE", order_id)

    # ---- Exit: liquidate the position back to USD ----
    def exit(self, pf: Portfolio, price: float) -> Optional[TradeResult]:
        if not pf.has_position or price <= 0:
            return None

        base = pf.pos_base
        product_id = pf.pos_product_id
        qty = pf.pos_quantity
        cost_basis = pf.pos_cost_basis_usd

        if self.dry_run:
            gross = qty * price
            proceeds = gross * (1 - self.fee_rate)
            pnl = proceeds - cost_basis
            pf.cash += proceeds
            self._clear_position(pf)
            return TradeResult("SELL", base, price, qty, proceeds, pnl, "DRY")

        # LIVE: market sell the full base size.
        base_size = self._round_base(product_id, qty)
        order_id = self._place_market(product_id, side="SELL", base_size=base_size)
        fill = self._fill(order_id)
        proceeds = fill["filled_value"] - fill["fees"]
        avg_price = fill["avg_price"] or price
        pnl = proceeds - cost_basis
        pf.cash += proceeds
        self._clear_position(pf)
        return TradeResult("SELL", base, avg_price, qty, proceeds, pnl, "LIVE", order_id)

    @staticmethod
    def _clear_position(pf: Portfolio) -> None:
        pf.pos_base = None
        pf.pos_product_id = None
        pf.pos_quantity = 0.0
        pf.pos_cost_basis_usd = 0.0
        pf.pos_mark_price = 0.0

    # ---- Coinbase order helpers ----
    def _place_market(self, product_id: str, side: str,
                      quote_size: Optional[str] = None, base_size: Optional[str] = None) -> str:
        coid = uuid.uuid4().hex
        if side == "BUY":
            resp = self._client.market_order_buy(client_order_id=coid, product_id=product_id, quote_size=quote_size)
        else:
            resp = self._client.market_order_sell(client_order_id=coid, product_id=product_id, base_size=base_size)

        data = resp if isinstance(resp, dict) else getattr(resp, "__dict__", {})
        success = data.get("success", getattr(resp, "success", False))
        if not success:
            raise BrokerError(f"Coinbase order rejected: {data}")
        # order id can live in a couple of shapes depending on SDK version
        sr = data.get("success_response") or getattr(resp, "success_response", None) or {}
        if isinstance(sr, dict):
            oid = sr.get("order_id")
        else:
            oid = getattr(sr, "order_id", None)
        oid = oid or data.get("order_id") or getattr(resp, "order_id", None)
        if not oid:
            raise BrokerError(f"Coinbase order accepted but no order_id returned: {data}")
        return oid

    def _fill(self, order_id: str, attempts: int = 6, delay: float = 1.0) -> dict:
        """Poll the order until filled; return normalized fill numbers."""
        last = {}
        for _ in range(attempts):
            resp = self._client.get_order(order_id=order_id)
            order = resp.get("order") if isinstance(resp, dict) else getattr(resp, "order", None)
            order = order or (resp if isinstance(resp, dict) else getattr(resp, "__dict__", {}))
            status = _g(order, "status")
            filled_size = _f(_g(order, "filled_size"))
            filled_value = _f(_g(order, "filled_value"))
            fees = _f(_g(order, "total_fees"))
            avg_price = _f(_g(order, "average_filled_price"))
            last = {
                "status": status, "filled_size": filled_size, "filled_value": filled_value,
                "fees": fees, "avg_price": avg_price,
            }
            if status in {"FILLED", "DONE"} and filled_size > 0:
                return last
            time.sleep(delay)
        if last.get("filled_size", 0) > 0:
            return last
        raise BrokerError(f"Order {order_id} did not fill in time: {last}")

    # ---- Increment rounding (Coinbase requires sizes on the product grid) ----
    def _round_base(self, product_id: str, qty: float) -> str:
        inc = self._increment(product_id, "base_increment", "0.00000001")
        return str(Decimal(str(qty)).quantize(inc, rounding=ROUND_DOWN))

    def _round_quote(self, product_id: str, usd: float) -> str:
        inc = self._increment(product_id, "quote_increment", "0.01")
        return str(Decimal(str(usd)).quantize(inc, rounding=ROUND_DOWN))

    def _increment(self, product_id: str, field: str, default: str) -> Decimal:
        try:
            resp = self._client.get_product(product_id=product_id)
            val = _g(resp, field) or (resp.get("product", {}).get(field) if isinstance(resp, dict) else None)
            return Decimal(str(val)) if val else Decimal(default)
        except Exception:
            return Decimal(default)


def _g(obj, key):
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
