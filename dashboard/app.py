from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

from agents.logging import LoggingAgent
from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import Severity

DATABASE_PATH = str(PROJECT_ROOT / "data" / "site_sense.db")
SOURCE_LABELS = {
    "ppe": "PPE",
    "ppe_coverage": "PPE coverage",
    "heat_compliance": "Heat compliance",
    "heat_wbgt": "Heat exposure",
}
STATUS_LABELS = {
    "active": "Active",
    "acknowledged": "Acknowledged",
    "resolved": "Resolved",
}
VISIBLE_ALERT_LIMIT = 10
PPE_ALERT_SLOTS = 4
REFERENCE_IMAGE_DIR = PROJECT_ROOT / "data" / "reference_ppe"
REFERENCE_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
LOGO_PATH = PROJECT_ROOT / "dashboard" / "assets" / "logo.png"
HEAT_TAXONOMY_PATH = PROJECT_ROOT / "taxonomy" / "heat_thresholds.md"
PPE_CORE_ITEMS = ("helmet", "gloves", "boots", "goggles", "vest")
MONITORED_SOURCES = {"ppe", "ppe_coverage", "heat_compliance", "heat_wbgt"}
PPE_ITEM_KEYS = {"no_goggle": "goggles", "goggle": "goggles"}
REFERENCE_WIDTH = 200
ALERT_DETAIL_HEIGHT = 320
PPE_ITEM_LABELS = {
    "helmet": "helmet",
    "gloves": "gloves",
    "vest": "hi-vis vest",
    "boots": "safety boots",
    "goggles": "eye protection",
    "no_goggle": "eye protection",
}
BUILT_IN_GUIDELINES: dict[str, dict[str, Any]] = {
    "no_helmet": {
        "title": "No helmet response protocol",
        "steps": [
            "Stop the worker from entering or continuing in the active work zone",
            "Issue a compliant safety helmet before work resumes",
            "Notify the site safety manager and record the intervention",
        ],
    },
    "no_gloves": {
        "title": "No gloves response protocol",
        "steps": [
            "Pause the task involving hand or material hazards",
            "Issue task-appropriate protective gloves",
            "Confirm the worker has fitted the gloves before restarting",
        ],
    },
    "no_boots": {
        "title": "Safety footwear violation response protocol",
        "steps": [
            "Remove the worker from the work zone immediately",
            "Issue GB 12011-compliant steel-toed safety footwear",
            "Examine the worker's feet for injuries before allowing return to work",
        ],
    },
    "no_goggle": {
        "title": "No goggles response protocol",
        "steps": [
            "Stop exposure to dust, particles, or splash hazards",
            "Issue appropriate eye protection for the task",
            "Check the fit and lens condition before work resumes",
        ],
    },
    "heat": {
        "title": "Heat stress emergency response protocol",
        "steps": [
            "Move the affected worker to a shaded, well-ventilated area immediately",
            "Provide cool potable water, at least 250 ml every 15 minutes",
            "Loosen or remove excess clothing and PPE to assist cooling",
            "Monitor vital signs and call first aid if the worker shows confusion or weakness",
            "Notify the site safety manager and record the daily heat exposure",
            "Enforce a 45-minute work and 15-minute rest cycle in the affected zone",
            "Review the heat management plan and reschedule heavy tasks if needed",
        ],
    },
}


def _init_state() -> None:
    for key, default in {
        "incident_status": {},
        "incident_notes": {},
        "incident_steps": {},
        "incident_times": {},
        "guidelines": {},
    }.items():
        st.session_state.setdefault(key, default)
    for key, guideline in BUILT_IN_GUIDELINES.items():
        st.session_state["guidelines"].setdefault(
            key, {"title": guideline["title"], "steps": list(guideline["steps"])}
        )


def _agent() -> LoggingAgent:
    return LoggingAgent(DATABASE_PATH)


def _brand_logo() -> Image.Image:
    with Image.open(LOGO_PATH) as logo:
        return logo.crop((250, 100, 1000, 850)).copy()


def _latest_record() -> LogRecord | None:
    records = _agent().recent(limit=1)
    return records[0] if records else None


def _reporting_sources(records: list[LogRecord]) -> set[str]:
    return {
        _assessment(record).source
        for record in records
        if _assessment(record).source in MONITORED_SOURCES
        if not (_assessment(record).source_detail or {}).get("synthetic")
    }


def _wbgt_high_risk_threshold() -> float:
    try:
        taxonomy = HEAT_TAXONOMY_PATH.read_text(encoding="utf-8")
    except OSError:
        return 30.0
    match = re.search(r"Risk Level: High Risk \(WBGT:\s*([0-9.]+)", taxonomy)
    return float(match.group(1)) if match else 30.0


def _ppe_compliance(records: list[LogRecord]) -> dict[str, dict[str, int | float]]:
    totals = {
        item: {"worn": 0, "missing": 0, "unaccounted": 0} for item in PPE_CORE_ITEMS
    }
    for record in records:
        assessment = _assessment(record)
        detail = assessment.source_detail or {}
        if assessment.source == "ppe":
            item = _ppe_item_key(assessment.label)
            if item in totals:
                totals[item][
                    "missing" if assessment.label.startswith("no_") else "worn"
                ] += 1
        elif assessment.source == "ppe_coverage":
            item = str(detail.get("item", assessment.label))
            if item in totals:
                totals[item]["unaccounted"] += 1
    for values in totals.values():
        denominator = values["worn"] + values["missing"] + values["unaccounted"]
        values["percentage"] = (
            round(100 * values["worn"] / denominator, 1) if denominator else 0.0
        )
    return totals


def _query_records(
    *,
    severity: str = "All severities",
    source: str = "All categories",
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[LogRecord]:
    agent = _agent()
    records = (
        agent.filter_by_date_range(start, end)
        if start is not None or end is not None
        else agent.recent(limit=200)
    )
    record_sets = [{record.record_id for record in records}]
    by_id = {record.record_id: record for record in records}
    if severity != "All severities":
        matches = agent.filter_by_severity(Severity[severity.upper()])
        record_sets.append({record.record_id for record in matches})
        by_id.update({record.record_id: record for record in matches})
    if source != "All categories":
        source_key = next(
            key for key, label in SOURCE_LABELS.items() if label == source
        )
        matches = agent.filter_by_source(source_key)
        record_sets.append({record.record_id for record in matches})
        by_id.update({record.record_id: record for record in matches})
    matching = set.intersection(*record_sets)
    return sorted(
        (
            by_id[record_id]
            for record_id in matching
            if not (_assessment(by_id[record_id]).source_detail or {}).get("synthetic")
        ),
        key=lambda record: record.recorded_at,
        reverse=True,
    )


def _assessment(record: LogRecord):
    return record.routed_alert.assessment


def _status(record: LogRecord) -> str:
    return st.session_state["incident_status"].get(record.record_id, "active")


def _relative_time(timestamp: datetime) -> str:
    delta = max(
        datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc), timedelta(0)
    )
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _format_response_time(record: LogRecord) -> str:
    resolved_at = (
        st.session_state["incident_times"].get(record.record_id, {}).get("resolved_at")
    )
    if resolved_at is None:
        return "—"
    elapsed = max(resolved_at - _assessment(record).assessed_at, timedelta(0))
    minutes = int(elapsed.total_seconds() // 60)
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"


def _ppe_item_text(label: str) -> str:
    """Human wording for a PPE detection class, without exposing the raw class token."""
    base = label[3:] if label.startswith("no_") else label
    return PPE_ITEM_LABELS.get(label, PPE_ITEM_LABELS.get(base, base.replace("_", " ")))


def _ppe_item_key(label: str) -> str:
    """Canonical PPE item key shared by positive/negative classes (no_goggle -> goggles)."""
    base = label[3:] if label.startswith("no_") else label
    return PPE_ITEM_KEYS.get(label, PPE_ITEM_KEYS.get(base, base))


def _reference_image(item_key: str) -> Path | None:
    """Locate a site-supplied reference photo of correct PPE for this item, if any.

    These are illustrative reference images only, never incident evidence: the logging schema
    does not persist the detection's source frame, so no stored record can point at one.
    """
    for suffix in REFERENCE_IMAGE_SUFFIXES:
        candidate = REFERENCE_IMAGE_DIR / f"{item_key}{suffix}"
        if candidate.exists():
            return candidate
    return None


@st.cache_data(show_spinner=False)
def _reference_manifest() -> dict[str, dict[str, Any]]:
    """Provenance for the generated reference images, keyed by PPE item.

    Written by `scripts/build_reference_ppe.py`; absent until that script has been run.
    """
    path = REFERENCE_IMAGE_DIR / "manifest.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return {
        entry["item"]: entry
        for entry in payload.get("references", [])
        if isinstance(entry, dict) and "item" in entry
    }


