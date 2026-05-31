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
  market data, score candidates, decide, and (if enabled) place orders.
- **Web service** (`app/web.py`) — dashboard: portfolio, P&L, trade log,
  recommendation history, and the controls (kill switch, dry-run/live, run-now).
- **Postgres** — stores settings, the portfolio, trades, recommendations, scans.

```
tradesim-server/
  run_cycle.py        # cron entrypoint
  run_web.py          # web entrypoint (uvicorn app.web:app)
  render.yaml         # Render blueprint (db + cron + web)
  app/
    config.py         # strategy params + env-driven runtime settings
    market.py         # Coinbase public data (port of MarketDataService.swift)
    signals.py        # SMA / RSI (port of SignalEngine.swift)
    predictor.py      # scoring + rotation decision (port of Predictor.swift)
    broker.py         # dry-run + live order execution
    db.py             # SQLAlchemy models (Postgres / local SQLite)
    engine.py         # one full cycle, with kill switch + balance floor
    web.py            # FastAPI dashboard
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

Strategy parameters live in `app/config.py` (`StrategyConfig`, `RotationConfig`,
`FEE_RATE`, `MIN_LIQUIDITY_USD`) and match the iOS app's defaults. Change the
cron cadence in `render.yaml` (`schedule`).

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
