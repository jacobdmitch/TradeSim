"""Coin scoring and rotation recommendation.

Direct port of TradeSim/Services/Predictor.swift. The "prediction" is an
explicit, transparent heuristic blending momentum, SMA trend and RSI into a
single short-term edge. It is a screening tool, never a guarantee.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from . import signals
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


@dataclass
class Recommendation:
    action: str             # ENTER | ROTATE | EXIT | HOLD
    from_base: Optional[str]
    to_base: Optional[str]
    rationale: str
    edge_pct: float


class Predictor:
    def __init__(self, strategy: StrategyConfig, rotation: RotationConfig):
        self.strategy = strategy
        self.rotation = rotation

    # ---- Scoring ----
    def score(self, stat: MarketStat, closes: List[float]) -> CoinScore:
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

        edge = momentum
        if not trend_up:
            edge *= 0.3                                   # fade counter-trend moves
        if rsi is not None:
            if rsi >= self.strategy.rsi_overbought:
                edge *= 0.4                               # likely to revert
            elif rsi <= self.strategy.rsi_oversold and trend_up:
                edge *= 1.3                               # oversold bounce

        return CoinScore(
            product_id=stat.product_id,
            base=stat.base,
            last=stat.last,
            change_24h=stat.change_pct,
            momentum=momentum,
            rsi=rsi,
            trend_up=trend_up,
            predicted_edge_pct=edge,
        )

    def rank(self, scores: List[CoinScore]) -> List[CoinScore]:
        return sorted(scores, key=lambda s: s.predicted_edge_pct, reverse=True)

    # ---- Recommendation ----
    def recommend(self, ranked: List[CoinScore], position_base: Optional[str], fee_rate: float) -> Recommendation:
        round_trip_cost_pct = fee_rate * 2 * 100
        best = ranked[0] if ranked else None

        # Currently in cash.
        if position_base is None:
            if best and best.predicted_edge_pct > self.rotation.enter_threshold_pct + fee_rate * 100:
                sign = "+" if best.change_24h >= 0 else ""
                return Recommendation(
                    "ENTER", None, best.base,
                    f"{best.base} leads with a {best.predicted_edge_pct:.1f}% predicted edge "
                    f"(24h {sign}{best.change_24h:.1f}%).",
                    best.predicted_edge_pct,
                )
            return Recommendation(
                "HOLD", None, None,
                "No coin clears the entry threshold. Staying in cash.",
                best.predicted_edge_pct if best else 0.0,
            )

        # Currently holding a coin.
        current = next((s for s in ranked if s.base == position_base), None)
        current_edge = current.predicted_edge_pct if current else 0.0

        if current_edge < self.rotation.exit_threshold_pct:
            better_exists = bool(
                best and best.base != position_base
                and best.predicted_edge_pct > self.rotation.enter_threshold_pct
            )
            if not better_exists:
                return Recommendation(
                    "EXIT", position_base, None,
                    f"{position_base} outlook turned negative ({current_edge:.1f}%). "
                    f"Move to cash to protect value.",
                    current_edge,
                )

        if (
            best and best.base != position_base
            and best.predicted_edge_pct > current_edge + self.rotation.rotation_threshold_pct + round_trip_cost_pct
        ):
            return Recommendation(
                "ROTATE", position_base, best.base,
                f"{best.base} ({best.predicted_edge_pct:.1f}%) beats {position_base} "
                f"({current_edge:.1f}%) by more than the {round_trip_cost_pct:.1f}% round-trip cost.",
                best.predicted_edge_pct - current_edge - round_trip_cost_pct,
            )

        return Recommendation(
            "HOLD", position_base, None,
            f"Holding {position_base} — still the best risk-adjusted pick ({current_edge:.1f}%).",
            current_edge,
        )


def select_candidates(stats: List[MarketStat], rotation: RotationConfig,
                      min_liquidity_usd: float, position_base: Optional[str],
                      seed_base: str) -> List[MarketStat]:
    """Liquid top movers plus the current holding and the seed coin."""
    liquid = [s for s in stats if s.volume_usd >= min_liquidity_usd]
    liquid.sort(key=lambda s: s.change_pct, reverse=True)
    picked = list(liquid[: rotation.candidate_count])
    picked_bases = {s.base for s in picked}
    for base in [b for b in (position_base, seed_base) if b]:
        if base not in picked_bases:
            extra = next((s for s in stats if s.base == base), None)
            if extra:
                picked.append(extra)
                picked_bases.add(base)
    return picked