def _render_reference_image(
    item_key: str, label: str, *, width: int = REFERENCE_WIDTH
) -> None:
    """Render the reference image when one exists; stay silent when there is none.

    The label sits above the image as a single uppercase line rather than as an image caption:
    a wrapping caption underneath gave each image a different total height and broke alignment.
    Provenance (source frame and detection confidence) stays in `manifest.json`.
    """
    path = _reference_image(item_key)
    if path is None:
        return
    st.markdown(
        f'<div class="detail-label reference-label">{html.escape(label)}</div>',
        unsafe_allow_html=True,
    )
    if item_key == "gloves":
        with Image.open(path) as image:
            st.image(image.rotate(270, expand=True), width=width)
    else:
        st.image(str(path), width=width)


def _incident_name(record: LogRecord) -> str:
    assessment = _assessment(record)
    if assessment.source.startswith("heat"):
        # Heat alert titles come straight from the heat taxonomy (e.g. "Heat Caution").
        title = (assessment.source_detail or {}).get("title")
        return str(title) if title else "Heat stress"
    if assessment.source == "ppe_coverage":
        return f"{_ppe_item_text(assessment.label).capitalize()} not verified"
    if assessment.label.startswith("no_"):
        return f"Missing {_ppe_item_text(assessment.label)}"
    if assessment.label == "none":
        return "Unclassified detection"
    if assessment.requires_review:
        return f"{_ppe_item_text(assessment.label).capitalize()} — low confidence"
    return f"{_ppe_item_text(assessment.label).capitalize()} detected"


def _confidence(record: LogRecord) -> float | None:
    value = (_assessment(record).source_detail or {}).get("confidence")
    return float(value) if value is not None else None


def _severity_badge(severity: str) -> str:
    return f'<span class="badge sev-{severity.lower()}">{html.escape(severity)}</span>'


def _status_badge(status: str) -> str:
    return f'<span class="status-badge status-{status}">{STATUS_LABELS[status]}</span>'


def _render_metric_card(
    container: Any, label: str, value: str | int, caption: str
) -> None:
    """Value and its supporting line inside one bordered card — no delta pill."""
    card = container.container(border=True)
    card.metric(label, str(value))
    card.markdown(
        f'<div class="metric-caption">{html.escape(caption)}</div>',
        unsafe_allow_html=True,
    )


