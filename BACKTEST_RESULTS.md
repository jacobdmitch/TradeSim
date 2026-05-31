# Backtest Results — Buy-Selection Variants (preliminary)

Window: ~11.3 days of hourly candles, 26 most-liquid Coinbase USD coins (+DIMO).
Start $100, 0.6%/leg fee, 2-scan confirmation. **Past data, not predictive.**

| strategy | return | final $ | trades | fees $ | max DD |
|---|---:|---:|---:|---:|---:|
| current (momentum / top gainers) | +46.15% | 146.15 | 77 | 42.74 | 40.9% |
| mean_reversion | 0.00% | 100.00 | 0 | 0.00 | 0.0% |
| cash | 0.00% | 100.00 | 0 | 0.00 | 0.0% |
| hold_dimo | −8.44% | 91.56 | 1 | 0.60 | 12.2% |
| anti_chasing | −25.49% | 74.51 | 65 | 36.68 | 34.6% |

## How to read this (carefully)

- **Turnover/fees is the dominant, robust finding.** The two active strategies paid
  **$42.74 and $36.68 in fees on a $100 account in 11 days** — 35–43% of capital
  burned on trading costs. No selection rule survives that. This is the clearest,
  most reliable signal in the whole test and it matches the live experience.
- **The "current" +46% is almost certainly window luck, not edge.** It came with a
  40.9% max drawdown and 77 trades. A strategy that can be +46% or −40% depending
  on the fortnight is high-variance noise; in your live run the same logic is
  losing because this is a different (weaker) window. Do not trust this number.
- **mean_reversion never traded** — my entry gates (uptrend AND RSI ≤ 42) were too
  strict for this window/universe, so it's inconclusive, not "safe."
- **hold_dimo −8.4%** confirms DIMO drifted down over the window (consistent with
  what you've seen).

## Why this isn't enough to pick a selection philosophy yet

1. **11 days is far too short** — one regime, heavy luck. We need multiple weeks and
   ideally walk-forward across several windows.
2. **Survivorship/selection bias** — the universe is "coins liquid *today*," replayed
   backward.
3. **No minimum-hold** — all active strategies churn every few bars, so the test is
   really measuring turnover cost more than selection quality.

## Recommendation

1. **Cut turnover first — the data already proves it's the killer.** Add a minimum
   hold period (e.g., don't switch for N hours after entering) and keep the higher
   rotation threshold. This is supported regardless of which selection rule wins.
2. **Then settle selection with a better backtest:** longer history (paginate to
   ~30–60 days), a minimum-hold in the harness, looser mean-reversion gates, and
   walk-forward across windows so we're not fooled by a single lucky fortnight.

Bottom line: don't flip the selection logic based on this run — the +46% is a
mirage. The proven, bankable change is to **trade far less often**. Lock that in,
then re-run a longer backtest to choose the entry philosophy on evidence.
