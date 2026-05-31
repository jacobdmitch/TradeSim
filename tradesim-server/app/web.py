"""FastAPI dashboard: portfolio, P&L, trades, recommendations, and controls
(kill switch, dry-run/live toggle, run-now). Server-rendered, no build step."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from . import config
from .db import (
    Portfolio, Recommendation, ScanLog, Settings, Trade,
    SessionLocal, get_portfolio, get_settings, init_db,
)
from .engine import run_once

app = FastAPI(title="TradeSim Server")


@app.on_event("startup")
def _startup():
    init_db()


def _authorized(token: str | None) -> bool:
    if not config.DASHBOARD_TOKEN:
        return True
    return token == config.DASHBOARD_TOKEN


@app.get("/healthz")
def healthz():
    return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/api/state")
def api_state():
    with SessionLocal() as s:
        st = get_settings(s)
        pf = get_portfolio(s)
        rec = s.query(Recommendation).order_by(Recommendation.id.desc()).first()
        trades = s.query(Trade).order_by(Trade.id.desc()).limit(50).all()
        realized = sum(t.realized_pnl or 0.0 for t in s.query(Trade).all())
        return JSONResponse({
            "enabled": st.enabled,
            "dry_run": st.dry_run,
            "seeded": st.seeded,
            "starting_balance": st.starting_balance,
            "balance_floor_usd": st.balance_floor_usd,
            "cash": pf.cash,
            "holding": pf.pos_base,
            "position_value": pf.position_value,
            "total_value": pf.total_value,
            "total_return": pf.total_value - st.starting_balance,
            "total_return_pct": ((pf.total_value - st.starting_balance) / st.starting_balance * 100)
            if st.starting_balance else 0.0,
            "realized_pnl": realized,
            "latest_recommendation": _rec_dict(rec),
            "trades": [_trade_dict(t) for t in trades],
        })


@app.post("/run-now")
def run_now(token: str | None = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    run_once()
    return RedirectResponse("/", status_code=303)


@app.post("/toggle/enabled")
def toggle_enabled(token: str | None = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    with SessionLocal() as s:
        st = get_settings(s)
        st.enabled = not st.enabled
        # Turning trading OFF also reverts to dry-run, so re-enabling later can't
        # silently resume live trading — going live stays a deliberate action.
        if not st.enabled:
            st.dry_run = True
        s.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/toggle/dry-run")
def toggle_dry_run(token: str | None = Form(default=None), confirm: str | None = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    with SessionLocal() as s:
        st = get_settings(s)
        # Going dry-run -> LIVE is the dangerous direction: require typing LIVE.
        if st.dry_run:
            if (confirm or "").strip().upper() != "LIVE":
                return RedirectResponse("/?err=confirm", status_code=303)
        st.dry_run = not st.dry_run
        s.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    with SessionLocal() as s:
        st = get_settings(s)
        pf = get_portfolio(s)
        rec = s.query(Recommendation).order_by(Recommendation.id.desc()).first()
        recs = s.query(Recommendation).order_by(Recommendation.id.desc()).limit(10).all()
        trades = s.query(Trade).order_by(Trade.id.desc()).limit(25).all()
        last_scan = s.query(ScanLog).order_by(ScanLog.id.desc()).first()
        realized = sum(t.realized_pnl or 0.0 for t in s.query(Trade).all())
        err = request.query_params.get("err")
        return HTMLResponse(_render(st, pf, rec, recs, trades, last_scan, realized, err))


# ---------- rendering ----------

def _render(st: Settings, pf: Portfolio, rec, recs, trades, last_scan, realized, err: str | None = None) -> str:
    total = pf.total_value
    ret = total - st.starting_balance
    ret_pct = (ret / st.starting_balance * 100) if st.starting_balance else 0.0
    holding = pf.pos_base or "USD (cash)"
    ret_color = "#16c784" if ret >= 0 else "#ea3943"

    mode_badge = (
        '<span class="badge live">LIVE</span>' if not st.dry_run
        else '<span class="badge dry">DRY-RUN</span>'
    )
    enabled_badge = (
        '<span class="badge on">TRADING ON</span>' if st.enabled
        else '<span class="badge off">TRADING OFF</span>'
    )
    token_field = (
        '<input class="tok" type="password" name="token" placeholder="control token" required>'
        if config.DASHBOARD_TOKEN else ""
    )

    err_messages = {
        "confirm": "Type LIVE in the box to switch to live trading.",
        "auth": "Wrong control token.",
    }
    err_banner = (
        f'<div class="banner">{_esc(err_messages[err])}</div>'
        if err in err_messages else ""
    )

    # Going to LIVE requires typing the word LIVE; going back to DRY-RUN is one click.
    if st.dry_run:
        dry_run_form = (
            f'<form class="inline" method="post" action="/toggle/dry-run">{token_field}'
            f'<input class="tok" type="text" name="confirm" placeholder="type LIVE" '
            f'autocomplete="off" required>'
            f'<button class="warn">Switch to LIVE</button></form>'
        )
    else:
        dry_run_form = (
            f'<form class="inline" method="post" action="/toggle/dry-run">{token_field}'
            f'<button class="ghost">Switch to DRY-RUN</button></form>'
        )

    rec_html = "<p class='muted'>No recommendation yet.</p>"
    if rec:
        rec_html = (
            f"<div class='rec rec-{rec.action.lower()}'>"
            f"<span class='action'>{rec.action}</span>"
            f"<span class='rationale'>{_esc(rec.rationale)}</span>"
            f"<span class='muted'>edge {rec.edge_pct:+.2f}% · {_ago(rec.ts)}</span>"
            f"</div>"
        )

    trade_rows = "".join(
        f"<tr><td>{_ago(t.ts)}</td><td class='{ 'buy' if t.action=='BUY' else 'sell'}'>{t.action}</td>"
        f"<td>{_esc(t.base)}</td><td>{t.quantity:.6f}</td><td>${t.price:,.6f}</td>"
        f"<td>${t.cash_flow:,.2f}</td>"
        f"<td>{('$%+.2f' % t.realized_pnl) if t.realized_pnl is not None else '—'}</td>"
        f"<td><span class='badge {'live' if t.mode=='LIVE' else 'dry'}'>{t.mode}</span></td></tr>"
        for t in trades
    ) or "<tr><td colspan='8' class='muted'>No trades yet.</td></tr>"

    rec_rows = "".join(
        f"<li><b>{r.action}</b> {_esc(r.rationale)} <span class='muted'>({_ago(r.ts)})</span></li>"
        for r in recs
    ) or "<li class='muted'>None yet.</li>"

    scan_line = ""
    if last_scan:
        scan_line = (
            f"<p class='muted'>Last scan {_ago(last_scan.ts)} · {last_scan.candidates} candidates"
            + (f" · <span class='err'>error: {_esc(last_scan.error)}</span>" if last_scan.error else "")
            + "</p>"
        )

    floor_note = (
        f"Balance floor: ${st.balance_floor_usd:,.2f}. " if st.balance_floor_usd > 0 else ""
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradeSim</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:#0b0f17; color:#e6e9ef; line-height:1.45; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 24px 18px 64px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color:#8b94a7; font-size: 13px; margin-bottom: 20px; }}
  .grid {{ display:grid; grid-template-columns: repeat(3,1fr); gap:12px; margin-bottom:20px; }}
  .card {{ background:#141a26; border:1px solid #1f2838; border-radius:14px; padding:16px; }}
  .card .label {{ color:#8b94a7; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
  .card .value {{ font-size:22px; font-weight:600; margin-top:4px; }}
  .badge {{ display:inline-block; padding:3px 9px; border-radius:999px; font-size:11px; font-weight:700;
           letter-spacing:.03em; }}
  .badge.live {{ background:#3a1620; color:#ff6b81; }}
  .badge.dry  {{ background:#14233a; color:#5ac8fa; }}
  .badge.on   {{ background:#0f2e22; color:#16c784; }}
  .badge.off  {{ background:#2a2f3a; color:#9aa3b2; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:10px 0 22px; }}
  form.inline {{ display:inline-flex; gap:8px; align-items:center; }}
  button {{ background:#1f6feb; color:#fff; border:0; border-radius:10px; padding:9px 14px;
           font-size:14px; font-weight:600; cursor:pointer; }}
  button.ghost {{ background:#202a3a; }}
  button.warn {{ background:#b4232f; }}
  .tok {{ background:#0b0f17; border:1px solid #2a3242; color:#e6e9ef; border-radius:8px; padding:8px; }}
  .rec {{ display:flex; flex-direction:column; gap:4px; padding:14px; border-radius:12px; background:#141a26;
         border-left:4px solid #5ac8fa; }}
  .rec .action {{ font-weight:700; }}
  .rec-enter, .rec-rotate {{ border-left-color:#16c784; }}
  .rec-exit {{ border-left-color:#f0a13a; }}
  .rec-hold {{ border-left-color:#5a6678; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 6px; border-bottom:1px solid #1b2333; }}
  th {{ color:#8b94a7; font-weight:600; font-size:11px; text-transform:uppercase; }}
  .buy {{ color:#16c784; font-weight:600; }} .sell {{ color:#ea3943; font-weight:600; }}
  .muted {{ color:#8b94a7; }} .err {{ color:#ff6b81; }}
  .banner {{ background:#3a1620; color:#ffb3c0; border:1px solid #5a2230; border-radius:10px;
            padding:10px 14px; margin-bottom:14px; font-size:13px; }}
  h2 {{ font-size:14px; text-transform:uppercase; letter-spacing:.04em; color:#8b94a7; margin:26px 0 10px; }}
  ul {{ padding-left:18px; }} li {{ margin-bottom:6px; font-size:13px; }}
  .disclaimer {{ margin-top:30px; font-size:12px; color:#6b7587; }}
</style></head>
<body><div class="wrap">
  <h1>TradeSim {mode_badge} {enabled_badge}</h1>
  <div class="sub">Seed {config.SEED_BASE} · started at ${st.starting_balance:,.2f} · {floor_note}10-min cron strategy</div>

  <div class="grid">
    <div class="card"><div class="label">Total Value</div><div class="value">${total:,.2f}</div></div>
    <div class="card"><div class="label">Total Return</div>
      <div class="value" style="color:{ret_color}">${ret:+,.2f} ({ret_pct:+.1f}%)</div></div>
    <div class="card"><div class="label">Holding</div><div class="value">{_esc(holding)}</div></div>
  </div>

  {err_banner}
  <div class="controls">
    <form class="inline" method="post" action="/toggle/enabled">{token_field}
      <button class="{ 'warn' if st.enabled else ''}">{ 'Turn trading OFF' if st.enabled else 'Turn trading ON'}</button></form>
    {dry_run_form}
    <form class="inline" method="post" action="/run-now">{token_field}
      <button class="ghost">Run cycle now</button></form>
  </div>

  <h2>Latest recommendation</h2>
  {rec_html}
  {scan_line}

  <h2>Recent trades</h2>
  <table>
    <thead><tr><th>When</th><th>Side</th><th>Coin</th><th>Qty</th><th>Price</th><th>Cash flow</th><th>P&amp;L</th><th>Mode</th></tr></thead>
    <tbody>{trade_rows}</tbody>
  </table>
  <p class="muted" style="margin-top:8px">Realized P&amp;L to date: ${realized:+,.2f}</p>

  <h2>Recommendation history</h2>
  <ul>{rec_rows}</ul>

  <p class="disclaimer">Personal paper/auto-trading tool. Not financial advice.
  In DRY-RUN no real orders are placed. In LIVE, orders execute on Coinbase with a Trade-scoped key.</p>
</div></body></html>"""


def _rec_dict(r):
    if not r:
        return None
    return {"action": r.action, "from_base": r.from_base, "to_base": r.to_base,
            "rationale": r.rationale, "edge_pct": r.edge_pct, "ts": r.ts.isoformat()}


def _trade_dict(t):
    return {"ts": t.ts.isoformat(), "action": t.action, "base": t.base, "price": t.price,
            "quantity": t.quantity, "cash_flow": t.cash_flow, "realized_pnl": t.realized_pnl,
            "mode": t.mode, "order_id": t.order_id}


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _ago(ts: datetime) -> str:
    if ts is None:
        return "—"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"