def _inject_css() -> None:
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    /* Every text token clears WCAG AA (>=4.5:1) on the white card, and every severity label
       clears it on its own tint. Ratios vs the card: ink 10.4, muted 6.0, faint 5.3. The page
       canvas sits a full step below the card (1.20:1) so containers read as raised surfaces,
       and border tokens are strong enough to bound a card without looking like a wireframe.
       Severity stays red/amber/blue for critical/moderate/minor; the tints carry the at-a-glance
       signal while the text label (never colour alone) carries identity. */
    :root { --navy:#102b3f; --ink:#334c5e; --muted:#5d7381; --faint:#718591; --line:#b9cbd0; --line-soft:#d8e4e2; --surface:#ffffff; --surface-tint:#f8fbfa; --page:#e8f0ee; --sidebar:#edf5f0; --blue:#2d647d; --blue-bg:#e5f1f5; --blue-line:#b5d2dc; --amber:#a56a14; --amber-bg:#fff3d9; --amber-line:#e7c887; --red:#a52e2b; --red-bg:#fff0ee; --red-line:#e4b5b1; --green:#338451; --green-bg:#e6f4e9; --green-line:#b9d9c0; --focus:#2d647d; --sidebar-text:#213d4b; --card-border:#1b2b35; --checklist-text:#214957; }
    .stApp { background:var(--page); color:var(--ink); font-family:'DM Sans',sans-serif; }
    [data-testid="stAppViewContainer"] > .main { background:linear-gradient(135deg,#e8f0ee 0%,#edf3f5 55%,#f6f3eb 100%); }
    .main .block-container { max-width:1440px; }
    .stApp p, .stApp label, .stApp .stMarkdown, .stApp [data-testid="stCaptionContainer"] { color:var(--ink); }
    [data-testid="stSidebar"] { background:var(--sidebar); border-right:1px solid var(--line); color:var(--sidebar-text); }
    [data-testid="stSidebar"] > div:first-child { padding-top:0!important; }
    [data-testid="stAppViewContainer"] .main .block-container,[data-testid="stMainBlockContainer"] { padding-top:1.5rem!important; }
     /* Streamlit renders st.navigation before user content regardless of call order. Reorder
         the sidebar regions so the brand and site selector lead the page links visually. */
    [data-testid="stSidebarContent"] { display:flex!important; flex-direction:column!important; }
     [data-testid="stSidebarUserContent"] { order:1!important; }
    [data-testid="stSidebarUserContent"] { padding-bottom:.35rem!important; margin-bottom:0!important; }
    [data-testid="stSidebarNav"] { order:2!important; margin-top:0!important; padding-top:0!important; }
    [data-testid="stSidebar"] * { color:var(--sidebar-text)!important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p, [data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] [data-testid="stSidebarNav"] a { color:var(--sidebar-text)!important; }
    [data-testid="stSidebarNav"] { display:block; } [data-testid="stSidebarNav"] ul { margin-top:0!important; padding-top:.25rem!important; } [data-testid="stSidebarNav"] a { color:var(--navy)!important; font-weight:600; border-radius:8px; } [data-testid="stSidebarNav"] a[aria-current="page"] { background:#ffffff!important; box-shadow:0 2px 5px rgba(27,55,65,.1); } [data-testid="stHeader"],[data-testid="stAppHeader"] { background:transparent; } [data-testid="stToolbar"] { visibility:hidden; }
    /* Keep the sidebar collapse/expand affordance permanently visible — Streamlit only reveals
       it on hover by default, which reads as a missing control on a wall-mounted display. */
    [data-testid="stSidebarCollapseButton"],[data-testid="stExpandSidebarButton"] { display:flex!important; visibility:visible!important; opacity:1!important; }
    [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] { top:.75rem!important; left:.75rem!important; }
    [data-testid="stSidebarCollapseButton"] button,[data-testid="stExpandSidebarButton"] button { width:2rem!important; height:2rem!important; padding:0!important; background:var(--surface)!important; border:1px solid var(--line)!important; border-radius:8px!important; color:var(--muted)!important; box-shadow:0 1px 2px rgba(16,27,45,.06)!important; } [data-testid="stSidebarCollapseButton"] button:hover,[data-testid="stExpandSidebarButton"] button:hover { color:var(--navy)!important; border-color:#8fa2b6!important; background:#f7fafc!important; }
    h1,h2,h3,h4,p,span,label,div { font-family:'DM Sans',sans-serif; } h1 { font-size:1.75rem!important; font-weight:600!important; letter-spacing:-.015em; color:var(--navy)!important; } h2 { font-size:1.05rem!important; font-weight:600!important; letter-spacing:-.005em; color:var(--navy)!important; } h3 { font-size:1rem!important; font-weight:600!important; color:var(--navy)!important; }
    /* Cards are real Streamlit containers (st.container(border=True)) so their border actually
       encloses their contents. Section heads and rows sit flush to the container's own padding. */
    [data-testid="stVerticalBlockBorderWrapper"] { background:var(--surface)!important; border:1.5px solid #263842!important; border-radius:10px; box-shadow:0 4px 12px rgba(27,55,65,.08); }
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { background:var(--surface)!important; border:1.5px solid #263842!important; border-radius:10px; box-shadow:0 4px 12px rgba(27,55,65,.08); }
    [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stMetric"]) { border-color:#000!important; }
    /* The metric card provides its own frame, so the inner metric widget carries none. */
    [data-testid="stMetric"] { background:transparent; border:0; padding:0; }
    [data-testid="stMetricLabel"] { color:var(--muted)!important; } [data-testid="stMetricLabel"] p { font-size:.72rem!important; font-weight:600!important; letter-spacing:.06em; text-transform:uppercase; color:var(--muted)!important; }
    [data-testid="stMetricValue"] { color:var(--navy)!important; font-size:2rem!important; font-weight:600!important; line-height:1.15!important; letter-spacing:-.02em; }
    [data-testid="stMetricDelta"] { display:none!important; }
    [data-testid="stMetric"]:after { content:""; position:absolute; right:-.8rem; bottom:-1.35rem; width:5rem; height:5rem; border:.8rem solid #e4f0e8; border-radius:50%; }
    .metric-caption { color:var(--faint); font-size:.75rem; margin-top:.3rem; line-height:1.4; }
    [data-testid="stMetric"] { position:relative; overflow:hidden; } [data-testid="stMetric"] > div { position:relative; z-index:1; }
    .brand-wordmark { color:var(--navy)!important; font-family:'DM Sans',sans-serif!important; font-size:1.1rem; font-weight:600; line-height:1.2; } .st-key-sidebar-brand,.st-key-mobile-brand { padding:0 0 .35rem; } .st-key-mobile-brand { display:none; } .st-key-sidebar-brand [data-testid="stHorizontalBlock"],.st-key-mobile-brand [data-testid="stHorizontalBlock"] { align-items:center!important; } .st-key-sidebar-brand [data-testid="stImage"] img,.st-key-mobile-brand [data-testid="stImage"] img { width:60px; height:60px; object-fit:cover; border-radius:0; border:0!important; background:transparent; }
    /* Active Site uses Streamlit's current React-Aria combobox markup, not BaseWeb select markup. */
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"] { background:var(--blue)!important; border:0!important; color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; caret-color:#ffffff!important; font-family:'DM Sans',sans-serif!important; }
    [data-testid="stSidebar"] div:has(> input[aria-label="Active site"][role="combobox"]) { background:var(--blue)!important; border:1px solid var(--blue)!important; box-shadow:none!important; }
    [data-testid="stSidebar"] div:has(input[aria-label="Active site"][role="combobox"]) button { background:#ffffff!important; border:1px solid var(--blue)!important; color:var(--navy)!important; }
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"]:focus,
    [data-testid="stSidebar"] input[aria-label="Active site"][role="combobox"]:focus-visible { outline:none!important; border:0!important; box-shadow:none!important; }
    [data-testid="stSidebar"] div:has(> input[aria-label="Active site"][role="combobox"]):focus-within { border-color:var(--blue)!important; outline:0!important; box-shadow:0 0 0 1px var(--blue)!important; }
    [data-testid="stSidebar"] [role="listbox"] [role="option"] { background:var(--navy)!important; color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; }
    [data-testid="stSidebar"] .sidebar-status { position:fixed; left:1.25rem; bottom:1.25rem; color:var(--muted)!important; font-family:'DM Sans',sans-serif!important; font-size:.78rem; line-height:1.8; }
    .eyebrow { color:var(--faint); font-size:.7rem; font-weight:600; letter-spacing:.09em; text-transform:uppercase; } .page-intro { color:var(--muted); font-size:.92rem; margin-top:-.5rem; margin-bottom:1.75rem; } .page-shell { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1.4rem; } .breadcrumb { color:var(--faint); font-family:'IBM Plex Mono',monospace; font-size:.72rem; } .breadcrumb strong { color:var(--navy); font-weight:600; } .live-status { display:flex; align-items:center; gap:.45rem; color:#2f7d4a; font-size:.76rem; font-weight:600; white-space:nowrap; } .live-dot { width:.45rem; height:.45rem; border-radius:50%; background:#3d9a5b; } .live-status.offline { color:var(--amber); } .live-status.offline .live-dot { background:#c7892f; }
    .section-gap { height:1.75rem; }
    .section-head { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.1rem 0 .85rem; border-bottom:1px solid var(--line-soft); margin-bottom:.35rem; } .section-head h2 { margin:0; } .section-head p { color:var(--faint); margin:.25rem 0 0; font-size:.8rem; }
    .count { background:var(--line-soft); color:var(--navy); padding:.2rem .55rem; border-radius:999px; font-family:'IBM Plex Mono',monospace; font-size:.76rem; }
    .badge,.status-badge { display:inline-block; border:1px solid; border-radius:4px; padding:.16rem .45rem; font-size:.7rem; font-weight:600; letter-spacing:.01em; white-space:nowrap; } .status-badge { border-radius:999px; }
    .sev-critical { color:var(--red); background:var(--red-bg); border-color:var(--red-line); } .sev-moderate { color:var(--amber); background:var(--amber-bg); border-color:var(--amber-line); } .sev-minor { color:var(--blue); background:var(--blue-bg); border-color:var(--blue-line); } .sev-none { color:var(--navy); background:var(--line-soft); border-color:var(--line); }
    .status-active { color:var(--red); background:var(--red-bg); border-color:var(--red-line); } .status-acknowledged { color:var(--amber); background:var(--amber-bg); border-color:var(--amber-line); } .status-resolved { color:var(--blue); background:var(--blue-bg); border-color:var(--blue-line); }
    .alert-row { margin:.55rem 0; padding:.85rem .9rem .7rem; background:var(--surface-tint); border:1.5px solid var(--card-border); border-radius:8px; box-shadow:0 4px 10px rgba(27,55,65,.08); } .alert-row:last-child { margin-bottom:.25rem; } .alert-row.critical { background:var(--red-bg); box-shadow:inset 4px 0 0 var(--red), 0 4px 10px rgba(165,46,43,.1); padding-left:1rem; } .alert-row.moderate { background:var(--amber-bg); box-shadow:inset 4px 0 0 var(--amber), 0 4px 10px rgba(165,106,20,.1); padding-left:1rem; } .alert-row.minor { background:var(--blue-bg); box-shadow:inset 4px 0 0 var(--blue), 0 4px 10px rgba(45,100,125,.1); padding-left:1rem; } .alert-title { display:flex; align-items:center; flex-wrap:wrap; gap:.5rem; font-size:.95rem; font-weight:600; color:var(--navy); } .alert-meta { color:var(--faint); font-size:.74rem; letter-spacing:.01em; margin:.4rem 0 .5rem; } .alert-row .muted { color:var(--ink); font-size:.86rem; line-height:1.5; }
    .compliance-label { display:flex; justify-content:space-between; gap:1rem; margin:.75rem 0 .15rem; color:var(--muted); font-size:.76rem; } .compliance-label strong { color:var(--navy); } .compliance-bar { height:.55rem; margin:.2rem 0 .15rem; overflow:hidden; display:flex; background:#cbd9d3; border-radius:999px; } .compliance-fill { height:100%; background:var(--green); } .compliance-legend { display:flex; justify-content:space-between; color:var(--faint); font-size:.66rem; }
    [class*="st-key-alert-actions-"] { margin-top:.7rem; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] details { border:0!important; border-radius:6px!important; box-shadow:none!important; background:transparent!important; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] summary { min-height:2.25rem; padding:.45rem .7rem!important; border:1px solid var(--line)!important; border-radius:6px!important; background:#f7fafc!important; } [class*="st-key-alert-actions-"] [data-testid="stExpander"] summary:hover { border-color:#8fa2b6!important; background:#eef3f7!important; } [class*="st-key-alert-actions-"] button { min-height:2.25rem!important; width:100%!important; }
    /* Labelled detail fields replace the previous raw JSON dump. */
    .detail-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(8.5rem,1fr)); gap:.6rem 1.25rem; padding:.7rem 0 .2rem; } .detail-grid .detail-value { font-size:.84rem; } .detail-label { color:var(--faint); font-size:.68rem; font-weight:600; letter-spacing:.07em; text-transform:uppercase; } .detail-value { color:var(--ink); font-size:.88rem; margin-top:.15rem; line-height:1.45; } .detail-note { color:var(--faint); font-size:.75rem; font-style:italic; margin-top:.5rem; } .detail-ref { color:var(--faint); font-family:'IBM Plex Mono',monospace; font-size:.7rem; margin-top:.85rem; }
    /* Reference images: fixed width + square crops => identical heights, so they line up.
       Captions are suppressed outright; the label sits above the image instead. */
    .reference-label { margin:.9rem 0 .35rem; }
    [data-testid="stImage"] { margin:0; } [data-testid="stImage"] img { border-radius:8px; border:1px solid var(--line-soft); display:block; }
    [data-testid="stImageCaption"], [data-testid="stImage"] figcaption { display:none!important; }
    .muted { color:var(--muted); } .empty { text-align:center; padding:2.75rem 1.25rem; color:var(--ink); font-size:.88rem; } .chart-empty { min-height:10rem; display:flex; align-items:center; justify-content:center; box-sizing:border-box; background:#f5f8f7; border-radius:7px; } .mono { font-family:'IBM Plex Mono',monospace; font-size:.84rem; color:var(--ink); } .mobile-brand { display:none; } .sidebar-workspace { color:var(--faint)!important; font-size:.68rem; font-weight:600; letter-spacing:.1em; text-transform:uppercase; margin:.55rem 0 .2rem; } .sidebar-status { border-top:1px solid var(--line-soft); padding-top:.75rem; }
    button { border-radius:6px!important; background:#fff!important; color:var(--ink)!important; border:1px solid var(--line)!important; font-weight:500!important; } button p { color:inherit!important; font-size:.84rem!important; } button:hover:not(:disabled) { border-color:#8fa2b6!important; background:#f7fafc!important; color:var(--navy)!important; }
    button[kind="primary"] { background:var(--navy)!important; color:#fff!important; border-color:var(--navy)!important; } button[kind="primary"]:hover { background:#1c2c44!important; } button[kind="primary"] p { color:#fff!important; }
    button:disabled, button[disabled] { background:var(--page)!important; color:var(--muted)!important; border-color:var(--line)!important; box-shadow:none!important; cursor:not-allowed!important; }
    /* Keyboard usability: Streamlit ships no visible focus ring on these controls. */
    button:focus-visible, summary:focus-visible, input:focus-visible, select:focus-visible, [role="checkbox"]:focus-visible, textarea:focus-visible { outline:2px solid var(--focus)!important; outline-offset:2px!important; }
    /* Form controls need a border strong enough to find on a bright site display. */
    [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] { border-color:var(--line)!important; background:var(--surface)!important; } [data-baseweb="select"] > div:hover, [data-baseweb="input"]:hover { border-color:#8fa2b6!important; }
    [data-testid="stWidgetLabel"] p { color:var(--muted)!important; font-size:.76rem!important; font-weight:600!important; }
    [data-testid="stExpander"] details { border:1.5px solid var(--card-border)!important; border-radius:8px!important; background:var(--surface)!important; box-shadow:0 1px 3px rgba(16,27,45,.08); }
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary * { font-size:.88rem!important; color:var(--navy)!important; -webkit-text-fill-color:var(--navy)!important; }
    [data-testid="stExpander"] details[open] > summary, [data-testid="stExpander"] details[open] > summary * { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; background:#101b2d!important; }
    [data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:hover * { color:#ffffff!important; -webkit-text-fill-color:#ffffff!important; background:#101b2d!important; }
    [data-testid="stExpander"] [data-testid="stMarkdownContainer"], [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p, [data-testid="stExpander"] .detail-value, [data-testid="stExpander"] .mono { color:var(--ink)!important; }
    [data-testid="stExpander"] .detail-label, [data-testid="stExpander"] .detail-note, [data-testid="stExpander"] .detail-ref { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] p, [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stMarkdownContainer"] li { color:var(--ink); }
    [data-testid="stVerticalBlockBorderWrapper"] .section-head p, [data-testid="stVerticalBlockBorderWrapper"] .metric-caption { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .detail-label { color:var(--faint)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .detail-value { color:var(--ink)!important; }
    [data-testid="stVerticalBlockBorderWrapper"] .badge, [data-testid="stVerticalBlockBorderWrapper"] .status-badge { color:inherit; }
    [data-testid="stCheckbox"] label { color:var(--checklist-text)!important; font-weight:600; }
    [data-testid="stCheckbox"] span { color:var(--checklist-text)!important; }
    [data-testid="stCheckbox"] .stCheckbox { border-left:2px solid var(--blue-line); padding-left:.35rem; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] p { color:var(--muted)!important; }
    .response-note { margin-top:.8rem; padding:.7rem .8rem; border-left:2px solid #4a9a61; background:#f1f7f2; color:var(--ink); line-height:1.45; } .response-empty { margin-top:.8rem; padding:1rem .75rem; background:#f7fafc; }
    .protocol-icon { display:inline-grid; place-items:center; width:2rem; height:2rem; margin-right:.55rem; border-radius:7px; background:var(--green-bg); color:var(--green); font-family:'IBM Plex Mono',monospace; font-size:.75rem; font-weight:600; vertical-align:middle; } .protocol-description { color:var(--muted); font-size:.8rem; margin:.3rem 0 .8rem 2.55rem; } .protocol-footer { display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--line-soft); margin-top:.8rem; padding-top:.65rem; }
    .library-banner { margin-top:1rem; padding:.75rem; background:#f5f0e3; color:#7a5410; font-size:.76rem; line-height:1.45; border-radius:6px; } .library-legend { margin-top:.8rem; color:var(--muted); font-size:.76rem; line-height:2; } .legend-dot { display:inline-block; width:.45rem; height:.45rem; margin-right:.35rem; border-radius:50%; } .legend-critical { background:var(--red); } .legend-moderate { background:#c7892f; } .legend-recorded { background:#3d9a5b; }
     /* The pinned base theme is light, so the dialog must explicitly provide its own light
         surface and dark form text instead of relying on Streamlit's overlay defaults. */
     [data-testid="stDialog"] [role="dialog"] { background:var(--surface)!important; color:var(--ink)!important; border:1.5px solid var(--card-border)!important; box-shadow:0 18px 45px rgba(16,43,63,.2)!important; }
     [data-testid="stDialog"] [role="dialog"] * { color:var(--ink)!important; }
     [data-testid="stDialog"] [role="dialog"] h1, [data-testid="stDialog"] [role="dialog"] h2, [data-testid="stDialog"] [role="dialog"] h3, [data-testid="stDialog"] [role="dialog"] h4, [data-testid="stDialog"] [role="dialog"] .dialog-incident-title { color:var(--navy)!important; }
     [data-testid="stDialog"] [role="dialog"] .dialog-incident-title { font-weight:700; letter-spacing:-.01em; }
     [data-testid="stDialog"] [role="dialog"] .dialog-incident-meta { color:var(--muted)!important; font-size:.86rem; }
     [data-testid="stDialog"] [role="dialog"] [data-testid="stCaptionContainer"] p, [data-testid="stDialog"] [role="dialog"] [data-testid="stCheckbox"] label, [data-testid="stDialog"] [role="dialog"] [data-testid="stCheckbox"] span { color:var(--ink)!important; }
     [data-testid="stDialog"] [role="dialog"] [data-testid="stWidgetLabel"] p { color:var(--muted)!important; }
     [data-testid="stDialog"] [role="dialog"] input[type="checkbox"] { accent-color:var(--green); }
     [data-testid="stDialog"] [role="dialog"] textarea { color:var(--ink)!important; background:var(--surface)!important; border:1.5px solid var(--line)!important; }
     [data-testid="stDialog"] [role="dialog"] textarea::placeholder { color:var(--faint)!important; opacity:1!important; }
     [data-testid="stDialog"] [role="dialog"] button { color:var(--ink)!important; border-color:var(--line)!important; background:var(--surface)!important; }
     [data-testid="stDialog"] [role="dialog"] button[kind="primary"] { color:#ffffff!important; background:var(--blue)!important; border-color:var(--blue)!important; }
     [data-testid="stDialog"] [role="dialog"] button[kind="primary"] p, [data-testid="stDialog"] [role="dialog"] button p { color:inherit!important; }
    @media (max-width:800px) { .st-key-mobile-brand { display:block; } .page-intro { margin-bottom:1rem; } .section-gap { height:1rem; } }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _sidebar() -> None:
    with st.sidebar:
        with st.container(key="sidebar-brand"):
            logo_column, wordmark_column = st.columns([1, 4], gap="small")
            with logo_column:
                st.image(_brand_logo(), width=60)
            with wordmark_column:
                st.markdown(
                    '<div class="brand-wordmark">Site Sense</div>',
                    unsafe_allow_html=True,
                )
        st.markdown('<div class="eyebrow">Active site</div>', unsafe_allow_html=True)
        st.selectbox(
            "Active site",
            ["Shenzhen", "Guangzhou", "Shanghai"],
            label_visibility="collapsed",
            key="active_site",
        )
        st.markdown(
            '<div class="sidebar-workspace">Workspace</div>', unsafe_allow_html=True
        )
        logging_agent = _agent()
        sources = {
            source
            for source in MONITORED_SOURCES
            if _reporting_sources(logging_agent.filter_by_source(source))
        }
        latest_records = logging_agent.recent(limit=1)
        latest = latest_records[0] if latest_records else None
        last_sync = (
            latest.recorded_at.astimezone().strftime("%Y-%m-%d %H:%M")
            if latest is not None
            else "No records yet"
        )
        st.markdown(
            f'<div class="sidebar-status"><div><strong>Monitoring active</strong></div><div>{len(sources)} data sources reporting</div><div class="mono">Last sync: {html.escape(last_sync)}</div></div>',
            unsafe_allow_html=True,
        )


def _page_header(title: str, description: str) -> None:
    with st.container(key="mobile-brand"):
        logo_column, wordmark_column = st.columns([1, 4], gap="small")
        with logo_column:
            st.image(_brand_logo(), width=60)
        with wordmark_column:
            st.markdown(
                '<div class="brand-wordmark">Site Sense</div>', unsafe_allow_html=True
            )
    latest = _latest_record()
    status_text = "Live monitoring" if latest is not None else "Awaiting telemetry"
    status_class = "" if latest is not None else " offline"
    site = html.escape(str(st.session_state.get("active_site", "Unknown site")))
    st.markdown(
        f'<div class="page-shell"><div class="breadcrumb">{site} / <strong>{html.escape(title)}</strong></div><div class="live-status{status_class}"><span class="live-dot"></span>{status_text}</div></div>',
        unsafe_allow_html=True,
    )
    st.title(title)
    st.markdown(
        f'<p class="page-intro">{html.escape(description)}</p>', unsafe_allow_html=True
    )


def _reading_time(record: LogRecord) -> datetime:
    """When the measurement was taken, falling back to when it was recorded."""
    raw = (_assessment(record).source_detail or {}).get("reading_at")
    if raw is not None:
        try:
            return datetime.fromisoformat(str(raw))
        except TypeError, ValueError:
            pass
    return record.recorded_at


def _render_heat_chart(records: list[LogRecord]) -> None:
    points = []
    for record in records:
        detail = _assessment(record).source_detail or {}
        value = detail.get("wbgt_c", detail.get("air_temperature_c"))
        if value is not None:
            # Plot the time the reading was taken, not the time the row was written. Records
            # ingested in one batch share a write timestamp, which collapsed the x-axis to a
            # sub-second span while the axis still claimed to cover hours.
            points.append({"time": _reading_time(record), "temperature": float(value)})
    # A real container is required: Streamlit renders each widget as a DOM sibling, so an
    # unclosed `<div>` from st.markdown never encloses what follows it.
    card = st.container(border=True)
    # Copy names the series as a proxy reading: this pipeline has no live thermal hardware.
    card.markdown(
        '<div class="section-head"><div><h2>Heat exposure trend</h2><p>Proxy heat readings, plotted by reading time</p></div></div>',
        unsafe_allow_html=True,
    )
    if not points:
        card.markdown(
            '<div class="empty chart-empty">No heat telemetry is available for this period.</div>',
            unsafe_allow_html=True,
        )
    else:
        frame = pd.DataFrame(points).sort_values("time")
        figure = go.Figure(
            go.Scatter(
                x=frame["time"],
                y=frame["temperature"],
                mode="lines+markers",
                name="Proxy heat reading",
                line={"color": "#a56a14", "width": 2.5},
                marker={
                    "color": "#a56a14",
                    "size": 8,
                    "line": {"color": "#fff3d9", "width": 2},
                },
                fill="tozeroy",
                fillcolor="rgba(229, 200, 135, .28)",
            )
        )
        threshold = _wbgt_high_risk_threshold()
        figure.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="#a52e2b",
            annotation_text=f"High-risk threshold {threshold:.1f}°C",
            annotation_position="top left",
        )
        figure.update_layout(
            height=330,
            margin={"l": 10, "r": 20, "t": 20, "b": 10},
            paper_bgcolor="white",
            plot_bgcolor="white",
            font={"family": "DM Sans", "color": "#566575", "size": 12},
            xaxis={
                "showgrid": False,
                "linecolor": "#35515d",
                "linewidth": 2,
                "tickfont": {"color": "#35515d", "size": 12},
            },
            yaxis={
                "title": {"text": "°C", "font": {"color": "#35515d", "size": 13}},
                "gridcolor": "#b7c9c7",
                "linecolor": "#35515d",
                "linewidth": 2,
                "tickfont": {"color": "#35515d", "size": 12},
                "range": [0, max(40, float(frame["temperature"].max()) + 5)],
            },
            hovermode="x unified",
        )
        card.plotly_chart(
            figure, use_container_width=True, config={"displayModeBar": False}
        )


def _render_ppe_compliance(records: list[LogRecord]) -> None:
    card = st.container(border=True)
    card.markdown(
        '<div class="section-head"><div><h2>PPE compliance</h2><p>Confirmed worn against missing and unaccounted assessments</p></div></div>',
        unsafe_allow_html=True,
    )
    totals = _ppe_compliance(records)
    for item, values in totals.items():
        label = _ppe_item_text(item).capitalize()
        percentage = float(values["percentage"])
        card.markdown(
            f'<div class="compliance-label"><span>{html.escape(label)}</span><strong>{percentage:.1f}%</strong></div>',
            unsafe_allow_html=True,
        )
        card.markdown(
            f'<div class="compliance-bar" role="img" aria-label="{html.escape(label)}: {percentage:.1f}% confirmed worn, {100 - percentage:.1f}% not confirmed"><div class="compliance-fill" style="width:{percentage:.1f}%"></div></div><div class="compliance-legend"><span>Confirmed worn</span><span>Not confirmed</span></div>',
            unsafe_allow_html=True,
        )
    if not any(
        sum(values[key] for key in ("worn", "missing", "unaccounted"))
        for values in totals.values()
    ):
        card.markdown(
            '<div class="detail-note">No core PPE assessments are currently logged.</div>',
            unsafe_allow_html=True,
        )


@st.dialog("Incident response")
def _resolution_dialog(record_id: str, action: str) -> None:
    record = next(
        (item for item in _query_records() if item.record_id == record_id), None
    )
    if record is None:
        st.error("This incident is no longer available.")
        return
    assessment = _assessment(record)
    st.markdown(
        f'<h3 class="dialog-incident-title">{html.escape(_incident_name(record))}</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="dialog-incident-meta">{html.escape(assessment.zone or "Unassigned zone")} · {html.escape(_relative_time(assessment.assessed_at))} · {html.escape(assessment.severity.name.title())}</p>',
        unsafe_allow_html=True,
    )
    # Show the target state before the responder works the checklist.
    if assessment.source.startswith("ppe"):
        _render_reference_image(
            _ppe_item_key(assessment.label),
            f"Correct {_ppe_item_text(assessment.label)}",
        )
    guideline = st.session_state["guidelines"].get(
        "heat" if assessment.source.startswith("heat") else assessment.label
    )
    selected: list[int] = []
    if guideline:
        st.markdown(f"**{guideline['title']}**")
        for index, step in enumerate(guideline["steps"], start=1):
            if st.checkbox(f"{index}. {step}", key=f"dialog-{record_id}-{index}"):
                selected.append(index)
    else:
        st.info(
            "No guideline is configured. Add resolution notes to record the response."
        )
    notes = st.text_area(
        "Resolution notes",
        value=st.session_state["incident_notes"].get(record_id, ""),
        placeholder="Describe the corrective action taken...",
    )
    cancel, submit = st.columns(2)
    if cancel.button("Cancel", use_container_width=True):
        st.rerun()
    if submit.button(
        "Mark resolved" if action == "resolve" else "Mark acknowledged",
        type="primary",
        use_container_width=True,
    ):
        now = datetime.now(timezone.utc)
        st.session_state["incident_status"][record_id] = (
            "resolved" if action == "resolve" else "acknowledged"
        )
        st.session_state["incident_notes"][record_id] = notes
        st.session_state["incident_steps"][record_id] = selected
        times = st.session_state["incident_times"].setdefault(record_id, {})
        times.setdefault("acknowledged_at", now)
        if action == "resolve":
            times["resolved_at"] = now
        st.rerun()


def _alert_actions(record: LogRecord, key_prefix: str) -> None:
    status = _status(record)
    if status == "active" and st.button(
        "Acknowledge", key=f"ack-{key_prefix}-{record.record_id}"
    ):
        _resolution_dialog(record.record_id, "acknowledge")
    elif status == "acknowledged" and st.button(
        "Resolve", key=f"resolve-{key_prefix}-{record.record_id}"
    ):
        _resolution_dialog(record.record_id, "resolve")


def _description_block(record: LogRecord) -> str:
    """Description markup, omitted when it merely repeats the incident name.

    Heat assessments use the alert title as their description, so rendering both printed the
    same sentence twice in every heat row.
    """
    description = _readable_description(record)
    if description.strip().lower() == _incident_name(record).strip().lower():
        return ""
    return f'<div class="muted">{html.escape(description)}</div>'


def _alert_card(record: LogRecord, key_prefix: str) -> None:
    assessment = _assessment(record)
    confidence = _confidence(record)
    confidence_text = (
        f"{confidence:.0%} confidence"
        if confidence is not None
        else "Confidence unavailable"
    )
    st.markdown(
        f'<div class="alert-row {assessment.severity.name.lower()}"><div class="alert-title">{_severity_badge(assessment.severity.name.title())} {html.escape(_incident_name(record))} {(_status_badge(_status(record)) if _status(record) != "active" else "")}</div><div class="alert-meta">{html.escape(assessment.zone or "Unassigned zone")} · {SOURCE_LABELS.get(assessment.source, assessment.source)} · {confidence_text} · {_relative_time(record.recorded_at)}</div>{_description_block(record)}</div>',
        unsafe_allow_html=True,
    )
    with st.container(key=f"alert-actions-{key_prefix}-{record.record_id}"):
        details, response = st.columns([1.35, 1], gap="small")
        with details:
            with st.expander("View details"):
                with st.container(height=ALERT_DETAIL_HEIGHT, border=False):
                    _incident_details(record)
        with response:
            _alert_actions(record, key_prefix)


def _is_ppe_violation(record: LogRecord) -> bool:
    assessment = _assessment(record)
    return assessment.source == "ppe" and assessment.label.startswith("no_")


def _alert_rank(record: LogRecord) -> tuple[int, float]:
    """Most severe first, then most recent."""
    return (-_assessment(record).severity.value, -record.recorded_at.timestamp())


def _visible_alerts(records: list[LogRecord]) -> tuple[list[LogRecord], int]:
    """Pick the alerts to surface on the overview, and the total actionable count.

    Only missing-PPE violations and heat alerts are actionable here; positive detections and
    unverified-coverage flags stay in the incident log. PPE keeps a reserved share of the
    visible slots so a long run of heat readings cannot bury a missing-PPE violation.
    """
    violations = sorted((r for r in records if _is_ppe_violation(r)), key=_alert_rank)
    heat = sorted(
        (r for r in records if _assessment(r).source.startswith("heat")),
        key=_alert_rank,
    )
    shown = violations[:PPE_ALERT_SLOTS]
    shown += heat[: max(VISIBLE_ALERT_LIMIT - len(shown), 0)]
    return sorted(shown, key=_alert_rank), len(violations) + len(heat)


def render_dashboard() -> None:
    _page_header(
        "Safety overview", "A clear read on conditions that need your attention."
    )
    records = _query_records()
    today = _today_records()
    active = [record for record in records if _status(record) != "resolved"]
    ppe_records = [
        record for record in records if _assessment(record).source.startswith("ppe")
    ]
    heat_records = [
        record for record in records if _assessment(record).source.startswith("heat")
    ]
    ppe_positive = sum(
        1 for record in ppe_records if not _assessment(record).label.startswith("no_")
    )
    compliance = round(100 * ppe_positive / len(ppe_records)) if ppe_records else 0
    st.markdown('<div class="eyebrow">Site status</div>', unsafe_allow_html=True)
    metrics = st.columns(4)
    _render_metric_card(metrics[0], "Active alerts", len(active), "Require attention")
    _render_metric_card(
        metrics[1],
        "PPE compliance",
        f"{compliance}%",
        f"Across {len(ppe_records)} recorded PPE events",
    )
    _render_metric_card(
        metrics[2],
        "Heat risk exposure",
        len([r for r in heat_records if _assessment(r).severity is not Severity.NONE]),
        "Readings above the safe threshold",
    )
    _render_metric_card(
        metrics[3], "Incidents today", len(today), "Events logged today"
    )
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    visible, actionable_total = _visible_alerts(active)
    left, right = st.columns([1.05, 0.95])
    with left:
        with st.container(border=True):
            st.markdown(
                f'<div class="section-head"><div><h2>Recent alerts</h2><p>PPE violations and heat alerts awaiting action</p></div><span class="count">{actionable_total}</span></div>',
                unsafe_allow_html=True,
            )
            if visible:
                for record in visible:
                    _alert_card(record, "dashboard")
            else:
                st.markdown(
                    '<div class="empty">All monitored zones are clear.</div>',
                    unsafe_allow_html=True,
                )
    with right:
        now = datetime.now(timezone.utc)
        _render_ppe_compliance(records)
        _render_heat_chart(_query_records(start=now - timedelta(hours=6), end=now))


def _observed_item_text(label: str) -> str:
    if label == "person":
        return "Worker"
    if label == "none":
        return "Unclassified object"
    if label.startswith("no_"):
        return f"Missing {_ppe_item_text(label)}"
    return _ppe_item_text(label).capitalize()


def _format_timestamp(value: Any, *, date_only: bool = False) -> str:
    pattern = "%b %d, %Y" if date_only else "%b %d, %Y %H:%M"
    if isinstance(value, datetime):
        return value.strftime(pattern)
    try:
        return datetime.fromisoformat(str(value)).strftime(pattern)
    except TypeError, ValueError:
        return str(value)


def _threshold_band(detail: dict[str, Any]) -> str | None:
    minimum, maximum = detail.get("threshold_min_c"), detail.get("threshold_max_c")
    if minimum is None:
        return None
    return (
        f"{float(minimum):.0f}–{float(maximum):.0f} °C"
        if maximum is not None
        else f"Above {float(minimum):.0f} °C"
    )


def _detail_rows(record: LogRecord) -> list[tuple[str, str]]:
    """Labelled, human-readable fields for one incident, per detection source."""
    assessment = _assessment(record)
    detail = assessment.source_detail or {}
    rows: list[tuple[str, str]] = []

    if assessment.source == "ppe":
        rows.append(("Detected item", _observed_item_text(assessment.label)))
        box = detail.get("bounding_box") or {}
        if all(key in box for key in ("x_min", "y_min", "x_max", "y_max")):
            width, height = float(box["x_max"]) - float(box["x_min"]), float(
                box["y_max"]
            ) - float(box["y_min"])
            rows.append(
                (
                    "Image region",
                    f"{width:.0f} × {height:.0f} px at x {float(box['x_min']):.0f}, y {float(box['y_min']):.0f}",
                )
            )
    elif assessment.source == "ppe_coverage":
        rows.append(("PPE item", _ppe_item_text(assessment.label).capitalize()))
        rows.append(
            (
                "Coverage status",
                str(detail.get("coverage_status", "unaccounted"))
                .replace("_", " ")
                .capitalize(),
            )
        )
        observed = [
            label for label in detail.get("observed_labels") or [] if label != "none"
        ]
        if observed:
            rows.append(
                (
                    "Also seen in frame",
                    ", ".join(_observed_item_text(label) for label in observed),
                )
            )
    elif assessment.source == "heat_wbgt":
        rows.append(("Site", str(detail.get("city", "Unspecified"))))
        rows.append(
            (
                "Reading taken",
                _format_timestamp(detail.get("reading_at", assessment.assessed_at)),
            )
        )
        if detail.get("wbgt_c") is not None:
            rows.append(("WBGT reading", f"{float(detail['wbgt_c']):.1f} °C"))
        if detail.get("air_temperature_c") is not None:
            rows.append(
                ("Air temperature", f"{float(detail['air_temperature_c']):.1f} °C")
            )
        rows.append(("Risk level", str(detail.get("level", assessment.label))))
    elif assessment.source == "heat_compliance":
        rows.append(("Site", str(detail.get("city", "Unspecified"))))
        rows.append(
            (
                "Forecast date",
                _format_timestamp(
                    detail.get("forecast_date", assessment.assessed_at), date_only=True
                ),
            )
        )
        if detail.get("forecast_max_temperature_c") is not None:
            rows.append(
                (
                    "Forecast maximum",
                    f"{float(detail['forecast_max_temperature_c']):.1f} °C",
                )
            )
        rows.append(("Alert level", str(detail.get("level", assessment.label))))

    band = _threshold_band(detail)
    if band:
        rows.append(("Threshold band", band))
    return rows


def _detail_note(record: LogRecord) -> str | None:
    """Surface the heat-proxy limitation and low-confidence reviews honestly."""
    assessment = _assessment(record)
    metadata = (assessment.source_detail or {}).get("metadata") or {}
    if assessment.source == "heat_wbgt" and metadata.get("simulation_mode"):
        return "Simulated WBGT proxy reading — not live thermal camera data."
    if assessment.source.startswith("heat"):
        return "Derived from weather/WBGT proxy data, not live thermal hardware."
    if assessment.requires_review:
        return "Below the confidence threshold — downgraded and flagged for supervisor review."
    return None


def _render_detail_grid(rows: list[tuple[str, str]]) -> None:
    cells = "".join(
        f'<div><div class="detail-label">{html.escape(label)}</div><div class="detail-value">{html.escape(value)}</div></div>'
        for label, value in rows
    )
    st.markdown(f'<div class="detail-grid">{cells}</div>', unsafe_allow_html=True)


def _readable_description(record: LogRecord) -> str:
    """Swap the raw PPE class token in agent-authored text for its human wording."""
    assessment = _assessment(record)
    if not assessment.source.startswith("ppe"):
        return assessment.description
    label = assessment.label
    phrase = (
        f"missing {_ppe_item_text(label)}"
        if label.startswith("no_")
        else _ppe_item_text(label)
    )
    return assessment.description.replace(label, phrase)


def _incident_details(record: LogRecord) -> None:
    assessment = _assessment(record)
    confidence = _confidence(record)
    rows = [
        ("Event type", _incident_name(record)),
        ("Category", SOURCE_LABELS.get(assessment.source, assessment.source)),
        ("Zone", assessment.zone or "Unassigned"),
        ("Detected", _relative_time(assessment.assessed_at)),
        ("Response time", _format_response_time(record)),
        *_detail_rows(record),
    ]
    _render_detail_grid(rows)
    if confidence is not None:
        st.progress(confidence, text=f"Detection confidence {confidence:.0%}")
    st.markdown(
        f'<div class="detail-label">Assessment</div><div class="detail-value">{html.escape(_readable_description(record))}</div>',
        unsafe_allow_html=True,
    )
    if assessment.recommended_actions:
        actions = "".join(
            f"<li>{html.escape(action)}</li>"
            for action in assessment.recommended_actions
        )
        st.markdown(
            f'<div class="detail-label" style="margin-top:.85rem">Recommended actions</div><ul class="detail-value" style="margin:.2rem 0 0;padding-left:1.1rem">{actions}</ul>',
            unsafe_allow_html=True,
        )
    if assessment.source.startswith("ppe"):
        item = _ppe_item_text(assessment.label)
        _render_reference_image(_ppe_item_key(assessment.label), f"Correct {item}")
    notes = st.session_state["incident_notes"].get(record.record_id)
    if notes:
        st.markdown(
            f'<div class="detail-label" style="margin-top:.85rem">Resolution notes</div><div class="detail-value">{html.escape(notes)}</div>',
            unsafe_allow_html=True,
        )
    note = _detail_note(record)
    if note:
        st.markdown(
            f'<div class="detail-note">{html.escape(note)}</div>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div class="detail-ref">Record reference {html.escape(record.record_id)}</div>',
        unsafe_allow_html=True,
    )


def _incident_evidence(record: LogRecord) -> None:
    st.markdown('<div class="eyebrow">Detection evidence</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="detail-value"><strong>{html.escape(_incident_name(record))}</strong><br>{html.escape(_readable_description(record))}</div>',
        unsafe_allow_html=True,
    )
    _render_detail_grid(_detail_rows(record))
    if (confidence := _confidence(record)) is not None:
        st.progress(confidence, text=f"Detection confidence {confidence:.0%}")


def _incident_response(record: LogRecord) -> None:
    notes = st.session_state["incident_notes"].get(record.record_id)
    st.markdown('<div class="eyebrow">Response record</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="detail-value"><strong>{html.escape(STATUS_LABELS[_status(record)])}</strong><br>Response time: {html.escape(_format_response_time(record))}</div>',
        unsafe_allow_html=True,
    )
    if notes:
        st.markdown(
            f'<div class="response-note">{html.escape(notes)}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="empty response-empty">No response notes have been entered.</div>',
            unsafe_allow_html=True,
        )
    _alert_actions(record, "log")


def render_incident_log() -> None:
    _page_header(
        "Incident log", "A comprehensive history of safety events and actions taken."
    )
    controls = st.columns([1.7, 1, 1, 1])
    search = controls[0].text_input(
        "Search", placeholder="Search by zone, item, or incident ID"
    )
    severity = controls[1].selectbox(
        "Severity", ["All severities", "Critical", "Moderate", "Minor"]
    )
    category = controls[2].selectbox(
        "Category", ["All categories", *SOURCE_LABELS.values()]
    )
    status = controls[3].selectbox("Status", ["All statuses", *STATUS_LABELS.values()])
    records = _query_records(severity=severity, source=category)
    if search:
        needle = search.lower()
        records = [
            record
            for record in records
            if needle
            in " ".join(
                [
                    record.record_id,
                    _assessment(record).label,
                    _assessment(record).zone or "",
                ]
            ).lower()
        ]
    if status != "All statuses":
        selected = next(key for key, value in STATUS_LABELS.items() if value == status)
        records = [record for record in records if _status(record) == selected]
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    events = st.container(border=True)
    events.markdown(
        '<div class="section-head"><div><h2>Safety events</h2><p>Expand a row to inspect evidence and response data.</p></div><span class="count">{}</span></div>'.format(
            len(records)
        ),
        unsafe_allow_html=True,
    )
    if not records:
        events.markdown(
            '<div class="empty">No incidents match the selected filters.</div>',
            unsafe_allow_html=True,
        )
    for record in records:
        assessment = _assessment(record)
        with events.expander(
            f"{_incident_name(record)} · {SOURCE_LABELS.get(assessment.source, assessment.source)} · {assessment.zone or 'Unassigned zone'} · {_status(record).title()}"
        ):
            columns = st.columns([1.3, 1.1, 1, 1])
            columns[0].markdown(
                f"<div class='detail-label'>Timestamp</div><span class='mono'>{record.recorded_at.strftime('%b %d, %Y %H:%M')}</span>",
                unsafe_allow_html=True,
            )
            columns[1].markdown(
                f"<div class='detail-label'>Severity</div>{_severity_badge(assessment.severity.name.title())}",
                unsafe_allow_html=True,
            )
            columns[2].markdown(
                f"<div class='detail-label'>Status</div>{_status_badge(_status(record))}",
                unsafe_allow_html=True,
            )
            columns[3].markdown(
                f"<div class='detail-label'>Response time</div><span class='mono'>{_format_response_time(record)}</span>",
                unsafe_allow_html=True,
            )
            evidence, response = st.columns([1.2, 1])
            with evidence:
                _incident_evidence(record)
            with response:
                _incident_response(record)


def _render_guideline_card(key: str, built_in: dict[str, Any]) -> None:
    current = st.session_state["guidelines"][key]
    with st.container(border=True):
        top = st.columns([3, 1, 1])
        scope = "Heat stress" if key == "heat" else f"Missing {_ppe_item_text(key)}"
        icon = "H" if key == "heat" else _ppe_item_text(key)[:1].upper()
        top[0].markdown(
            f'<span class="protocol-icon">{icon}</span><strong>{html.escape(current["title"])}</strong><div class="protocol-description">Response steps for {html.escape(scope.lower())}.</div>',
            unsafe_allow_html=True,
        )
        severity_class = (
            "sev-critical"
            if key in {"heat", "no_helmet", "no_boots"}
            else "sev-moderate"
        )
        severity_text = (
            "Critical protocol"
            if severity_class == "sev-critical"
            else "Moderate protocol"
        )
        top[1].markdown(
            f'<span class="badge {severity_class}">{severity_text}</span>',
            unsafe_allow_html=True,
        )
        editing = f"editing-{key}"
        if top[2].button("Edit", key=f"edit-{key}"):
            st.session_state[editing] = True
        if st.session_state.get(editing):
            title = st.text_input(
                "Protocol title", value=current["title"], key=f"title-{key}"
            )
            edited = st.data_editor(
                pd.DataFrame({"Step": current["steps"]}),
                num_rows="dynamic",
                hide_index=True,
                key=f"editor-{key}",
                use_container_width=True,
            )
            save, cancel, reset = st.columns(3)
            if save.button("Save changes", key=f"save-{key}", type="primary"):
                steps = [
                    str(step).strip()
                    for step in edited["Step"].tolist()
                    if str(step).strip()
                ]
                st.session_state["guidelines"][key] = {
                    "title": title.strip() or built_in["title"],
                    "steps": steps,
                }
                st.session_state[editing] = False
                st.rerun()
            if cancel.button("Cancel", key=f"cancel-{key}"):
                st.session_state[editing] = False
                st.rerun()
            if reset.button("Reset", key=f"reset-{key}"):
                st.session_state["guidelines"][key] = {
                    "title": built_in["title"],
                    "steps": list(built_in["steps"]),
                }
                st.session_state[editing] = False
                st.rerun()
        else:
            item_key = _ppe_item_key(key)
            reference = _reference_image(item_key)
            steps_column, image_column = (
                st.columns([2.6, 1])
                if reference is not None
                else (st.container(), None)
            )
            with steps_column:
                for index, step in enumerate(current["steps"], start=1):
                    st.markdown(
                        f'<span class="mono">{index:02d}</span> {html.escape(step)}',
                        unsafe_allow_html=True,
                    )
            if image_column is not None:
                with image_column:
                    _render_reference_image(item_key, f"Correct {_ppe_item_text(key)}")
            st.markdown(
                f'<div class="protocol-footer"><span class="detail-note">{"Customized" if current != built_in else "Built-in protocol"}</span><span class="badge {severity_class}">{severity_text}</span></div>',
                unsafe_allow_html=True,
            )


def render_guidelines() -> None:
    _page_header(
        "Response guidelines",
        "China construction safety response protocols. Customize steps to match site procedures.",
    )
    library, protocols = st.columns([1, 2.5])
    with library:
        with st.container(border=True):
            protocol_count = len(st.session_state["guidelines"])
            st.markdown("### Protocol library")
            st.markdown(
                f'<div class="detail-value">{protocol_count} active protocol{"s" if protocol_count != 1 else ""}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="library-legend"><div><span class="legend-dot legend-critical"></span>Critical: immediate stop and correct</div><div><span class="legend-dot legend-moderate"></span>Moderate: intervene and monitor</div><div><span class="legend-dot legend-recorded"></span>Response recorded by supervisor</div></div><div class="library-banner">Guidelines apply to new alerts automatically. Edit only the site-specific instruction; core safety steps remain visible to every supervisor.</div>',
                unsafe_allow_html=True,
            )
    with protocols:
        for key, built_in in BUILT_IN_GUIDELINES.items():
            _render_guideline_card(key, built_in)


def _today_records() -> list[LogRecord]:
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    records = _agent().filter_by_date_range(start=start, end=now)
    return [
        record
        for record in records
        if not (_assessment(record).source_detail or {}).get("synthetic")
    ]


def main() -> None:
    st.set_page_config(
        page_title="Site Sense",
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    _inject_css()
    _sidebar()
    navigation = st.navigation(
        [
            st.Page(render_dashboard, title="Dashboard", icon=":material/dashboard:"),
            st.Page(
                render_incident_log, title="Incident log", icon=":material/assignment:"
            ),
            st.Page(render_guidelines, title="Guidelines", icon=":material/menu_book:"),
        ],
        position="sidebar",
    )
    navigation.run()


if __name__ == "__main__":
    main()
