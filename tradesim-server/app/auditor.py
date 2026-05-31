"""Optional pre-trade audit with Claude.

A veto-only safety layer. Before the engine executes a non-HOLD action, Claude
reviews the numbers the strategy already produced and checks recent news on the
coin (via Anthropic's web search tool). It can only APPROVE the action or
downgrade it to HOLD — it can never create, enlarge, or change a trade.

Design rules:
  - Fail-open: any error, timeout, missing key, or unparseable reply => APPROVE
    (used=False). A Claude outage must never freeze or distort trading.
  - It audits data integrity + obvious traps + adverse news only. It is NOT a
    price predictor; the quantitative edge stays with the deterministic engine.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from . import config

log = logging.getLogger("tradesim.auditor")


@dataclass
class AuditResult:
    used: bool          # did the audit actually run and return a verdict?
    approved: bool      # True = proceed, False = downgrade to HOLD
    reason: str
    model: Optional[str] = None


_SYSTEM = (
    "You are a risk auditor for a tiny automated crypto trading bot. You do NOT "
    "predict prices. The bot has already chosen an action using its own momentum/"
    "RSI/trend math. Your only job is to catch reasons the action is unsafe to "
    "execute RIGHT NOW:\n"
    "  1. Data integrity: prices/volume/momentum that look anomalous, stale, or "
    "internally inconsistent (e.g. a huge 'gain' on near-zero volume = thin-book "
    "artifact).\n"
    "  2. Liquidity traps: the target coin is far too illiquid to enter/exit cleanly.\n"
    "  3. Adverse news: use web search to check for very recent delisting, exchange "
    "removal, hack/exploit, depeg, team/rug events, or trading halts for the coin.\n"
    "Approve by default. Only veto (downgrade to HOLD) when you find a concrete, "
    "specific problem — never on vague caution. "
    'Reply with ONLY a JSON object: {"verdict":"approve"|"hold","reason":"<one short sentence>"}.'
)


def audit(action: str, to_base: Optional[str], from_base: Optional[str],
          payload: dict, audit_enabled: bool) -> AuditResult:
    """Return an AuditResult. Never raises."""
    if not audit_enabled:
        return AuditResult(used=False, approved=True, reason="audit disabled")
    if not config.ANTHROPIC_API_KEY:
        return AuditResult(used=False, approved=True, reason="no ANTHROPIC_API_KEY (fail-open)")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=40.0, max_retries=1)
        coin = to_base or from_base or "the held coin"
        user = (
            f"Pending action: {action}"
            + (f" into {to_base}" if to_base else "")
            + (f" out of {from_base}" if from_base else "")
            + ".\n\nStrategy figures (JSON):\n"
            + json.dumps(payload, indent=2)
            + f"\n\nSearch the web for the latest news on the {coin} crypto token "
            "(symbol may map to a project name) and audit this action. "
            "Return only the JSON verdict."
        )
        resp = client.messages.create(
            model=config.AUDIT_MODEL,
            max_tokens=800,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            tools=[{"type": "web_search_20250305", "name": "web_search",
                    "max_uses": config.AUDIT_MAX_SEARCHES}],
        )
        text = _final_text(resp)
        verdict, reason = _parse_verdict(text)
        if verdict is None:
            return AuditResult(used=False, approved=True,
                               reason="unparseable audit reply (fail-open)", model=config.AUDIT_MODEL)
        approved = verdict == "approve"
        return AuditResult(used=True, approved=approved, reason=reason or verdict, model=config.AUDIT_MODEL)

    except Exception as e:  # noqa: BLE001 - fail open on anything
        log.warning("audit failed, proceeding without veto: %s", e)
        return AuditResult(used=False, approved=True, reason=f"audit error: {e} (fail-open)")


def _final_text(resp) -> str:
    """Concatenate the model's text blocks, ignoring tool-use/result blocks."""
    parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(parts).strip()


def _parse_verdict(text: str):
    """Extract (verdict, reason) from the model's JSON reply. Tolerant of stray text."""
    if not text:
        return None, ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, ""
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None, ""
    verdict = str(obj.get("verdict", "")).strip().lower()
    reason = str(obj.get("reason", "")).strip()
    if verdict not in {"approve", "hold"}:
        return None, reason
    return verdict, reason
