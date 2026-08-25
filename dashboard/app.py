from __future__ import annotations

import html
import json
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

from agents.logging import LoggingAgent
from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import Severity

DATABASE_PATH = str(PROJECT_ROOT / "data" / "site_sense.db")
SOURCE_LABELS = {"ppe": "PPE", "ppe_coverage": "PPE coverage", "heat_compliance": "Heat compliance", "heat_wbgt": "Heat exposure"}
STATUS_LABELS = {"active": "Active", "acknowledged": "Acknowledged", "resolved": "Resolved"}
SEVERITY_COLORS = {"Critical": ("#b42318", "#fff0ee"), "Moderate": ("#a15c00", "#fff7e6"), "Minor": ("#315f78", "#edf7fb")}
BUILT_IN_GUIDELINES: dict[str, dict[str, Any]] = {
    "no_helmet": {"title": "No helmet response protocol", "steps": ["Stop the worker from entering or continuing in the active work zone", "Issue a compliant safety helmet before work resumes", "Notify the site safety manager and record the intervention"]},
    "no_gloves": {"title": "No gloves response protocol", "steps": ["Pause the task involving hand or material hazards", "Issue task-appropriate protective gloves", "Confirm the worker has fitted the gloves before restarting"]},
    "no_boots": {"title": "Safety footwear violation response protocol", "steps": ["Remove the worker from the work zone immediately", "Issue GB 12011-compliant steel-toed safety footwear", "Examine the worker's feet for injuries before allowing return to work"]},
    "no_goggle": {"title": "No goggles response protocol", "steps": ["Stop exposure to dust, particles, or splash hazards", "Issue appropriate eye protection for the task", "Check the fit and lens condition before work resumes"]},
    "heat": {"title": "Heat stress emergency response protocol", "steps": ["Move the affected worker to a shaded, well-ventilated area immediately", "Provide cool potable water, at least 250 ml every 15 minutes", "Loosen or remove excess clothing and PPE to assist cooling", "Monitor vital signs and call first aid if the worker shows confusion or weakness", "Notify the site safety manager and record the daily heat exposure", "Enforce a 45-minute work and 15-minute rest cycle in the affected zone", "Review the heat management plan and reschedule heavy tasks if needed"]},
}


def _init_state() -> None:
    for key, default in {"incident_status": {}, "incident_notes": {}, "incident_steps": {}, "incident_times": {}, "guidelines": {}}.items():
        st.session_state.setdefault(key, default)
    for key, guideline in BUILT_IN_GUIDELINES.items():
        st.session_state["guidelines"].setdefault(key, {"title": guideline["title"], "steps": list(guideline["steps"])})


def _agent() -> LoggingAgent:
    return LoggingAgent(DATABASE_PATH)


