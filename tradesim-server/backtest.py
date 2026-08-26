#!/usr/bin/env python3
"""Backtest harness for TradeSim selection logic.

Replays real historical hourly candles for a liquid Coinbase USD universe and
runs several buy-selection strategies under identical execution rules:
  - per-leg fee (0.6%)
  - 2-scan confirmation before switching (kills single-bar whipsaw)
  - single position, decisions on each bar's close, no look-ahead

Strategies compared:
  - current        : buy top 24h gainers, momentum-scored (today's live logic)
  - anti_chasing   : trend-following but avoid extended/overbought names; enter pullbacks
  - mean_reversion : buy oversold dips within a longer-term uptrend
  - hold_dimo      : buy DIMO at the start and hold (baseline)
  - cash           : never trade (baseline)

No look-ahead: indicators at bar i use only closes[:i+1]; fills use close[i].
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

import requests

from app import config, market, signals

FEE = config.FEE_RATE
SHORT, LONG, RSI_P = 9, 21, 14
LOOK = 6              # momentum window (bars)
MIN_LIQ = config.MIN_LIQUIDITY_USD
UNIVERSE_SIZE = 15   # most-liquid alts to consider (smaller so paging stays fast)
HISTORY_BARS = 720   # ~30 days of hourly candles
MIN_HOLD_BARS = 6    # don't switch coin->coin within this many bars (matches live default)
WALK_SEGMENTS = 3    # walk-forward windows
WARMUP = LONG + 26   # need long SMA + 24h change room

_EXCH = "https://api.exchange.coinbase.com"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "TradeSim-Backtest/1.0"})


def fetch_history(product_id: str, bars: int = HISTORY_BARS) -> list:
    """Page the exchange candles endpoint backward to assemble `bars` hourly
    candles (max 300 per request). Returns rows oldest-first."""
    rows: dict = {}
    end = datetime.now(timezone.utc)
    while len(rows) < bars:
        start = end - timedelta(hours=300)
        r = _SESSION.get(
            f"{_EXCH}/products/{product_id}/candles",
            params={"granularity": 3600, "start": start.isoformat(), "end": end.isoformat()},
            timeout=20,
        )
        if r.status_code != 200:
            break
        chunk = [row for row in r.json() if isinstance(row, list) and len(row) >= 6]
        if not chunk:
            break
        for row in chunk:
            rows[row[0]] = row
        end = start
        time.sleep(0.12)
        if len(chunk) < 200:   # ran out of history
            break
    return [rows[t] for t in sorted(rows)][-bars:]


# ---------- data ----------

def load_universe() -> Dict[str, list]:
    """Return {base: candles[]} for the most liquid USD alts (+ DIMO)."""
    products = market.fetch_usd_products()
    stats = market.fetch_stats(products)
    stats.sort(key=lambda s: s.volume_usd, reverse=True)
    bases = [s.base for s in stats[:UNIVERSE_SIZE]]
    if config.SEED_BASE not in bases:
        bases.append(config.SEED_BASE)
    out = {}
    pid = {s.base: s.product_id for s in stats}
    for b in bases:
        try:
            c = fetch_history(pid[b])
            if len(c) >= WARMUP + 10:
                out[b] = c
        except Exception:
            continue
    return out


def align(univ: Dict[str, list]):
    """Align all series onto a common timeline (intersection of timestamps).
    Candle rows are [time, low, high, open, close, volume]. Returns
    (timeline, closes{base:[..]}, vols{base:[..]})."""
    ts_sets = [set(r[0] for r in rows) for rows in univ.values()]
    common = sorted(set.intersection(*ts_sets))
    closes, vols = {}, {}
    for b, rows in univ.items():
        by_ts = {r[0]: r for r in rows}
        closes[b] = [by_ts[t][4] for t in common]            # close
        vols[b] = [by_ts[t][4] * by_ts[t][5] for t in common]  # USD volume proxy
    return common, closes, vols


# ---------- features ----------

@dataclass
class Feat:
    price: float
    ret24: float
    mom: float
    rsi: Optional[float]
    short_sma: float
    long_sma: float
    trend_up: bool
    extension: float   # % above short SMA
    roc3: float = 0.0  # % change over BREAKOUT_ROC_BARS bars
    vsurge: float = 0.0  # recent bar volume vs trailing 24h average


def feat(closes: List[float], vols: List[float], i: int) -> Optional[Feat]:
    if i < WARMUP:
        return None
    seq = closes[: i + 1]
    price = seq[-1]
    if price <= 0:
        return None
    ssma = signals.sma(seq, SHORT) or 0.0
    lsma = signals.sma(seq, LONG) or 0.0
    rsi = signals.rsi(seq, RSI_P)
    ret24 = (price / seq[-25] - 1) * 100 if len(seq) > 25 and seq[-25] > 0 else 0.0
    mom = (price / seq[-1 - LOOK] - 1) * 100 if len(seq) > LOOK and seq[-1 - LOOK] > 0 else 0.0
    ext = (price / ssma - 1) * 100 if ssma > 0 else 0.0
    bo_bars = config.BREAKOUT_ROC_BARS
    roc3 = (price / seq[-1 - bo_bars] - 1) * 100 if len(seq) > bo_bars and seq[-1 - bo_bars] > 0 else 0.0
    vseq = vols[: i + 1]
    vsurge = 0.0
    if len(vseq) >= 4:
        recent = max(vseq[-1], vseq[-2])
        baseline = vseq[-26:-2] if len(vseq) >= 26 else vseq[:-2]
        avg = sum(baseline) / len(baseline) if baseline else 0.0
        vsurge = recent / avg if avg > 0 else 0.0
    return Feat(price, ret24, mom, rsi, ssma, lsma, ssma > lsma, ext, roc3, vsurge)


# ---------- strategies: each returns the target base (or None = cash) ----------
# A strategy may instead return (target, strong): strong=True marks a breakout-
# grade signal that skips the 2-scan confirmation (mirrors the live engine).

def strat_current(feats: Dict[str, Feat], holding: Optional[str] = None) -> Optional[str]:
    # candidate pool = top 24h gainers, then momentum edge (mirrors live logic)
    pool = sorted(feats.items(), key=lambda kv: kv[1].ret24, reverse=True)[:12]
    best, best_edge = None, 0.0
    for b, f in pool:
        edge = f.mom
        if not f.trend_up:
            edge *= 0.3
        if f.rsi is not None:
            if f.rsi >= 70:
                edge *= 0.4
            elif f.rsi <= 30 and f.trend_up:
                edge *= 1.3
        if edge > best_edge:
            best, best_edge = b, edge
    return best if best_edge > 1.1 else None


def strat_anti_chasing(feats: Dict[str, Feat], holding: Optional[str] = None) -> Optional[str]:
    # established uptrend, NOT overbought, NOT stretched far above short SMA;
    # prefer the least-extended (closest to a pullback) with mild momentum.
    best, best_score = None, None
    for b, f in feats.items():
        if not f.trend_up:
            continue
        if f.rsi is None or f.rsi >= 68:        # exclude overbought
            continue
        if f.extension > 6.0:                   # exclude stretched (buying the rip)
            continue
        if f.mom <= 0:                          # still want a positive drift
            continue
        score = f.mom - 1.5 * max(f.extension, 0.0)   # penalize extension
        if best_score is None or score > best_score:
            best, best_score = b, score
    return best


def make_live_v2(enter_th: Optional[float] = None, rotate_th: Optional[float] = None) -> Callable:
    """Build a strat_live_v2-shaped target function bound to specific enter/
    rotate thresholds, defaulting to the live config's. Lets app/improve.py
    backtest nearby parameter variants through the same execution harness
    without changing run_strategy's (feats, holding) calling convention."""
    _enter_th = config.RotationConfig().enter_threshold_pct if enter_th is None else enter_th
    _rotate_th = config.RotationConfig().rotation_threshold_pct if rotate_th is None else rotate_th
    fee_pct = FEE * 100

    def edge(f: Feat):
        bo = (
            f.roc3 >= config.BREAKOUT_ROC_MIN_PCT
            and f.vsurge >= config.BREAKOUT_VOL_SURGE_MIN
            and f.rsi is not None and f.rsi < config.BREAKOUT_RSI_HARD_MAX
        )
        if bo:
            return max(f.mom, f.roc3), True
        if (not f.trend_up or f.mom <= 0 or f.rsi is None
                or f.rsi >= config.ANTI_RSI_MAX or f.extension > config.ANTI_EXTENSION_MAX):
            return -999.0, False
        return f.mom - 1.5 * max(f.extension, 0.0), False

    def strat(feats: Dict[str, Feat], holding: Optional[str] = None):
        """Mirror of the live anti_chasing + breakout predictor (app/predictor.py):
          - breakout path: ROC + volume surge qualifies a fresh run early, bypassing
            the SMA-cross / RSI / extension entry guards; edge = max(mom, roc)
          - pullback path: classic anti-chasing edge
          - hold edge: entry disqualifiers don't force exits out of a winning run
        Returns (target, strong)."""
        best, best_edge, best_strong = None, None, False
        for b, f in feats.items():
            e, s = edge(f)
            if best_edge is None or e > best_edge:
                best, best_edge, best_strong = b, e, s

        if holding is None:
            # Entering owns the whole round trip (buy now, sell later), so the edge
            # has to cover both legs. The live engine also applies a dollar floor on
            # expected net profit (config.MIN_NET_PROFIT_USD); at the $100 start size
            # used here it sits well below this gate and never binds.
            if best is not None and best_edge > _enter_th + 2 * fee_pct:
                return best, best_strong
            return None, False

        f = feats.get(holding)
        if f is None:
            return None, False          # holding fell out of the liquid universe
        e, s = edge(f)
        hold_edge = e if s else (f.mom if (f.trend_up and f.mom > 0) else -999.0)

        better_exists = best is not None and best != holding and best_edge > _enter_th
        if hold_edge < -1.0 and not better_exists:
            return None, False          # trend flip / momentum fade -> cash
        if best and best != holding and best_edge > hold_edge + _rotate_th + 2 * fee_pct:
            return best, best_strong
        return holding, False

    return strat


