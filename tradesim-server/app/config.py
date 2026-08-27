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
MIN_LIQUIDITY_USD = 100_000  # minimum 24h USD volume on Coinbase to be a rotation candidate

# Fee floor in real money. Percent thresholds alone hide fee drag on a small
# account: at 0.6%/leg a $27 position pays ~$0.32 per round trip, so a 0.2%
# "edge" is 5c of upside against 32c of cost. ENTER and ROTATE must therefore
# clear their own round-trip cost by at least this many dollars of expected
# profit — otherwise the engine holds. Raise it to trade less and only on
# meaningful moves; the % thresholds below stay in force either way.
MIN_NET_PROFIT_USD = _f("MIN_NET_PROFIT_USD", 0.25)

STABLECOINS = {
    "USDC", "USDT", "DAI", "PYUSD", "GUSD", "USDB", "PAX", "USDP",
    "EURC", "USD", "EUR", "GBP", "TUSD", "BUSD", "USTC", "RLUSD",
}

# Tokens that have been merged, deprecated, or asset-restructured and must never be traded.
# These are permanent exclusions beyond the dynamic veto system.
DEPRECATED_TOKENS = {
    "STG",  # merged into LayerZero (ZRO) at fixed 0.08634 ratio, April 2026; Binance.US/Coinmetro delisted
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
    # Raised from 0.5: at 0.6%/leg a 0.5% edge doesn't cover the 1.2% round trip,
    # so marginal entries were pure fee burn. Every entry must clear round-trip
    # cost with margin.
    enter_threshold_pct: float = 2.0
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

# Minimum time to hold before opening/switching a position (cuts churn). A
# protective exit-to-cash is always allowed; this blocks ENTER and ROTATE.
MIN_HOLD_HOURS_DEFAULT = int(os.environ.get("MIN_HOLD_HOURS", "6"))

# Hours a token stays excluded after receiving 2 consecutive AI Auditor vetos.
VETO_EXCLUSION_HOURS_DEFAULT = int(os.environ.get("VETO_EXCLUSION_HOURS", "24"))

# Min-hold bypass: if the current holding drops below this edge % AND at least
# MIN_HOLD_BYPASS_ALTERNATIVES other scored coins are above it, the 6-hour lock
# is lifted so the next refresh can act on a ROTATE or EXIT recommendation.
MIN_HOLD_BYPASS_SHELF_PCT = float(os.environ.get("MIN_HOLD_BYPASS_SHELF_PCT", "1.2"))
MIN_HOLD_BYPASS_ALTERNATIVES = int(os.environ.get("MIN_HOLD_BYPASS_ALTERNATIVES", "3"))

# Selection logic: "anti_chasing" (avoid extended/overbought, prefer pullbacks)
# or "momentum" (legacy top-gainer chasing). Backtest favored anti_chasing+regime.
SELECTION_MODE = os.environ.get("SELECTION_MODE", "anti_chasing").strip()

# Regime gate: favorable when BTC is trending up AND at least this fraction of
# the analyzed universe is trending up. Unfavorable doesn't block trading outright
# — it raises the bar (REGIME_PENALTY_PCT) so only a standout edge still clears.
REGIME_BREADTH_MIN = float(os.environ.get("REGIME_BREADTH_MIN", "0.5"))
REGIME_PENALTY_PCT = float(os.environ.get("REGIME_PENALTY_PCT", "3.0"))  # extra edge margin required when unfavorable
# Anti-chasing guardrails
ANTI_RSI_MAX = float(os.environ.get("ANTI_RSI_MAX", "68"))
ANTI_EXTENSION_MAX = float(os.environ.get("ANTI_EXTENSION_MAX", "6.0"))  # % above short SMA

# ---- Breakout entry path (catch hot runs early) ----
# A coin is a "breakout" when its short-term rate of change AND volume surge
# clear these thresholds. Breakouts bypass the anti-chasing RSI/extension caps
# and the SMA trend-cross requirement (which lags a fresh run by 10-20h), and
# skip the 2-scan confirmation. The trailing stop below is the risk control
# that replaces those entry guards.
BREAKOUT_ROC_BARS = int(os.environ.get("BREAKOUT_ROC_BARS", "3"))                 # 1h bars in the ROC window
BREAKOUT_ROC_MIN_PCT = float(os.environ.get("BREAKOUT_ROC_MIN_PCT", "3.0"))      # min % gain over that window
BREAKOUT_VOL_SURGE_MIN = float(os.environ.get("BREAKOUT_VOL_SURGE_MIN", "2.0"))  # recent bar vol vs 24h avg
BREAKOUT_RSI_HARD_MAX = float(os.environ.get("BREAKOUT_RSI_HARD_MAX", "85"))     # never buy a blow-off top

# Trailing stop: exit when price falls this % below its peak since entry.
# Locks in most of a run instead of holding until the (lagging) SMA flip.
TRAILING_STOP_PCT = float(os.environ.get("TRAILING_STOP_PCT", "5.0"))

COINBASE_API_KEY = os.environ.get("COINBASE_API_KEY", "").strip()
# Allow the PEM to be supplied with escaped newlines.
COINBASE_API_SECRET = os.environ.get("COINBASE_API_SECRET", "").replace("\\n", "\n").strip()
