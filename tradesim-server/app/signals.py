"""Technical-indicator math. Direct port of TradeSim/Services/SignalEngine.swift."""
from __future__ import annotations

from typing import Optional, Sequence


def sma(values: Sequence[float], period: int) -> Optional[float]:
    """Simple moving average of the most recent `period` values."""
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / float(period)


def rsi(values: Sequence[float], period: int) -> Optional[float]:
    """Wilder's RSI over the supplied series (matches the Swift implementation)."""
    if period <= 0 or len(values) <= period:
        return None

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change

    avg_gain = gains / period
    avg_loss = losses / period

    if len(values) > period + 1:
        for i in range(period + 1, len(values)):
            change = values[i] - values[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
