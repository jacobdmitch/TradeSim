"""Static configuration and strategy parameters.

The strategy numbers are a faithful port of the iOS app's StrategyConfig and
RotationConfig (TradeSim/Services/SignalEngine.swift and
Models/MarketScanModels.swift) so the server reproduces the app's behavior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # python-dotenv optional at runtime
    pass


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _b(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


# ---- Seed (your real-world starting point) ----
SEED_BASE = "DIMO"
SEED_PRODUCT_ID = "DIMO-USD"

# ---- Market / execution constants (match the iOS app) ----
QUOTE_CURRENCY = "USD"
GRANULARITY = 3600          # 1-hour candles
FEE_RATE = 0.006            # Coinbase Advanced taker fee, low-volume tier (~0.6%/leg)
MIN_LIQUIDITY_USD = 25_000  # minimum 24h USD volume to be a rotation candidate

STABLECOINS = {
    "USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDB", "PAX", "USDP",
    "EURC", "USD", "EUR", "GBP", "TUSD", "BUSD", "USTC", "RLUSD",
}


@dataclass
class StrategyConfig:
    short_sma: int = 9
    long_sma: int = 21
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "StrategyConfig":
        if not d:
            return cls()
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


@dataclass
class RotationConfig:
    candidate_count: int = 12
    momentum_lookback: int = 6
    enter_threshold_pct: float = 0.5
    rotation_threshold_pct: float = 3.0   # raised from 1.5 to cut marginal whipsaw rotations
    exit_threshold_pct: float = -1.0
    auto_rotate: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "RotationConfig":
        if not d:
            return cls()
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})


# ---- Runtime defaults (overridden by the DB settings row after first boot) ----
TRADING_ENABLED_DEFAULT = _b("TRADING_ENABLED", False)
DRY_RUN_DEFAULT = _b("DRY_RUN", True)
STARTING_BALANCE_DEFAULT = _f("STARTING_BALANCE", 23.17)
BALANCE_FLOOR_DEFAULT = _f("BALANCE_FLOOR_USD", 0.0)

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "").strip()

# ---- Claude pre-trade audit (optional, veto-only) ----
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
AUDIT_MODEL = os.environ.get("AUDIT_MODEL", "claude-haiku-4-5-20251001").strip()
AUDIT_ENABLED_DEFAULT = _b("AUDIT_ENABLED", False)
AUDIT_MAX_SEARCHES = int(os.environ.get("AUDIT_MAX_SEARCHES", "3"))

# Effective trading cadence (minutes). The Render cron fires every 15 min; this
# throttles to a multiple of that. Tunable from the dashboard knob.
INTERVAL_MINUTES_DEFAULT = int(os.environ.get("INTERVAL_MINUTES", "15"))
INTERVAL_CHOICES = [15, 30, 45, 60]
CRON_GRANULARITY_MIN = 15  # must match render.yaml cron schedule

# Minimum time to hold a coin before rotating to another (cuts churn). A
# protective exit-to-cash is always allowed; this only blocks coin->coin flips.
MIN_HOLD_HOURS_DEFAULT = int(os.environ.get("MIN_HOLD_HOURS", "6"))

COINBASE_API_KEY = os.environ.get("COINBASE_API_KEY", "").strip()
# Allow the PEM to be supplied with escaped newlines.
COINBASE_API_SECRET = os.environ.get("COINBASE_API_SECRET", "").replace("\\n", "\n").strip()