def _query_records(*, severity: str = "All severities", source: str = "All categories", start: datetime | None = None, end: datetime | None = None) -> list[LogRecord]:
    agent = _agent()
    records = agent.filter_by_date_range(start, end) if start is not None or end is not None else agent.recent(limit=200)
    record_sets = [{record.record_id for record in records}]
    by_id = {record.record_id: record for record in records}
    if severity != "All severities":
        matches = agent.filter_by_severity(Severity[severity.upper()])
        record_sets.append({record.record_id for record in matches})
        by_id.update({record.record_id: record for record in matches})
    if source != "All categories":
        source_key = next(key for key, label in SOURCE_LABELS.items() if label == source)
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
    delta = max(datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc), timedelta(0))
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def _format_response_time(record: LogRecord) -> str:
    resolved_at = st.session_state["incident_times"].get(record.record_id, {}).get("resolved_at")
    if resolved_at is None:
        return "—"
    elapsed = max(resolved_at - _assessment(record).assessed_at, timedelta(0))
    minutes = int(elapsed.total_seconds() // 60)
    return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"


def _incident_name(record: LogRecord) -> str:
    assessment = _assessment(record)
    if assessment.source.startswith("heat"):
        return "Heat stress"
    return assessment.label.replace("no_", "No ").replace("_", " ").title()


def _confidence(record: LogRecord) -> float | None:
    value = (_assessment(record).source_detail or {}).get("confidence")
    return float(value) if value is not None else None


def _severity_badge(severity: str) -> str:
    foreground, background = SEVERITY_COLORS.get(severity, ("#334155", "#f1f5f9"))
    return f'<span class="badge" style="color:{foreground};background:{background};">{html.escape(severity)}</span>'


def _status_badge(status: str) -> str:
    return f'<span class="status-badge status-{status}">{STATUS_LABELS[status]}</span>'


def _inject_css() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    :root { --navy:#101b2d; --muted:#64748b; --line:#dce3ea; --surface:#fff; --page:#f4f6f8; --blue:#176b87; --amber:#c47b00; --red:#b42318; }
    .stApp { background:var(--page); color:var(--navy); font-family:'DM Sans',sans-serif; }
    [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
    [data-testid="stSidebarNav"] { display:block; } [data-testid="stSidebarNav"] a { color:var(--navy)!important; } [data-testid="stHeader"] { background:transparent; } [data-testid="stToolbar"] { visibility:hidden; }
    h1,h2,h3,h4,p,span,label,div { font-family:'DM Sans',sans-serif; } h1 { font-size:2rem!important; color:var(--navy)!important; } h2 { font-size:1.35rem!important; color:var(--navy)!important; }
    [data-testid="stMetric"] { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:1.1rem; box-shadow:0 2px 8px rgba(16,27,45,.04); } [data-testid="stMetricLabel"] { color:var(--muted); } [data-testid="stMetricValue"] { color:var(--navy); }
    .brand { display:flex; align-items:center; gap:.7rem; padding:.4rem 0 1.5rem; color:var(--navy); font-size:1.15rem; font-weight:700; } .brand-mark { display:grid; place-items:center; width:2rem; height:2rem; border-radius:5px; background:var(--navy); color:#fff; font-weight:700; }
    .eyebrow { color:var(--muted); font-size:.72rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; } .page-intro { color:var(--muted); margin-top:-.65rem; margin-bottom:1.5rem; }
    .surface { background:var(--surface); border:1px solid var(--line); border-radius:8px; box-shadow:0 2px 8px rgba(16,27,45,.04); } .section-head { display:flex; align-items:center; justify-content:space-between; padding:1.25rem 1.35rem; border-bottom:1px solid var(--line); } .section-head h2 { margin:0; } .section-head p { color:var(--muted); margin:.2rem 0 0; font-size:.88rem; }
    .count { background:#edf2f6; color:var(--navy); padding:.25rem .55rem; border-radius:999px; font-family:'IBM Plex Mono',monospace; font-size:.8rem; } .badge,.status-badge { display:inline-block; border-radius:2px; padding:.24rem .48rem; font-size:.72rem; font-weight:700; white-space:nowrap; } .status-badge { border:1px solid; border-radius:999px; }
    .status-active { color:var(--red); background:#fff0ee; border-color:#f2b8b5; } .status-acknowledged { color:var(--amber); background:#fff7e6; border-color:#f2d18d; } .status-resolved { color:var(--blue); background:#edf7fb; border-color:#a9d5df; }
    .alert-row { padding:1rem 1.35rem; border-bottom:1px solid var(--line); } .alert-row:last-child { border-bottom:0; } .alert-row.critical { border-left:4px solid var(--red); padding-left:1.1rem; } .alert-title { display:flex; align-items:center; gap:.55rem; font-weight:700; color:var(--navy); } .alert-meta { color:var(--muted); font-family:'IBM Plex Mono',monospace; font-size:.76rem; margin:.45rem 0 .8rem; } .muted { color:var(--muted); } .empty { text-align:center; padding:3rem 1rem; color:var(--muted); } .mono { font-family:'IBM Plex Mono',monospace; } .mobile-brand { display:none; } button { border-radius:5px!important; }
    button { background:#fff!important; color:var(--navy)!important; border:1px solid var(--line)!important; } button p { color:inherit!important; } button[kind="primary"] { background:var(--navy)!important; color:#fff!important; border-color:var(--navy)!important; } button[kind="primary"] p { color:#fff!important; }
    @media (max-width:800px) { .mobile-brand { display:block; } .page-intro { margin-bottom:1rem; } }
    </style>
    """, unsafe_allow_html=True)


def _sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="brand"><span class="brand-mark">S</span><span>Site Sense</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="eyebrow">Active site</div>', unsafe_allow_html=True)
        st.selectbox("Active site", ["Riverside Tower"], label_visibility="collapsed")
        st.caption("System status: Online")
        st.caption(f"Last sync: {datetime.now().strftime('%H:%M')}")


def _page_header(title: str, description: str) -> None:
    st.markdown('<div class="mobile-brand brand"><span class="brand-mark">S</span><span>Site Sense</span></div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<p class="page-intro">{html.escape(description)}</p>', unsafe_allow_html=True)


def _render_heat_chart(records: list[LogRecord]) -> None:
    points = []
    for record in records:
        detail = _assessment(record).source_detail or {}
        value = detail.get("air_temperature_c", detail.get("wbgt_c"))
        if value is not None:
            points.append({"time": record.recorded_at, "temperature": float(value)})
    st.markdown('<div class="surface">', unsafe_allow_html=True)
    st.markdown('<div class="section-head"><div><h2>Heat exposure trend</h2><p>Average worker temperature over the last six hours</p></div></div>', unsafe_allow_html=True)
    if not points:
        st.markdown('<div class="empty">No heat telemetry is available for this period.</div>', unsafe_allow_html=True)
    else:
        frame = pd.DataFrame(points).sort_values("time")
        figure = go.Figure(go.Scatter(x=frame["time"], y=frame["temperature"], mode="lines+markers", name="Worker temperature", line={"color": "#d89200", "width": 3}, marker={"color": "#d89200", "size": 7}))
        figure.add_hline(y=38, line_dash="dash", line_color="#b42318", annotation_text="Danger threshold 38°C", annotation_position="top left")
        figure.update_layout(height=330, margin={"l": 10, "r": 20, "t": 20, "b": 10}, paper_bgcolor="white", plot_bgcolor="white", font={"family": "DM Sans", "color": "#64748b"}, xaxis={"showgrid": False}, yaxis={"title": "°C", "gridcolor": "#e6ebef"}, hovermode="x unified")
        st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)


@st.dialog("Incident response")
def _resolution_dialog(record_id: str, action: str) -> None:
    record = next((item for item in _query_records() if item.record_id == record_id), None)
    if record is None:
        st.error("This incident is no longer available.")
        return
    assessment = _assessment(record)
    st.markdown(f"### {_incident_name(record)}")
    st.caption(f"{assessment.zone or 'Unassigned zone'} · {_relative_time(assessment.assessed_at)} · {assessment.severity.name.title()}")
    guideline = st.session_state["guidelines"].get("heat" if assessment.source.startswith("heat") else assessment.label)
    selected: list[int] = []
    if guideline:
        st.markdown(f"**{guideline['title']}**")
        for index, step in enumerate(guideline["steps"], start=1):
            if st.checkbox(f"{index}. {step}", key=f"dialog-{record_id}-{index}"):
                selected.append(index)
    else:
        st.info("No guideline is configured. Add resolution notes to record the response.")
    notes = st.text_area("Resolution notes", value=st.session_state["incident_notes"].get(record_id, ""), placeholder="Describe the corrective action taken...")
    cancel, submit = st.columns(2)
    if cancel.button("Cancel", use_container_width=True):
        st.rerun()
    if submit.button("Mark resolved" if action == "resolve" else "Mark acknowledged", type="primary", use_container_width=True):
        now = datetime.now(timezone.utc)
        st.session_state["incident_status"][record_id] = "resolved" if action == "resolve" else "acknowledged"
        st.session_state["incident_notes"][record_id] = notes
        st.session_state["incident_steps"][record_id] = selected
        times = st.session_state["incident_times"].setdefault(record_id, {})
        times.setdefault("acknowledged_at", now)
        if action == "resolve":
            times["resolved_at"] = now
        st.rerun()


def _alert_actions(record: LogRecord, key_prefix: str) -> None:
    status = _status(record)
    if status == "active" and st.button("Acknowledge", key=f"ack-{key_prefix}-{record.record_id}"):
        _resolution_dialog(record.record_id, "acknowledge")
    elif status == "acknowledged" and st.button("Resolve", key=f"resolve-{key_prefix}-{record.record_id}"):
        _resolution_dialog(record.record_id, "resolve")


def _alert_card(record: LogRecord, key_prefix: str) -> None:
    assessment = _assessment(record)
    confidence = _confidence(record)
    confidence_text = f"{confidence:.0%} confidence" if confidence is not None else "Confidence unavailable"
    st.markdown(f'<div class="alert-row {"critical" if assessment.severity is Severity.CRITICAL else ""}"><div class="alert-title">{_severity_badge(assessment.severity.name.title())} {html.escape(_incident_name(record))} {(_status_badge(_status(record)) if _status(record) != "active" else "")}</div><div class="alert-meta">{html.escape(assessment.zone or "Unassigned zone")} · {confidence_text} · {_relative_time(record.recorded_at)}</div><div class="muted">{html.escape(assessment.description)}</div></div>', unsafe_allow_html=True)
    action, details = st.columns(2)
    with action:
        _alert_actions(record, key_prefix)
    with details:
        if st.button("View details", key=f"detail-{key_prefix}-{record.record_id}"):
            st.session_state["selected_incident"] = record.record_id
            st.rerun()


def render_dashboard() -> None:
    _page_header("Site overview", "Real-time safety telemetry and critical alerts.")
    records = _query_records()
    today = _today_records()
    active = [record for record in records if _status(record) != "resolved"]
    ppe_records = [record for record in records if _assessment(record).source.startswith("ppe")]
    heat_records = [record for record in records if _assessment(record).source.startswith("heat")]
    ppe_positive = sum(1 for record in ppe_records if not _assessment(record).label.startswith("no_"))
    compliance = round(100 * ppe_positive / len(ppe_records)) if ppe_records else 0
    metrics = st.columns(4)
    metrics[0].metric("Active alerts", len(active), "Require attention")
    metrics[1].metric("PPE compliance", f"{compliance}%", "Across recorded PPE events")
    metrics[2].metric("Heat risk exposure", len([r for r in heat_records if _assessment(r).severity is not Severity.NONE]), "Workers above safe threshold")
    metrics[3].metric("Incidents today", len(today), "Events logged today")
    left, right = st.columns([1.05, .95])
    with left:
        st.markdown(f'<div class="surface"><div class="section-head"><div><h2>Active alerts</h2><p>Latest unresolved incidents</p></div><span class="count">{len(active)}</span></div>', unsafe_allow_html=True)
        if active:
            for record in active[:10]:
                _alert_card(record, "dashboard")
        else:
            st.markdown('<div class="empty">All monitored zones are clear.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        now = datetime.now(timezone.utc)
        _render_heat_chart(_query_records(start=now - timedelta(hours=6), end=now))


def _incident_details(record: LogRecord) -> None:
    assessment = _assessment(record)
    detail = assessment.source_detail or {}
    confidence = _confidence(record)
    st.markdown(f"**Incident identifier:** `{record.record_id}`")
    st.markdown(f"**Event type:** {_incident_name(record)} · **Detected:** {_relative_time(assessment.assessed_at)}")
    st.progress(confidence or 0, text=f"Detection confidence: {confidence:.0%}" if confidence is not None else "Detection confidence: unavailable")
    st.markdown(f"**Response time:** {_format_response_time(record)}")
    notes = st.session_state["incident_notes"].get(record.record_id)
    if notes:
        st.markdown(f"**Resolution notes:** {html.escape(notes)}")
    st.code(json.dumps({"bounding_box": detail.get("bounding_box"), "model_metadata": detail}, indent=2, default=str), language="json")


def render_incident_log() -> None:
    _page_header("Incident log", "A comprehensive history of safety events and actions taken.")
    controls = st.columns([1.7, 1, 1, 1])
    search = controls[0].text_input("Search", placeholder="Search by zone, item, or incident ID")
    severity = controls[1].selectbox("Severity", ["All severities", "Critical", "Moderate", "Minor"])
    category = controls[2].selectbox("Category", ["All categories", *SOURCE_LABELS.values()])
    status = controls[3].selectbox("Status", ["All statuses", *STATUS_LABELS.values()])
    records = _query_records(severity=severity, source=category)
    if search:
        needle = search.lower()
        records = [record for record in records if needle in " ".join([record.record_id, _assessment(record).label, _assessment(record).zone or ""]).lower()]
    if status != "All statuses":
        selected = next(key for key, value in STATUS_LABELS.items() if value == status)
        records = [record for record in records if _status(record) == selected]
    st.markdown('<div class="surface"><div class="section-head"><div><h2>Safety events</h2><p>Expand a row to inspect evidence and response data.</p></div><span class="count">{}</span></div>'.format(len(records)), unsafe_allow_html=True)
    if not records:
        st.markdown('<div class="empty">No incidents match the selected filters.</div>', unsafe_allow_html=True)
    for record in records:
        assessment = _assessment(record)
        with st.expander(f"{_incident_name(record)} · {assessment.zone or 'Unassigned zone'} · {_status(record).title()}"):
            columns = st.columns([1.3, 1.1, 1, 1, 1])
            columns[0].markdown(f"**Timestamp**<br><span class='mono'>{record.recorded_at.strftime('%b %d, %Y %H:%M')}</span>", unsafe_allow_html=True)
            columns[1].markdown(f"**Severity**<br>{_severity_badge(assessment.severity.name.title())}", unsafe_allow_html=True)
            columns[2].markdown(f"**Status**<br>{_status_badge(_status(record))}", unsafe_allow_html=True)
            columns[3].markdown(f"**Response time**<br><span class='mono'>{_format_response_time(record)}</span>", unsafe_allow_html=True)
            with columns[4]:
                _alert_actions(record, "log")
            _incident_details(record)
    st.markdown('</div>', unsafe_allow_html=True)


def render_guidelines() -> None:
    _page_header("Response guidelines", "China construction safety response protocols. Customize steps to match site procedures.")
    for key, built_in in BUILT_IN_GUIDELINES.items():
        current = st.session_state["guidelines"][key]
        with st.container(border=True):
            top = st.columns([3, 1, 1])
            top[0].markdown(f"### {built_in['title']}\n<span class='muted'>{key.replace('_', ' ').title()}</span>", unsafe_allow_html=True)
            top[1].markdown("<br>" + ("<span class='status-badge status-acknowledged'>Custom</span>" if current != built_in else "<span class='status-badge status-resolved'>Built-in</span>"), unsafe_allow_html=True)
            editing = f"editing-{key}"
            if top[2].button("Edit", key=f"edit-{key}"):
                st.session_state[editing] = True
            if st.session_state.get(editing):
                title = st.text_input("Protocol title", value=current["title"], key=f"title-{key}")
                edited = st.data_editor(pd.DataFrame({"Step": current["steps"]}), num_rows="dynamic", hide_index=True, key=f"editor-{key}", use_container_width=True)
                # Data editor supports add/remove; drag-reorder remains a future enhancement.
                save, cancel, reset = st.columns(3)
                if save.button("Save changes", key=f"save-{key}", type="primary"):
                    steps = [str(step).strip() for step in edited["Step"].tolist() if str(step).strip()]
                    st.session_state["guidelines"][key] = {"title": title.strip() or built_in["title"], "steps": steps}
                    st.session_state[editing] = False
                    st.rerun()
                if cancel.button("Cancel", key=f"cancel-{key}"):
                    st.session_state[editing] = False
                    st.rerun()
                if reset.button("Reset", key=f"reset-{key}"):
                    st.session_state["guidelines"][key] = {"title": built_in["title"], "steps": list(built_in["steps"])}
                    st.session_state[editing] = False
                    st.rerun()
            else:
                for index, step in enumerate(current["steps"], start=1):
                    st.markdown(f"{index}. {html.escape(step)}")


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
    st.set_page_config(page_title="Site Sense", page_icon="S", layout="wide", initial_sidebar_state="expanded")
    _init_state()
    _inject_css()
    _sidebar()
    navigation = st.navigation([
        st.Page(render_dashboard, title="Dashboard", icon=":material/dashboard:"),
        st.Page(render_incident_log, title="Incident log", icon=":material/assignment:"),
        st.Page(render_guidelines, title="Guidelines", icon=":material/menu_book:"),
    ], position="sidebar")
    navigation.run()


if __name__ == "__main__":
    main()
