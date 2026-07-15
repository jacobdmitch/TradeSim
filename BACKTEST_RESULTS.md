# Backtest Results — Buy-Selection Variants

Latest run: ~24.4 days of hourly candles, 16 most-liquid Coinbase USD coins (+DIMO).
Start $100, 0.6%/leg fee, 2-scan confirmation, 6h minimum-hold. **Past data, not predictive.**

| strategy | return | final $ | trades | fees $ | max DD |
|---|---:|---:|---:|---:|---:|
| **cash (do nothing)** | **0.00%** | **100.00** | 0 | 0.00 | 0.0% |
| anti_chasing | −2.14% | 97.86 | 99 | 66.53 | 31.1% |
| hold_dimo | −16.66% | 83.34 | 1 | 0.60 | 22.6% |
| current (momentum/top-gainers) | −31.47% | 68.53 | 117 | 60.55 | 44.8% |
| mean_reversion | −49.31% | 50.69 | 83 | 36.62 | 49.8% |

### Walk-forward (return % within each ~8-day sub-window)

| strategy | seg1 | seg2 | seg3 |
|---|---:|---:|---:|
| current | +5.5 | −21.8 | −16.2 |
| anti_chasing | +20.0 | +3.4 | −22.5 |
| mean_reversion | −9.0 | −29.8 | −20.2 |
| hold_dimo | +0.4 | −15.5 | −0.4 |

## What this says (straight)

1. **Doing nothing beat every active strategy.** Over ~24 days, cash (0%) outperformed
   the current logic (−31%), anti-chasing (−2%), mean-reversion (−49%), and even
   holding DIMO (−17%). This is the opposite of the lucky 11-day window and is the
   more trustworthy result.
2. **No variant is consistently positive.** Walk-forward shows every active strategy
   has at least one badly negative sub-window; anti-chasing was strong early then
   gave it all back. None shows a durable edge.
3. **Fees are still the dominant drag — even with the new guards.** The 2-scan
   confirm and 6h min-hold did not stop the churn, because the strategies hop
   *through cash* (buy → drop → sell to cash → buy something else). current and
   anti-chasing each burned ~$60–66 of a $100 account in fees over 24 days.
4. **The alt market was broadly down** in this window, so rotating among falling
   coins compounded losses on top of fees.

## Honest conclusion

The evidence does **not** support any of the selection philosophies as a money-maker
in current conditions at this size. Changing *what* it buys isn't the fix — the
rotation approach itself is value-destructive here, and the best outcome in the
sample was to **not trade**. I would not take any of these live.

## Options from here

- **Regime filter (most promising):** only deploy out of cash when conditions are
  favorable (e.g., BTC and a majority of the universe in an uptrend); otherwise sit
  in cash. In this window that would have kept results near 0% instead of −31%.
- **Much heavier turnover brakes:** apply the min-hold to *all* position changes
  (including re-entry after a cash hop), require a far larger edge to act, and trade
  on a slower cadence — accept far fewer trades.
- **Keep it as a paper/learning tool:** leave it in dry-run; treat profit as unlikely
  at $23 in choppy alt markets and use it to study signals rather than to earn.

Recommendation: add the regime filter + all-changes min-hold, re-run this backtest,
and only revisit live trading if a variant is *consistently* positive across
walk-forward windows. Until then, stay in dry-run.

---

## Update — with regime filter + all-changes brake (same 24.4-day window)

Regime filter = only deploy when BTC is up and ≥50% of the universe is trending up;
otherwise sit in cash. Brake = min-hold applied to every position change (blocks
the cash-hopping churn).

| strategy | return | final $ | trades | fees $ | max DD |
|---|---:|---:|---:|---:|---:|
| **anti_chasing + regime + brakes** | **+6.26%** | **106.26** | 57 | 40.61 | 26.2% |
| cash | 0.00% | 100.00 | 0 | 0.00 | 0.0% |
| hold_dimo | −16.66% | 83.34 | 1 | 0.60 | 22.6% |
| mean_reversion + rg | −24.64% | 75.36 | 35 | 18.61 | 25.1% |
| current + rg | −26.92% | 73.08 | 65 | 33.26 | 41.7% |
| current (raw, no regime) | −31.47% | 68.53 | 117 | 60.55 | 44.8% |