# Default instance backtest against the live config's current thresholds.
strat_live_v2 = make_live_v2()


def regime_ok(feats: Dict[str, Feat]) -> bool:
    """Favorable market: BTC in an uptrend AND most of the universe trending up.
    When false, the wrapper forces a move to cash (don't fight a down market)."""
    if not feats:
        return False
    btc = feats.get("BTC")
    btc_up = btc.trend_up if btc else True
    breadth = sum(1 for f in feats.values() if f.trend_up) / len(feats)
    return btc_up and breadth >= 0.5


def strat_mean_reversion(feats: Dict[str, Feat], holding: Optional[str] = None) -> Optional[str]:
    # longer-term uptrend but short-term oversold -> buy the dip
    best, best_score = None, None
    for b, f in feats.items():
        if f.price <= f.long_sma * 0.99:        # require ~uptrend regime (slight slack)
            continue
        if f.rsi is None or f.rsi > 45:         # require pulled-back/oversold
            continue
        score = 45 - f.rsi                      # more oversold = better
        if best_score is None or score > best_score:
            best, best_score = b, score
    return best


# ---------- execution wrapper (shared, fair across strategies) ----------

@dataclass
class Result:
    name: str
    final: float
    ret_pct: float
    trades: int
    fees: float
    max_dd: float
    equity: List[float] = field(default_factory=list)


