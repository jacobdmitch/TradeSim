# TradeSim Server

A headless, always-on version of the TradeSim strategy that runs on Render
instead of an iPhone, so it can trade around the clock (an iOS app can't run a
background trading loop; a server can). It reuses the same strategy as the app
(SMA/RSI/momentum scoring and fee-aware rotation) and adds real order execution
via the Coinbase Advanced Trade API.

Starts in **paper mode** and with **trading disabled**. Nothing touches real
money until you explicitly flip both switches from the dashboard.

## Architecture

- **Cron job** (`run_cycle.py`) — runs one cycle every 10 minutes: pull Coinbase
  market data, score candidates, decide, and (if enabled) place orders. Every
  row it writes that cycle (scan, recommendation, audit, trade, equity) shares
  a `trace_id`, so a trade can be traced back to the scan/reasoning behind it.
- **Tuning cron job** (`run_improve.py`) — runs once a day: backtests the live
  rotation thresholds against recent market history and, if a nearby variant
  clearly beats them, nudges them (bounded step, logged, never touches the
  kill switch or dry-run/live). See "Tracing & self-improvement" below.
- **Web service** (`app/web.py`) — dashboard: portfolio, P&L, trade log,
  recommendation history, and the controls (kill switch, dry-run/live, run-now).
  Tap the candidate count under the recommendation to see the ranked shortlist
  the last scan weighed. Tuned for iPhone: open it in Safari and **Share → Add
  to Home Screen** to run it full-screen as a standalone web app with the icon.
- **Postgres** — stores settings, the portfolio, trades, recommendations, scans,
  and the strategy-tuning history.

```
tradesim-server/
  run_cycle.py        # cron entrypoint
  run_improve.py      # daily tuning-loop cron entrypoint
  run_web.py          # web entrypoint (uvicorn app.web:app)
  backtest.py         # backtesting harness, also used by the tuning loop
  render.yaml         # Render blueprint (db + cron + tuning cron + web)
  app/
    config.py         # strategy params + env-driven runtime settings
    market.py         # Coinbase public data (port of MarketDataService.swift)
    signals.py        # SMA / RSI (port of SignalEngine.swift)
    predictor.py      # scoring + rotation decision (port of Predictor.swift)
    broker.py         # dry-run + live order execution
    db.py             # SQLAlchemy models (Postgres / local SQLite)
    engine.py         # one full cycle, with kill switch + balance floor
    improve.py        # self-improvement loop: backtest, decide, log, apply
    web.py            # FastAPI dashboard
    static/           # web app icons + favicon (Add to Home Screen)
```

## Safety model

1. **Two switches, both default OFF/paper.** `TRADING_ENABLED=false` means the
   cron analyzes and logs but never orders. `DRY_RUN=true` simulates fills with
   the same fee math as the app. You must turn trading ON *and* switch to LIVE
   to risk real funds.
2. **Trade-only API key.** Scope the Coinbase CDP key to **Trade**. Do **not**
   grant transfer/withdraw, so a leaked key or bug can never move funds out of
   your account.
3. **Balance floor.** `BALANCE_FLOOR_USD` halts new entries/rotations once total
   value drops to/below it (a protective exit-to-cash is still allowed).
4. **Acts only on a changed recommendation**, same as the app — it won't churn.
5. **Switching modes starts a fresh run.** Flipping DRY-RUN ↔ LIVE (or turning
   trading OFF, which also reverts to DRY-RUN) re-baselines and clears the
   dashboard to the new run (prior trades/recs/equity are kept in the DB but
   hidden), then runs one cycle immediately so the new state shows at once:
   - **→ LIVE:** the next cycle adopts your real Coinbase balances and holdings
     as the starting point, with return % and P&L measured from there.
   - **→ DRY-RUN (incl. trading OFF):** snapshots the current account value as
     the new baseline and paper-trades forward from the holdings on hand.

## Coinbase API key

1. Go to the Coinbase Developer Platform → API Keys → create a key.
2. **Permissions: Trade only.** No transfer/withdraw.
3. Key type: Ed25519 (recommended) or ECDSA — the SDK handles JWT signing.
4. You get a key *name* (`organizations/.../apiKeys/...`) and a private key PEM.
   Put the name in `COINBASE_API_KEY` and the PEM in `COINBASE_API_SECRET`
   (escaped `\n` newlines are fine).

## Deploy on Render

1. The active Blueprint is `render.yaml` at the **repository root** (Render only
   reads `render.yaml` from the repo root, never a subfolder). It already sets
   `rootDir: tradesim-server` on both services, so the trader and dashboard build
   and run from this folder. Commit and push it to your `main` branch.