Walk-forward (return % per ~8-day window):

| strategy | seg1 | seg2 | seg3 |
|---|---:|---:|---:|
| anti+rg | +33.3 | −20.5 | −0.9 |
| current+rg | +8.0 | −31.1 | −1.0 |
| meanrev+rg | −4.0 | −15.2 | −6.9 |

### Read

- **The regime filter clearly helps.** It cut trades and drawdown across the board
  and flipped anti-chasing from −2% to **+6% (the only variant to beat cash)**.
  current improved from −31% to −27%.
- **But it's still not a durable edge.** anti+rg's entire gain came from one 8-day
  window (+33%); it lost 20% in another. That front-loaded pattern is the same
  warning sign — one good regime, not a repeatable advantage. Fees are still ~$40
  on $100.
- **Verdict:** anti-chasing + regime + brakes is the best candidate by a clear
  margin, and worth carrying forward, but the inconsistency means it is **not yet a
  green light for live money**. The right next test is forward paper-trading
  (out-of-sample), not just more backtests.

---

## Update — breakout entries + trailing stop + hold-edge fix (July 2026)

Live experience with anti+rg: realized P&L ≈ break-even (−$0.44) but ~$9 of a
$23 account burned in fees. Diagnosis: the entry stack (SMA9>21 cross, RSI<68,
extension≤6%, 2-scan confirm) lags a fresh run by 10–20h, so the bot buys the
first eligible pullback near the top, stops out, re-enters — churn without edge.

Changes (livev2 = live logic in app/predictor.py + app/engine.py):

- **Breakout entry path:** 3h ROC ≥ 3% + volume ≥ 2× the 24h average + RSI < 85
  qualifies a fresh run immediately, bypassing the SMA-cross/RSI/extension entry
  guards and the 2-scan confirmation.
- **Trailing stop 5%:** immediate exit when price falls 5% below its peak since
  entry — locks in runs instead of waiting for the lagging SMA flip.
- **Hold-edge fix:** the RSI/extension caps are entry disqualifiers only; they no
  longer force exits/rotations out of a winning (overbought-by-definition) run.
- **Entry bar raised 0.5% → 2.0%:** a 0.5% edge never covered the 1.2% round-trip
  fee; marginal entries were pure fee burn.

Same harness, ~27.5-day window (June–July 2026, broadly falling alt market):

| variant | return | trades | fees $ | max DD |
|---|---:|---:|---:|---:|
| cash | 0.00% | 0 | 0.00 | 0.0% |
| hold_dimo | −20.03% | 1 | 0.60 | 32.8% |
| anti+rg (old live) | −24.37% | 59 | 30.41 | 27.1% |
| **livev2+rg+trail (new live)** | **−24.74%** | **35** | **18.54** | 27.9% |
| livev2 no-trail (ablation) | −30.54% | 35 | 17.92 | 33.4% |
| current+rg | −66.92% | 53 | 23.58 | 68.0% |

Walk-forward (livev2: −8.0 / −8.9 / −10.2 vs anti+rg: −9.7 / −9.3 / −8.5) —
equally consistent, no single-window luck.

### Read (straight)

1. **The churn/fee goal is met:** 41% fewer trades and 39% lower fees for the
   same return as the old live logic in the identical window.
2. **The trailing stop is load-bearing:** identical entries without it lose 6
   points more. Early entries only work with a fast mechanical exit.
3. **This window had no sustained hot runs** — a falling market is the worst
   case for the breakout path, and it still matched the old logic while paying
   half the fees. The thesis (catch runs early, exit near peak) is untested in
   an up-market window; forward paper-trading is the real test.
4. **Nothing beat cash in this window.** The regime gate reduced damage but
   still deployed into dead-cat bounces. Unchanged conclusion: not a green
   light for live money.