def run_strategy(name: str, target_fn: Callable, timeline, closes, vols,
                 start_cash: float = 100.0, min_hold_bars: int = MIN_HOLD_BARS,
                 use_regime: bool = False, brake_all: bool = False,
                 trail_pct: Optional[float] = None) -> Result:
    cash, base, qty, basis = start_cash, None, 0.0, 0.0
    pending = None          # last bar's target signal (for 2-scan confirm)
    last_change = -10**9    # bar index of the last position change
    trades = 0
    fees = 0.0
    equity = []
    peak = start_cash
    max_dd = 0.0
    pos_peak = 0.0          # high-water mark of the held coin (trailing stop)

    n = len(timeline)
    for i in range(n):
        # Trailing stop: immediate exit when price falls trail_pct below the
        # peak since entry (mirrors the live engine; bypasses confirmation).
        if trail_pct and base is not None:
            px = closes[base][i]
            pos_peak = max(pos_peak, px)
            if px <= pos_peak * (1 - trail_pct / 100):
                gross = qty * px
                proceeds = gross * (1 - FEE)
                fees += gross * FEE
                cash += proceeds
                trades += 1
                base, qty, basis = None, 0.0, 0.0
                pos_peak = 0.0
                last_change = i

        # eligible features for liquid coins at bar i
        feats = {}
        for b in closes:
            if vols[b][i] < MIN_LIQ:
                continue
            f = feat(closes[b], vols[b], i)
            if f is not None and f.rsi is not None:
                feats[b] = f
        res = target_fn(feats, base) if feats else None
        target, strong = res if isinstance(res, tuple) else (res, False)

        # Regime filter: in an unfavorable market, force a move to cash.
        if use_regime and not regime_ok(feats):
            target, strong = None, False

        # 2-scan confirmation: only act when the target repeats across 2 bars.
        # Strong (breakout) signals act immediately, like the live engine.
        confirmed = (target == pending) or strong
        pending = target

        if confirmed and target != base:
            # Selling to cash (protective) is always allowed.
            if target is None:
                gross = qty * closes[base][i]
                proceeds = gross * (1 - FEE)
                fees += gross * FEE
                cash += proceeds
                trades += 1
                base, qty, basis = None, 0.0, 0.0
                last_change = i
            else:
                # Opening/switching requires the brake to be satisfied: enough
                # bars since the last change (blocks coin->coin AND cash-hopping).
                brake_bars = min_hold_bars if (brake_all or base is not None) else 0
                if (i - last_change) >= brake_bars:
                    price_now = closes.get(target, [None] * n)[i]
                    if base is not None:
                        gross = qty * closes[base][i]
                        proceeds = gross * (1 - FEE)
                        fees += gross * FEE
                        cash += proceeds
                        trades += 1
                        base, qty, basis = None, 0.0, 0.0
                    if price_now and price_now > 0:
                        invested = cash * (1 - FEE)
                        fees += cash * FEE
                        qty = invested / price_now
                        basis = invested
                        base = target
                        cash = 0.0
                        trades += 1
                        last_change = i

        # mark to market
        value = cash + (qty * closes[base][i] if base else 0.0)
        equity.append(value)
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak * 100)

    final = equity[-1] if equity else start_cash
    return Result(name, final, (final / start_cash - 1) * 100, trades, fees, max_dd, equity)