2. Render Dashboard → **New → Blueprint** → select the repo and `main` branch. It
   reads the root `render.yaml` and creates the Postgres DB, cron job, and dashboard.
3. In each service's **Environment**, set the secrets marked `sync: false`:
   `COINBASE_API_KEY`, `COINBASE_API_SECRET`, and optionally `DASHBOARD_TOKEN`.
4. Open the dashboard URL. It will already be tracking your seeded $23.17 DIMO
   position in **DRY-RUN**. Let it run a few days and confirm the paper results
   look sane.
5. When ready: dashboard → **Turn trading ON**, then **Switch to LIVE**.

## Run locally

```bash
cd tradesim-server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # leave DATABASE_URL blank to use local SQLite

python run_cycle.py           # one dry-run cycle
uvicorn app.web:app --reload  # dashboard at http://127.0.0.1:8000
```

## Tuning

Most strategy parameters live in `app/config.py` (`StrategyConfig`,
`FEE_RATE`, `MIN_LIQUIDITY_USD`, `MIN_NET_PROFIT_USD`). The four rotation
thresholds — `enter_threshold_pct`, `rotation_threshold_pct`,
`exit_threshold_pct`, `trailing_stop_pct` — instead live in the DB
(`StrategyParams`, a singleton row) so the self-improvement loop can retune
them; see below. Change the cron cadence in `render.yaml` (`schedule`).

## Tracing & self-improvement

Every row written during a trading cycle (scan, recommendation, audit,
trade, equity snapshot) carries the same `trace_id`, so a trade can be
traced back end-to-end to the scan and reasoning that produced it —
join on `trace_id` across the `scans`/`recommendations`/`audits`/`trades`/
`equity` tables, or filter `/api/state`'s `trades`/`latest_recommendation`
by it.

A separate daily cron (`run_improve.py` → `app/improve.py`) closes the loop:
it backtests the live rotation thresholds against recent real market history
(reusing `backtest.py`'s walk-forward harness), then backtests a small
neighborhood of nearby variants. If one clearly and consistently beats what's
live — by a minimum margin, scored on the worst walk-forward segment so a
lucky single window can't win — it nudges `StrategyParams` a bounded step
toward it (never a jump) and logs the change (old value, new value, the
metrics that justified it) to `StrategyChangeLog`, shown on the dashboard
under "Strategy tuning". Each parameter has a hard-coded min/max range and a
24h cooldown between changes.

This loop can only retune existing thresholds — it never touches the
`TRADING_ENABLED`/`DRY_RUN` kill switches, so it can't turn trading on or
take it live on its own.

## Fee gate (what makes a trade worth doing)

Percent thresholds alone hide fee drag on a small balance: at ~0.6%/leg a $27
position pays ~$0.32 per round trip, so a 0.2% "edge" is 5c of upside against
32c of cost. Every gain-seeking action therefore has to clear its trading cost
twice over:

1. **In percent** — an ENTER needs `enter_threshold_pct` *plus the full round
   trip* (the coin has to be sold again, so the decision owns both legs, not
   just the entry fee). A ROTATE needs `rotation_threshold_pct` plus the round
   trip on top of the current holding's edge.
2. **In dollars** — expected profit after fees must be at least
   `MIN_NET_PROFIT_USD` (default $0.25). Below that the trade is dropped to HOLD
   and the scan note records `fee_gate:net$X<$Y`.

A protective EXIT is exempt from both — moving to cash to stop a loss is priced
as a cost, not a profit — but its fee is still reported in the rationale.

The same numbers (traded value, fee legs, estimated fee, expected gross and net)
are handed to the Claude pre-trade audit, which can veto an action that cannot
pay for itself.

## Rotation routing (fee minimization)

When the strategy rotates from one coin to another in **LIVE** mode, it picks the
cheaper of two paths per trade:

- **Two order-book legs** (sell→USD→buy on Advanced Trade): no spread, ~0.6% fee
  per leg.
- **Coinbase Convert** (single step): one step, but Coinbase bakes a spread into
  the rate on top of fees.

It fetches a live Convert quote, compares how much value each path retains, and
uses Convert only if it strictly keeps more and the commit confirms — otherwise
it falls back to the two legs. If a Convert is chosen but can't be confirmed, the
cycle does nothing and the next cycle reconciles from real balances (no double
execution). DRY-RUN always uses the two-leg model.

## Reality check

This trades a tiny balance in a thin market. After ~0.6%/leg fees and DIMO's
spread, the rotation strategy has to clear a real cost hurdle every trade. Watch
the DRY-RUN results against simply holding DIMO before going live. Not financial
advice.
