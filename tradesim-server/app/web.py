"""FastAPI dashboard: portfolio, P&L, trades, recommendations, and controls
(kill switch, dry-run/live toggle, run-now). Server-rendered, no build step."""
import json
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import (
    AuditLog, EquitySnapshot, Portfolio, Recommendation, ScanLog, Settings, Trade,
    SessionLocal, get_portfolio, get_settings, init_db,
)
from .engine import run_once

app = FastAPI(title="TradeSim Server")

# Icons / manifest for "Add to Home Screen" on iPhone live here.
_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/manifest.webmanifest")
def manifest():
    """Web app manifest so the dashboard installs as a standalone iPhone app."""
    return JSONResponse({
        "name": "TradeSim",
        "short_name": "TradeSim",
        "description": "Auto-rotation crypto trading dashboard.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0c2233",
        "theme_color": "#0c2233",
        "icons": [
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
    }, media_type="application/manifest+json")


@app.on_event("startup")
def _startup():
    init_db()


def _authorized(token: Optional[str]) -> bool:
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
def run_now(token: Optional[str] = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    run_once()
    return RedirectResponse("/", status_code=303)


@app.post("/toggle/enabled")
def toggle_enabled(token: Optional[str] = Form(default=None)):
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
def toggle_dry_run(token: Optional[str] = Form(default=None), confirm: Optional[str] = Form(default=None)):
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


@app.post("/toggle/audit")
def toggle_audit(token: Optional[str] = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    with SessionLocal() as s:
        st = get_settings(s)
        st.audit_enabled = not st.audit_enabled
        s.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/set/interval")
def set_interval(value: int = Form(...), token: Optional[str] = Form(default=None)):
    if not _authorized(token):
        return RedirectResponse("/?err=auth", status_code=303)
    if value in config.INTERVAL_CHOICES:
        with SessionLocal() as s:
            st = get_settings(s)
            st.interval_minutes = value
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
        all_trades = s.query(Trade).all()
        realized = sum(t.realized_pnl or 0.0 for t in all_trades)
        fees_total = sum(getattr(t, "fee_usd", 0.0) or 0.0 for t in all_trades)
        equity = (
            s.query(EquitySnapshot).order_by(EquitySnapshot.id.desc()).limit(300).all()
        )
        equity = list(reversed(equity))  # oldest-first for the chart
        audits = s.query(AuditLog).order_by(AuditLog.id.desc()).limit(8).all()
        err = request.query_params.get("err")
        return HTMLResponse(
            _render(st, pf, rec, recs, trades, last_scan, realized, fees_total, equity, audits, err)
        )


# ---------- rendering ----------

_KNOB_ANGLES = {15: -135, 30: -45, 45: 45, 60: 135}


def _knob(interval: int, token_field: str) -> str:
    """A retro rotary knob with 15/30/45/60-minute stops. Each stop is a tiny
    form that posts the new cadence; the needle points to the current stop."""
    cur_angle = _KNOB_ANGLES.get(interval, -135)
    stops = ""
    for v, a in _KNOB_ANGLES.items():
        active = "active" if v == interval else ""
        stops += (
            f"<form class='stop {active}' method='post' action='/set/interval' "
            f"style='transform:translate(-50%,-50%) rotate({a}deg) translate(0,-92px) rotate({-a}deg)'>"
            f"{token_field}<input type='hidden' name='value' value='{v}'>"
            f"<button type='submit'>{v}</button></form>"
        )
    return (
        "<div class='knobwrap'>"
        "<div class='knob'>"
        f"<div class='needle' style='transform:translate(-50%,-100%) rotate({cur_angle}deg)'></div>"
        "<div class='knobcap'></div>"
        f"{stops}"
        "</div>"
        f"<div class='knobread'><span class='big'>{interval}</span><span class='unit'>min</span>"
        "<span class='cap'>cycle cadence</span></div>"
        "</div>"
    )


def _render(st: Settings, pf: Portfolio, rec, recs, trades, last_scan, realized, fees_total,
            equity, audits, err: Optional[str] = None) -> str:
    total = pf.total_value
    ret = total - st.starting_balance
    ret_pct = (ret / st.starting_balance * 100) if st.starting_balance else 0.0
    holding = pf.pos_base or "USD (cash)"
    up = ret >= 0

    # Holding detail: explains value moves between trades (mark-to-market).
    if pf.has_position and pf.pos_quantity > 0:
        cur_price = pf.pos_mark_price
        entry_price = pf.pos_cost_basis_usd / pf.pos_quantity if pf.pos_quantity else 0.0
        upnl = pf.position_value - pf.pos_cost_basis_usd
        upnl_pct = (upnl / pf.pos_cost_basis_usd * 100) if pf.pos_cost_basis_usd else 0.0
        upnl_class = "pos" if upnl >= 0 else "neg"
        min_h = getattr(st, "min_hold_hours", 6)
        held_line = ""
        opened = getattr(pf, "pos_opened_at", None)
        if opened is not None:
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            age_h = (datetime.now(timezone.utc) - opened).total_seconds() / 3600
            locked = " 🔒" if age_h < min_h else ""
            held_line = f"<span>held {age_h:.1f}h · min {min_h}h{locked}</span>"
        holding_detail = (
            f"<div class='hdetail'>"
            f"<span>price ${cur_price:,.6f}</span>"
            f"<span>entry ${entry_price:,.6f}</span>"
            f"<span class='{upnl_class}'>unrealized ${upnl:+,.2f} ({upnl_pct:+.1f}%)</span>"
            f"{held_line}"
            f"</div>"
        )
    else:
        holding_detail = "<div class='hdetail'><span>in USD cash</span></div>"

    mode_badge = (
        '<span class="badge live">● LIVE</span>' if not st.dry_run
        else '<span class="badge dry">◐ DRY-RUN</span>'
    )
    enabled_badge = (
        '<span class="badge on">▶ TRADING ON</span>' if st.enabled
        else '<span class="badge off">⏸ TRADING OFF</span>'
    )
    audit_on = getattr(st, "audit_enabled", False)
    audit_badge = (
        '<span class="badge audit">✦ AI AUDIT ON</span>' if audit_on
        else '<span class="badge off">AI AUDIT OFF</span>'
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

    if st.dry_run:
        dry_run_form = (
            f'<form class="inline" method="post" action="/toggle/dry-run">{token_field}'
            f'<input class="tok" type="text" name="confirm" placeholder="type LIVE" '
            f'autocomplete="off" required>'
            f'<button class="warn">Go LIVE</button></form>'
        )
    else:
        dry_run_form = (
            f'<form class="inline" method="post" action="/toggle/dry-run">{token_field}'
            f'<button class="ghost">Back to DRY-RUN</button></form>'
        )

    # Latest recommendation, with an animated edge meter.
    if rec:
        edge_w = max(0.0, min(abs(rec.edge_pct) / 15.0, 1.0)) * 100  # scale to 0..100%
        rec_html = (
            f"<div class='rec rec-{rec.action.lower()}'>"
            f"<div class='rec-top'><span class='action'>{rec.action}</span>"
            f"<span class='edge'>edge {rec.edge_pct:+.2f}%</span></div>"
            f"<div class='rationale'>{_esc(rec.rationale)}</div>"
            f"<div class='meter'><span style='width:{edge_w:.0f}%'></span></div>"
            f"<div class='muted small'>{_ago(rec.ts)}</div>"
            f"</div>"
        )
    else:
        rec_html = "<p class='muted'>No recommendation yet.</p>"

    trade_rows = "".join(
        f"<tr><td>{_ago(t.ts)}</td><td class='{ 'buy' if t.action=='BUY' else 'sell'}'>{t.action}</td>"
        f"<td>{_esc(t.base)}</td><td>{t.quantity:.6f}</td><td>${t.price:,.6f}</td>"
        f"<td>${t.cash_flow:,.2f}</td>"
        f"<td class='muted'>${(getattr(t, 'fee_usd', 0.0) or 0.0):.2f}</td>"
        f"<td>{('$%+.2f' % t.realized_pnl) if t.realized_pnl is not None else '—'}</td>"
        f"<td><span class='badge {'live' if t.mode=='LIVE' else 'dry'}'>{t.mode}</span></td></tr>"
        for t in trades
    ) or "<tr><td colspan='9' class='muted'>No trades yet.</td></tr>"

    rec_rows = "".join(
        f"<li><b>{r.action}</b> {_esc(r.rationale)} <span class='muted'>({_ago(r.ts)})</span></li>"
        for r in recs
    ) or "<li class='muted'>None yet.</li>"

    pending = bool(last_scan and last_scan.note and "awaiting_confirmation" in last_scan.note)
    scan_line = ""
    if last_scan:
        scan_line = (
            f"<p class='muted small'>Last scan {_ago(last_scan.ts)} · {last_scan.candidates} candidates"
            + (" · <span class='pending'>awaiting 2nd-scan confirmation</span>" if pending else "")
            + (f" · <span class='err'>error: {_esc(last_scan.error)}</span>" if last_scan.error else "")
            + "</p>"
        )

    floor_note = (
        f"balance floor ${st.balance_floor_usd:,.2f} · " if st.balance_floor_usd > 0 else ""
    )

    audit_form = (
        f'<form class="inline" method="post" action="/toggle/audit">{token_field}'
        f'<button class="ghost">{"Disable AI audit" if audit_on else "Enable AI audit"}</button></form>'
    )
    # Compact summary of the most recent AI audit decision (shown under the rec).
    if audit_on and audits:
        a0 = audits[0]
        cls = "veto" if a0.verdict == "VETO" else "pos"
        icon = "⛔" if a0.verdict == "VETO" else "✓"
        tgt = f" {a0.action}{(' → ' + _esc(a0.to_base)) if a0.to_base else ''}" if a0.action else ""
        audit_summary = (
            f"<div class='auditsum {cls}'><span class='av'>{icon} AI audit: {a0.verdict}</span>"
            f"<span class='muted'>{tgt} — {_esc(a0.reason)} · {_ago(a0.ts)}</span></div>"
        )
    elif audit_on:
        audit_summary = "<div class='auditsum muted'>AI audit on — no decision logged yet.</div>"
    else:
        audit_summary = ""

    if audits:
        audit_rows = "".join(
            f"<li><b class='{ 'veto' if a.verdict=='VETO' else 'buy'}'>{a.verdict}</b> "
            f"{a.action}{(' → ' + _esc(a.to_base)) if a.to_base else ''} — {_esc(a.reason)} "
            f"<span class='muted'>({_ago(a.ts)})</span></li>"
            for a in audits
        )
        audit_section = f"<h2>AI audit log</h2><ul>{audit_rows}</ul>"
    else:
        audit_section = ""

    # Chart data.
    eq_labels = [e.ts.strftime("%m/%d %H:%M") for e in equity]
    eq_values = [round(e.total_value, 4) for e in equity]
    eq_holdings = [e.holding or "USD" for e in equity]
    equity_json = json.dumps({"labels": eq_labels, "values": eq_values, "holdings": eq_holdings})
    alloc_json = json.dumps({
        "cash": round(pf.cash, 4),
        "position": round(pf.position_value, 4),
        "holding": pf.pos_base or "Cash",
    })
    baseline_json = json.dumps(round(st.starting_balance, 4))

    interval = getattr(st, "interval_minutes", config.INTERVAL_MINUTES_DEFAULT)
    knob = _knob(interval, token_field)

    ctx = {
        "fees_total": f"{fees_total:,.2f}",
        "knob": knob,
        "seed": config.SEED_BASE,
        "start": f"{st.starting_balance:,.2f}",
        "floor_note": floor_note,
        "mode_badge": mode_badge,
        "enabled_badge": enabled_badge,
        "audit_badge": audit_badge,
        "audit_form": audit_form,
        "audit_section": audit_section,
        "audit_summary": audit_summary,
        "total": f"{total:,.2f}",
        "total_raw": f"{total:.4f}",
        "ret": f"{ret:+,.2f}",
        "ret_pct": f"{ret_pct:+.1f}",
        "ret_class": "pos" if up else "neg",
        "holding": _esc(holding),
        "holding_detail": holding_detail,
        "realized": f"{realized:+,.2f}",
        "err_banner": err_banner,
        "dry_run_form": dry_run_form,
        "token_field": token_field,
        "enabled_btn_class": "warn" if st.enabled else "go",
        "enabled_btn_label": "Turn trading OFF" if st.enabled else "Turn trading ON",
        "rec_html": rec_html,
        "scan_line": scan_line,
        "trade_rows": trade_rows,
        "rec_rows": rec_rows,
        "equity_json": equity_json,
        "alloc_json": alloc_json,
        "baseline_json": baseline_json,
    }
    return Template(_PAGE).safe_substitute(ctx)


# Palette (coolors): d9ed92 b5e48c 99d98c 76c893 52b69a 34a0a4 168aad 1a759f 1e6091 184e77
_PAGE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TradeSim</title>
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#0c2233">
<link rel="icon" type="image/png" sizes="32x32" href="/static/favicon-32.png">
<link rel="apple-touch-icon" href="/static/apple-touch-icon.png">
<!-- iPhone: run full-screen with a dark status bar when added to Home Screen -->
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="TradeSim">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
<style>
  :root {
    --lime:#d9ed92; --grass:#b5e48c; --leaf:#99d98c; --jade:#76c893; --teal:#52b69a;
    --aqua:#34a0a4; --sea:#168aad; --ocean:#1a759f; --deep:#1e6091; --navy:#184e77;
    --bg:#0c2233; --panel:#10314a; --panel2:#0e2a40; --line:#1d4663;
    --text:#e8f3ee; --muted:#8fb3bf; --pos:#99d98c; --neg:#f4978e;
    color-scheme: dark;
  }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    color:var(--text); line-height:1.45;
    -webkit-text-size-adjust:100%;
    -webkit-tap-highlight-color:rgba(82,182,154,.2);
    background:
      radial-gradient(1200px 600px at 15% -10%, rgba(82,182,154,.18), transparent 60%),
      radial-gradient(1000px 500px at 110% 10%, rgba(22,138,173,.20), transparent 55%),
      var(--bg);
    min-height:100vh; }
  /* Respect the iPhone notch / home indicator when run as a Home Screen app. */
  .wrap { max-width: 920px; margin:0 auto;
    padding: calc(26px + env(safe-area-inset-top)) calc(18px + env(safe-area-inset-right))
             calc(72px + env(safe-area-inset-bottom)) calc(18px + env(safe-area-inset-left)); }
  .head { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  /* Refresh button — iPhone web apps can't pull-to-refresh, so reload from here. */
  .refresh { margin-left:auto; flex:none; width:40px; height:40px; border-radius:50%;
    display:inline-flex; align-items:center; justify-content:center; text-decoration:none;
    font-size:20px; line-height:1; color:#06202a;
    background:linear-gradient(180deg,var(--leaf),var(--teal));
    box-shadow:0 6px 16px rgba(82,182,154,.25);
    transition:transform .25s ease, filter .12s ease; }
  .refresh:hover { transform:rotate(90deg); filter:brightness(1.05); }
  .refresh:active { transform:rotate(180deg); }
  h1 { font-size:24px; margin:0; font-weight:800; letter-spacing:-.02em;
    background:linear-gradient(90deg,var(--lime),var(--jade),var(--aqua),var(--sea));
    background-size:300% 100%; -webkit-background-clip:text; background-clip:text;
    -webkit-text-fill-color:transparent; animation:shimmer 8s ease infinite; }
  @keyframes shimmer { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
  .sub { color:var(--muted); font-size:13px; margin:6px 0 22px; }
  .badge { display:inline-block; padding:4px 10px; border-radius:999px; font-size:11px; font-weight:800;
    letter-spacing:.04em; }
  .badge.live { background:rgba(244,151,142,.16); color:#f4978e; }
  .badge.dry  { background:rgba(82,182,154,.18); color:var(--leaf); }
  .badge.on   { background:rgba(153,217,140,.18); color:var(--grass); }
  .badge.off  { background:rgba(143,179,191,.14); color:var(--muted); }
  .badge.audit { background:rgba(52,160,164,.20); color:var(--aqua); }
  .veto { color:#f4978e; font-weight:700; }
  .badge.live { animation:pulse 1.8s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.55} }

  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:18px; }
  .card { background:linear-gradient(160deg,var(--panel),var(--panel2));
    border:1px solid var(--line); border-radius:16px; padding:18px;
    box-shadow:0 10px 30px rgba(0,0,0,.25); opacity:0; transform:translateY(10px);
    animation:rise .6s cubic-bezier(.2,.7,.2,1) forwards; }
  .card:nth-child(2){ animation-delay:.08s } .card:nth-child(3){ animation-delay:.16s }
  @keyframes rise { to { opacity:1; transform:none } }
  .card .label { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }
  .card .value { font-size:26px; font-weight:800; margin-top:6px; letter-spacing:-.01em; }
  .value.pos { color:var(--pos); } .value.neg { color:var(--neg); }
  .holding-chip { display:inline-block; margin-top:6px; font-size:18px; font-weight:700; }
  .hdetail { display:flex; flex-direction:column; gap:2px; margin-top:8px; font-size:12px; color:var(--muted); }
  .hdetail .pos { color:var(--pos); } .hdetail .neg { color:var(--neg); }

  .panel { background:linear-gradient(160deg,var(--panel),var(--panel2));
    border:1px solid var(--line); border-radius:16px; padding:18px; margin-bottom:18px;
    box-shadow:0 10px 30px rgba(0,0,0,.22);
    opacity:0; transform:translateY(10px); animation:rise .6s ease forwards .12s; }
  .charts { display:grid; grid-template-columns:2fr 1fr; gap:14px; }
  @media (max-width:640px){
    .charts{ grid-template-columns:1fr } .grid{ grid-template-columns:1fr }
    h1{ font-size:21px } .cbox{ height:200px }
    /* Trades fit the screen width: smaller type and cells wrap to a second
       line instead of scrolling sideways. */
    th,td{ padding:7px 5px; font-size:11px; }
    .tradespanel{ padding:12px; }
    /* On phones only: bound to ~10 rows and scroll vertically (sticky header).
       The panel keeps non-scrolling side gutters so swiping the edges scrolls
       the whole page rather than the inner table. */
    .tscroll{ max-height:24rem; overflow-y:auto; overflow-x:hidden;
      -webkit-overflow-scrolling:touch; }
    .tscroll thead th{ position:sticky; top:0; background:var(--panel2);
      box-shadow:inset 0 -1px 0 var(--line); z-index:2; }
    /* Controls become full-width, comfortably tappable rows. */
    .controls{ gap:8px; }
    .controls form.inline, .controls button{ width:100%; }
    .controls button{ padding:13px 15px; }
    /* Stack the knob above its readout so the row never overflows narrow screens. */
    .knobwrap{ flex-direction:column; gap:14px; align-items:flex-start; }
    .knobread .big{ font-size:32px; }
  }
  .chart-title { font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 10px; }
  .cbox { position:relative; height:240px; }
  .cbox canvas { position:absolute; inset:0; }

  .controls { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:6px 0 20px; }
  form.inline { display:inline-flex; gap:8px; align-items:center; }
  button { color:#06202a; border:0; border-radius:11px; padding:10px 15px; font-size:14px; font-weight:700;
    cursor:pointer; transition:transform .12s ease, box-shadow .12s ease, filter .12s ease;
    background:linear-gradient(180deg,var(--leaf),var(--teal)); box-shadow:0 6px 16px rgba(82,182,154,.25); }
  button:hover { transform:translateY(-1px); filter:brightness(1.05); box-shadow:0 10px 22px rgba(82,182,154,.35); }
  button.ghost { background:rgba(143,179,191,.12); color:var(--text); box-shadow:none; border:1px solid var(--line); }
  button.go { background:linear-gradient(180deg,var(--grass),var(--jade)); }
  button.warn { background:linear-gradient(180deg,#f4978e,#e5675b); color:#2a0d0a; box-shadow:0 6px 16px rgba(229,103,91,.3); }
  .tok { background:var(--bg); border:1px solid var(--line); color:var(--text); border-radius:9px; padding:9px; }

  .rec { padding:16px; border-radius:14px; background:var(--panel2); border-left:4px solid var(--teal);
    box-shadow:0 8px 20px rgba(0,0,0,.2); }
  .rec-top { display:flex; justify-content:space-between; align-items:center; }
  .rec .action { font-weight:800; letter-spacing:.03em; }
  .rec .edge { font-variant-numeric:tabular-nums; color:var(--muted); font-size:13px; }
  .rec .rationale { margin:8px 0; font-size:14px; }
  .rec-enter, .rec-rotate { border-left-color:var(--grass); }
  .rec-exit { border-left-color:#f4b16e; }
  .rec-hold { border-left-color:var(--ocean); }
  .meter { height:6px; border-radius:999px; background:rgba(255,255,255,.08); overflow:hidden; }
  .meter > span { display:block; height:100%; width:0;
    background:linear-gradient(90deg,var(--teal),var(--lime));
    animation:fill 1s cubic-bezier(.2,.7,.2,1) forwards .2s; }
  @keyframes fill { from{ width:0 } }

  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { text-align:left; padding:9px 6px; border-bottom:1px solid var(--line); font-variant-numeric:tabular-nums; }
  th { color:var(--muted); font-weight:700; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }
  tbody tr { transition:background .12s ease; } tbody tr:hover { background:rgba(82,182,154,.07); }
  .tradespanel { padding:14px 20px; }
  .buy { color:var(--grass); font-weight:700; } .sell { color:var(--neg); font-weight:700; }
  .muted { color:var(--muted); } .small { font-size:12px; } .err { color:var(--neg); }
  .banner { background:rgba(244,151,142,.14); color:#ffd0c9; border:1px solid rgba(244,151,142,.35);
    border-radius:12px; padding:11px 14px; margin-bottom:14px; font-size:13px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:26px 0 10px; }
  ul { padding-left:18px; } li { margin-bottom:6px; font-size:13px; }
  .disclaimer { margin-top:30px; font-size:12px; color:var(--muted); opacity:.8; }
  .pending { color:var(--lime); font-weight:600; }
  .auditsum { margin:10px 0 0; padding:9px 12px; border-radius:10px; font-size:13px;
    background:rgba(52,160,164,.10); border:1px solid var(--line);
    display:flex; gap:8px; flex-wrap:wrap; align-items:baseline; }
  .auditsum .av { font-weight:800; letter-spacing:.02em; }
  .auditsum.pos .av { color:var(--grass); } .auditsum.veto .av { color:var(--neg); }
  /* Retro cadence knob */
  .knobwrap { display:flex; align-items:center; gap:26px; padding:8px 4px; }
  .knob { position:relative; width:184px; height:184px; border-radius:50%;
    background:
      radial-gradient(circle at 50% 38%, #20465c 0%, #0d2638 62%, #08202f 100%);
    border:1px solid #2a5871;
    box-shadow: inset 0 3px 12px rgba(0,0,0,.6), inset 0 -2px 8px rgba(82,182,154,.15),
                0 10px 26px rgba(0,0,0,.4); }
  .knob .needle { position:absolute; left:50%; top:50%; width:5px; height:72px;
    transform-origin:50% 100%; border-radius:3px;
    background:linear-gradient(var(--lime), var(--teal));
    box-shadow:0 0 10px rgba(217,237,146,.6); transition:transform .5s cubic-bezier(.2,.8,.2,1); }
  .knob .knobcap { position:absolute; left:50%; top:50%; width:46px; height:46px;
    transform:translate(-50%,-50%); border-radius:50%;
    background:radial-gradient(circle at 40% 35%, #3a6b82, #12303f);
    border:1px solid #2a5871; box-shadow:inset 0 1px 3px rgba(255,255,255,.15); }
  .knob .stop { position:absolute; left:50%; top:50%; margin:0; }
  .knob .stop button { width:34px; height:34px; border-radius:50%; padding:0;
    font-size:12px; font-weight:800; cursor:pointer; color:var(--text);
    background:rgba(13,38,56,.7); border:1px solid var(--line); box-shadow:none; }
  .knob .stop button:hover { transform:translateY(-1px); filter:brightness(1.15); }
  .knob .stop.active button { background:linear-gradient(180deg,var(--lime),var(--teal));
    color:#06202a; border-color:var(--lime); box-shadow:0 0 12px rgba(217,237,146,.5); }
  .knobread { display:flex; flex-direction:column; line-height:1; }
  .knobread .big { font-size:40px; font-weight:800; color:var(--lime); }
  .knobread .unit { font-size:14px; color:var(--muted); margin-top:2px; }
  .knobread .cap { font-size:11px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--muted); margin-top:10px; }
</style></head>
<body><div class="wrap">
  <div class="head"><h1>TradeSim</h1> $mode_badge $enabled_badge $audit_badge
    <a class="refresh" href="/" aria-label="Refresh" title="Refresh">⟳</a></div>
  <div class="sub">Seed $seed · started at $$${start} · ${floor_note}auto-rotation strategy</div>

  <div class="grid">
    <div class="card"><div class="label">Total Value</div>
      <div class="value" data-countup="$total_raw" data-prefix="1">$$${total}</div></div>
    <div class="card"><div class="label">Total Return</div>
      <div class="value $ret_class">$$${ret} <span class="small">($ret_pct%)</span></div></div>
    <div class="card"><div class="label">Holding</div>
      <div class="holding-chip">$holding</div>$holding_detail</div>
  </div>

  <div class="panel charts">
    <div>
      <p class="chart-title">Portfolio value</p>
      <div class="cbox"><canvas id="equity"></canvas></div>
    </div>
    <div>
      <p class="chart-title">Allocation</p>
      <div class="cbox"><canvas id="alloc"></canvas></div>
    </div>
  </div>

  $err_banner
  <div class="controls">
    <form class="inline" method="post" action="/toggle/enabled">$token_field
      <button class="$enabled_btn_class">$enabled_btn_label</button></form>
    $dry_run_form
    $audit_form
    <form class="inline" method="post" action="/run-now">$token_field
      <button class="ghost">Run cycle now</button></form>
  </div>

  <div class="panel"><p class="chart-title">Cadence — how often it trades</p>$knob</div>

  <h2>Latest recommendation</h2>
  $rec_html
  $audit_summary
  $scan_line

  <h2>Recent trades</h2>
  <div class="panel tradespanel">
    <div class="tscroll">
    <table>
      <thead><tr><th>When</th><th>Side</th><th>Coin</th><th>Qty</th><th>Price</th><th>Cash flow</th><th>Fee</th><th>P&amp;L</th><th>Mode</th></tr></thead>
      <tbody>$trade_rows</tbody>
    </table></div>
  </div>
  <p class="muted small">Realized P&amp;L to date: $$${realized} · Fees paid to date: $$${fees_total}</p>

  <h2>Recommendation history</h2>
  <ul>$rec_rows</ul>

  $audit_section

  <p class="disclaimer">Personal paper/auto-trading tool. Not financial advice.
  In DRY-RUN no real orders are placed. In LIVE, orders execute on Coinbase with a Trade-scoped key.</p>
</div>

<script>
const EQUITY = $equity_json;
const ALLOC = $alloc_json;
const BASELINE = $baseline_json;
const D = String.fromCharCode(36); // dollar sign
const P = { lime:'#d9ed92', leaf:'#99d98c', jade:'#76c893', teal:'#52b69a',
            aqua:'#34a0a4', sea:'#168aad', ocean:'#1a759f', muted:'#8fb3bf' };

// Animated count-up for the Total Value stat.
document.querySelectorAll('[data-countup]').forEach(function(el){
  const target = parseFloat(el.getAttribute('data-countup')) || 0;
  const pre = el.getAttribute('data-prefix') ? D : '';
  const dur = 900; const t0 = performance.now();
  function fmt(n){ return n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
  function step(now){
    const k = Math.min((now - t0)/dur, 1);
    const e = 1 - Math.pow(1 - k, 3);
    el.textContent = pre + fmt(target * e);
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
});

if (!window.Chart) {
  document.querySelectorAll('.cbox').forEach(function(b){
    b.innerHTML = '<p class="muted small">Charts unavailable (Chart.js failed to load).</p>';
  });
}
if (window.Chart) {
  Chart.defaults.color = P.muted;
  Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif';

  // Equity curve with a teal->lime gradient fill.
  const ec = document.getElementById('equity').getContext('2d');
  const grad = ec.createLinearGradient(0, 0, 0, 220);
  grad.addColorStop(0, 'rgba(82,182,154,0.45)');
  grad.addColorStop(1, 'rgba(82,182,154,0.02)');
  const hasData = EQUITY.values.length > 0;
  new Chart(ec, {
    type: 'line',
    data: { labels: hasData ? EQUITY.labels : ['start'],
      datasets: [{
        data: hasData ? EQUITY.values : [BASELINE],
        borderColor: P.lime, borderWidth: 2.5, fill: true, backgroundColor: grad,
        tension: 0.35, pointRadius: 0, pointHoverRadius: 4, pointHoverBackgroundColor: P.lime,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 1100, easing: 'easeOutCubic' },
      interaction: { intersect: false, mode: 'index' },
      plugins: { legend: { display: false },
        tooltip: { callbacks: {
          label: function(c){ return D + c.parsed.y.toFixed(2); },
          afterLabel: function(c){
            var h = (EQUITY.holdings || [])[c.dataIndex];
            return h ? ('holding ' + h) : '';
          }
        } } },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 6 } },
        y: { grid: { color: 'rgba(143,179,191,0.10)' },
             ticks: { callback: function(v){ return D + v.toFixed(2); } } }
      }
    }
  });

  // Allocation doughnut: cash vs current position.
  const acx = document.getElementById('alloc').getContext('2d');
  new Chart(acx, {
    type: 'doughnut',
    data: { labels: ['Cash', ALLOC.holding],
      datasets: [{ data: [ALLOC.cash, ALLOC.position],
        backgroundColor: [P.sea, P.jade], borderColor: 'rgba(0,0,0,0)', borderWidth: 0,
        hoverOffset: 6 }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: '66%',
      animation: { animateRotate: true, duration: 1100 },
      plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, padding: 14 } },
        tooltip: { callbacks: { label: function(c){ return c.label + ': ' + D + c.parsed.toFixed(2); } } } } }
  });
}
</script>
</body></html>"""


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