def run_hold_dimo(timeline, closes, start_cash=100.0) -> Result:
    if config.SEED_BASE not in closes:
        return Result("hold_dimo", start_cash, 0.0, 0, 0.0, 0.0)
    c = closes[config.SEED_BASE]
    qty = (start_cash * (1 - FEE)) / c[0]
    equity = [qty * p for p in c]
    final = equity[-1]
    peak, dd = start_cash, 0.0
    for v in equity:
        peak = max(peak, v); dd = max(dd, (peak - v) / peak * 100)
    return Result("hold_dimo", final, (final / start_cash - 1) * 100, 1, start_cash * FEE, dd, equity)


def main():
    print("Loading universe + candles from Coinbase...")
    univ = load_universe()
    timeline, closes, vols = align(univ)
    days = len(timeline) / 24.0
    print(f"Universe: {len(closes)} coins | {len(timeline)} hourly bars (~{days:.1f} days)\n")

    rg = dict(use_regime=True, brake_all=True)
    results = [
        run_strategy("current(raw)", strat_current, timeline, closes, vols),
        run_strategy("current+rg", strat_current, timeline, closes, vols, **rg),
        run_strategy("anti+rg", strat_anti_chasing, timeline, closes, vols, **rg),
        run_strategy("livev2+rg+trail", strat_live_v2, timeline, closes, vols,
                     trail_pct=config.TRAILING_STOP_PCT, **rg),
        run_strategy("meanrev+rg", strat_mean_reversion, timeline, closes, vols, **rg),
        run_hold_dimo(timeline, closes),
    ]
    # cash baseline
    results.append(Result("cash", 100.0, 0.0, 0, 0.0, 0.0))

    print(f"{'strategy':16} {'return%':>9} {'final$':>9} {'trades':>7} {'fees$':>7} {'maxDD%':>7}")
    print("-" * 60)
    for r in sorted(results, key=lambda r: r.ret_pct, reverse=True):
        print(f"{r.name:16} {r.ret_pct:>+8.2f}% {r.final:>8.2f} {r.trades:>7} {r.fees:>7.2f} {r.max_dd:>6.1f}%")

    # Walk-forward: return within each equal time segment (consistency check).
    n = len(timeline)
    seg = max(n // WALK_SEGMENTS, 1)
    bounds = [(k * seg, (n if k == WALK_SEGMENTS - 1 else (k + 1) * seg)) for k in range(WALK_SEGMENTS)]
    print(f"\nWalk-forward (return % within each ~{days / WALK_SEGMENTS:.1f}-day window):")
    hdr = "  ".join([f"seg{k+1}" for k in range(WALK_SEGMENTS)])
    print(f"{'strategy':16} {hdr}")
    print("-" * 60)
    for r in results:
        if not r.equity:
            continue
        segs = []
        for (a, b) in bounds:
            sv, ev = r.equity[a], r.equity[min(b, n) - 1]
            segs.append((ev / sv - 1) * 100 if sv else 0.0)
        cells = "  ".join(f"{x:>+5.1f}" for x in segs)
        print(f"{r.name:16} {cells}")

    print(f"\nWindow: ~{days:.1f} days of 1h candles. Start $100, fee {FEE*100:.1f}%/leg, "
          f"2-scan confirm, {MIN_HOLD_BARS}h min-hold. Past results, not predictive.")


if __name__ == "__main__":
    main()
