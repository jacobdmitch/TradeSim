"""Coin scoring and rotation recommendation.

Direct port of TradeSim/Services/Predictor.swift. The "prediction" is an
explicit, transparent heuristic blending momentum, SMA trend and RSI into a
single short-term edge. It is a screening tool, never a guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import config, signals
from .config import RotationConfig, StrategyConfig
from .market import MarketStat


@dataclass
class CoinScore:
    product_id: str
    base: str
    last: float
    change_24h: float
    momentum: float
    rsi: Optional[float]
    trend_up: bool
    predicted_edge_pct: float
    breakout: bool = False   # fresh run: short-term ROC + volume surge qualified
    roc: float = 0.0         # % change over BREAKOUT_ROC_BARS bars
    vol_surge: float = 0.0   # recent bar volume vs trailing 24h average


@dataclass
class TradeEconomics:
    """What acting is actually worth in dollars at the current account size.

    Percent edges hide fee drag on a small balance — a 0.2% edge on $27 is 5c of
    upside against 32c of round-trip fees — so every gain-seeking action is
    checked against these numbers, not just against the percent thresholds."""
    trade_value_usd: float
    fee_legs: int
    fee_usd: float
    gross_gain_usd: float
    net_gain_usd: float


def trade_economics(account_value_usd: float, fee_legs: int, edge_pct: float,
                    fee_rate: float) -> TradeEconomics:
    """Dollar cost/benefit of a pending action.

    `fee_legs` is 2 for ENTER and ROTATE — the position has to be sold again, so
    the decision owns the whole round trip — and 1 for a protective EXIT.
    `edge_pct` is the expected advantage of acting: the target's edge for ENTER,
    the edge gained over the current holding for ROTATE, and 0 for an EXIT, which
    is taken to avoid a loss rather than to book a gain."""
    value = max(account_value_usd, 0.0)
    fee = value * fee_rate * fee_legs
    gross = value * edge_pct / 100.0
    return TradeEconomics(value, fee_legs, fee, gross, gross - fee)


@dataclass
class Recommendation:
    action: str             # ENTER | ROTATE | EXIT | HOLD
    from_base: Optional[str]
    to_base: Optional[str]
    rationale: str
    edge_pct: float
    strong: bool = False    # breakout-driven: engine may skip 2-scan confirmation
    economics: Optional[TradeEconomics] = None
    fee_blocked: bool = False  # cleared the % thresholds but not the dollar floor


class Predictor:
    def __init__(self, strategy: StrategyConfig, rotation: RotationConfig, mode: Optional[str] = None):
        self.strategy = strategy
        self.rotation = rotation
        self.mode = mode or config.SELECTION_MODE

    # ---- Scoring ----
    def score(self, stat: MarketStat, closes: List[float],
              vols: Optional[List[float]] = None) -> CoinScore:
        look = min(self.rotation.momentum_lookback, max(len(closes) - 1, 1))
        if len(closes) > look and closes:
            past = closes[len(closes) - 1 - look]
            last = closes[-1]
            momentum = (last - past) / past * 100 if past > 0 else 0.0
        else:
            momentum = stat.change_pct

        short_sma = signals.sma(closes, self.strategy.short_sma) or 0.0
        long_sma = signals.sma(closes, self.strategy.long_sma) or 0.0
        trend_up = short_sma > long_sma
        rsi = signals.rsi(closes, self.strategy.rsi_period)
        extension = (stat.last / short_sma - 1) * 100 if short_sma > 0 else 0.0
        breakout, roc, vol_surge = self._breakout(closes, vols, rsi)

        if self.mode == "anti_chasing":
            edge = self._edge_anti_chasing(momentum, trend_up, rsi, extension,
                                           breakout, roc)
        else:
            edge = self._edge_momentum(momentum, trend_up, rsi)

        return CoinScore(
            product_id=stat.product_id,
            base=stat.base,
            last=stat.last,
            change_24h=stat.change_pct,
            momentum=momentum,
            rsi=rsi,
            trend_up=trend_up,
            predicted_edge_pct=edge,
            breakout=breakout,
            roc=roc,
            vol_surge=vol_surge,
        )

    @staticmethod
    def _breakout(closes: List[float], vols: Optional[List[float]],
                  rsi: Optional[float]) -> tuple:
        """(is_breakout, roc_pct, vol_surge). A fresh hot run = fast short-term
        rate of change on surging volume, before the SMA cross can confirm it.
        Volume surge uses the max of the last two bars (the newest bar may be a
        partial hour) against the trailing 24h average."""
        bars = config.BREAKOUT_ROC_BARS
        roc = 0.0
        if len(closes) > bars and closes[-1 - bars] > 0:
            roc = (closes[-1] / closes[-1 - bars] - 1) * 100

        vol_surge = 0.0
        if vols and len(vols) >= 4:
            recent = max(vols[-1], vols[-2])
            baseline = vols[-26:-2] if len(vols) >= 26 else vols[:-2]
            avg = sum(baseline) / len(baseline) if baseline else 0.0
            vol_surge = recent / avg if avg > 0 else 0.0

        is_breakout = (
            roc >= config.BREAKOUT_ROC_MIN_PCT
            and vol_surge >= config.BREAKOUT_VOL_SURGE_MIN
            and rsi is not None
            and rsi < config.BREAKOUT_RSI_HARD_MAX
        )
        return is_breakout, roc, vol_surge

    def _edge_momentum(self, momentum, trend_up, rsi) -> float:
        edge = momentum
        if not trend_up:
            edge *= 0.3                                   # fade counter-trend moves
        if rsi is not None:
            if rsi >= self.strategy.rsi_overbought:
                edge *= 0.4                               # likely to revert
            elif rsi <= self.strategy.rsi_oversold and trend_up:
                edge *= 1.3                               # oversold bounce
        return edge

    def _edge_anti_chasing(self, momentum, trend_up, rsi, extension,
                           breakout: bool = False, roc: float = 0.0) -> float:
        # Breakout path: a fresh run qualified by ROC + volume surge. The SMA
        # cross lags a new run by 10-20h and the RSI/extension caps reject the
        # strong phase outright, so both are bypassed here — the trailing stop
        # is the risk control instead. Edge = the faster of 6h momentum and
        # short-term ROC, unpenalized.
        if breakout:
            return max(momentum, roc)
        # Pullback path: require an established uptrend with positive drift,
        # NOT overbought and NOT stretched far above the short SMA.
        # Disqualified coins get a large negative edge so they're never chosen.
        if not trend_up or momentum <= 0:
            return -999.0
        if rsi is None or rsi >= config.ANTI_RSI_MAX:
            return -999.0
        if extension > config.ANTI_EXTENSION_MAX:
            return -999.0
        return momentum - 1.5 * max(extension, 0.0)        # penalize extension

    def rank(self, scores: List[CoinScore]) -> List[CoinScore]:
        return sorted(scores, key=lambda s: s.predicted_edge_pct, reverse=True)

    def _hold_edge(self, s: CoinScore) -> float:
        """Edge of the coin already owned. The anti-chasing RSI/extension caps
        are ENTRY disqualifiers — applying them to a holding forced exits and
        rotations out of winning runs (a hot coin is overbought by definition).
        A holding only turns bad on a trend flip or momentum fade; the trailing
        stop in the engine handles profit protection."""
        if self.mode != "anti_chasing":
            return s.predicted_edge_pct
        if s.breakout:
            return s.predicted_edge_pct
        if not s.trend_up or s.momentum <= 0:
            return -999.0
        return s.momentum

    # ---- Recommendation ----
    def recommend(self, ranked: List[CoinScore], position_base: Optional[str],
                  fee_rate: float, account_value_usd: float = 0.0) -> Recommendation:
        """Pick the action. Every gain-seeking action has to clear its own
        trading cost twice over: once in percent (the rotation thresholds plus
        the round trip) and once in dollars (`MIN_NET_PROFIT_USD` of expected
        profit after fees), so a technically-qualifying edge that only amounts
        to pennies on this account never turns into a trade."""
        round_trip_cost_pct = fee_rate * 2 * 100
        min_net_usd = config.MIN_NET_PROFIT_USD
        best = ranked[0] if ranked else None

        # Currently in cash.
        if position_base is None:
            # Entering commits to a round trip — the coin has to be sold again —
            # so the edge must cover both legs, not just the entry fee.
            if best and best.predicted_edge_pct > self.rotation.enter_threshold_pct + round_trip_cost_pct:
                econ = trade_economics(account_value_usd, 2, best.predicted_edge_pct, fee_rate)
                if econ.net_gain_usd < min_net_usd:
                    return Recommendation(
                        "HOLD", None, None,
                        f"{best.base}'s {best.predicted_edge_pct:.1f}% edge is only "
                        f"${econ.gross_gain_usd:.2f} on ${econ.trade_value_usd:.2f}; "
                        f"${econ.fee_usd:.2f} of fees leaves ${econ.net_gain_usd:.2f}, under the "
                        f"${min_net_usd:.2f} minimum. Not worth the trade — staying in cash.",
                        best.predicted_edge_pct, economics=econ, fee_blocked=True,
                    )
                sign = "+" if best.change_24h >= 0 else ""
                what = "is breaking out" if best.breakout else "leads"
                return Recommendation(
                    "ENTER", None, best.base,
                    f"{best.base} {what} with a {best.predicted_edge_pct:.1f}% predicted edge "
                    f"(24h {sign}{best.change_24h:.1f}%): ~${econ.gross_gain_usd:.2f} on "
                    f"${econ.trade_value_usd:.2f} less ${econ.fee_usd:.2f} round-trip fees "
                    f"= ${econ.net_gain_usd:.2f} net.",
                    best.predicted_edge_pct,
                    strong=best.breakout,
                    economics=econ,
                )
            return Recommendation(
                "HOLD", None, None,
                "No coin clears the entry threshold. Staying in cash.",
                best.predicted_edge_pct if best else 0.0,
            )

        # Currently holding a coin.
        current = next((s for s in ranked if s.base == position_base), None)
        current_edge = self._hold_edge(current) if current else 0.0

        if current_edge < self.rotation.exit_threshold_pct:
            better_exists = bool(
                best and best.base != position_base
                and best.predicted_edge_pct > self.rotation.enter_threshold_pct
            )
            if not better_exists:
                # Protective, so it isn't gated on expected profit — but the cost
                # of the leg is still reported for the audit and the log.
                econ = trade_economics(account_value_usd, 1, 0.0, fee_rate)
                return Recommendation(
                    "EXIT", position_base, None,
                    f"{position_base} outlook turned negative ({current_edge:.1f}%). "
                    f"Move to cash to protect value (${econ.fee_usd:.2f} exit fee).",
                    current_edge, economics=econ,
                )

        if (
            best and best.base != position_base
            and best.predicted_edge_pct > current_edge + self.rotation.rotation_threshold_pct + round_trip_cost_pct
        ):
            # Floor the holding's edge at 0 for the dollar math: a disqualified
            # holding scores -999, which would otherwise project an absurd gain.
            gain_pct = best.predicted_edge_pct - max(current_edge, 0.0)
            econ = trade_economics(account_value_usd, 2, gain_pct, fee_rate)
            net_edge_pct = best.predicted_edge_pct - current_edge - round_trip_cost_pct
            if econ.net_gain_usd < min_net_usd:
                return Recommendation(
                    "HOLD", position_base, None,
                    f"{best.base} ({best.predicted_edge_pct:.1f}%) beats {position_base} "
                    f"({current_edge:.1f}%), but only by ${econ.gross_gain_usd:.2f} on "
                    f"${econ.trade_value_usd:.2f}; ${econ.fee_usd:.2f} of rotation fees leaves "
                    f"${econ.net_gain_usd:.2f}, under the ${min_net_usd:.2f} minimum. "
                    f"Holding {position_base}.",
                    net_edge_pct, economics=econ, fee_blocked=True,
                )
            return Recommendation(
                "ROTATE", position_base, best.base,
                f"{best.base} ({best.predicted_edge_pct:.1f}%) beats {position_base} "
                f"({current_edge:.1f}%) by more than the {round_trip_cost_pct:.1f}% round-trip cost: "
                f"~${econ.gross_gain_usd:.2f} of edge on ${econ.trade_value_usd:.2f} less "
                f"${econ.fee_usd:.2f} fees = ${econ.net_gain_usd:.2f} net.",
                net_edge_pct,
                strong=best.breakout,
                economics=econ,
            )

        return Recommendation(
            "HOLD", position_base, None,
            f"Holding {position_base} — still the best risk-adjusted pick ({current_edge:.1f}%).",
            current_edge,
        )


def select_candidates(stats: List[MarketStat], rotation: RotationConfig,
                      min_liquidity_usd: float, position_base: Optional[str],
                      seed_base: str, excluded_bases: Optional[set] = None) -> List[MarketStat]:
    """Liquid coins, plus the held coin, the seed, and BTC (for the regime check).

    In anti_chasing mode candidates are sorted by volume (not 24h gain) to avoid
    pre-biasing the pool toward coins that already pumped.

    Tokens in excluded_bases are filtered from the regular candidate pool.
    The current holding (position_base) is always included for scoring so the
    engine can decide to HOLD or EXIT even if the token is veto-excluded.
    seed_base is force-included only if not excluded."""
    excluded = excluded_bases or set()
    liquid = [s for s in stats if s.volume_usd >= min_liquidity_usd and s.base not in excluded]
    if config.SELECTION_MODE == "anti_chasing":
        liquid.sort(key=lambda s: s.volume_usd, reverse=True)
    else:
        liquid.sort(key=lambda s: s.change_pct, reverse=True)
    picked = list(liquid[: rotation.candidate_count])
    picked_bases = {s.base for s in picked}
    # Always include current holding for scoring (allow HOLD/EXIT even if vetoed).
    force_bases = [b for b in (position_base,) if b]
    # Force-include seed_base and BTC only when they clear the liquidity bar — prevents
    # entering a thin-market position just because it's the seed token. BTC nearly
    # always passes; seed tokens that lack real Coinbase liquidity are excluded.
    liquid_bases = {s.base for s in stats if s.volume_usd >= min_liquidity_usd}
    for b in (seed_base, "BTC"):
        if b and b not in excluded and b in liquid_bases:
            force_bases.append(b)
    for base in force_bases:
        if base not in picked_bases:
            extra = next((s for s in stats if s.base == base), None)
            if extra:
                picked.append(extra)
                picked_bases.add(base)
    return picked
