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
from PIL import Image

from agents.logging.schema import LogRecord
from agents.risk_scoring.schema import Severity
from dashboard.data import (
    MONITORED_SOURCES,
    SOURCE_LABELS,
    STATUS_LABELS,
    _agent,
    _assessment,
    _latest_record,
    _query_records,
    _reporting_sources,
    _today_records,
    _wbgt_high_risk_threshold,
)
from dashboard.styles import inject_css

VISIBLE_ALERT_LIMIT = 10
PPE_ALERT_SLOTS = 4
REFERENCE_IMAGE_DIR = PROJECT_ROOT / "data" / "reference_ppe"
REFERENCE_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
LOGO_PATH = PROJECT_ROOT / "dashboard" / "assets" / "logo.png"
PPE_CORE_ITEMS = ("helmet", "gloves", "boots", "goggles", "vest")
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


def _brand_logo() -> Image.Image:
    with Image.open(LOGO_PATH) as logo:
        return logo.crop((250, 100, 1000, 850)).copy()


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

    These are illustrative reference images only, distinct from _evidence_image below: a
    reference photo shows what correct PPE looks like in general, not what happened in this
    particular incident.
    """
    for suffix in REFERENCE_IMAGE_SUFFIXES:
        candidate = REFERENCE_IMAGE_DIR / f"{item_key}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _evidence_image(record: LogRecord) -> Path | None:
    """The real frame a PPE detection came from, when the record has one on disk.

    Distinct from _reference_image: this points at the actual incident, not a stand-in
    "correct PPE" example. Silently absent for heat sources (no frame exists to point at) and
    for any record whose stored path no longer resolves.
    """
    path_str = _assessment(record).evidence_image
    if not path_str:
        return None
    path = Path(path_str)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


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


def _render_evidence_image(record: LogRecord, *, width: int = REFERENCE_WIDTH) -> None:
    """Render the real incident photo when one exists; stay silent when there is none."""
    path = _evidence_image(record)
    if path is None:
        return
    st.markdown(
        '<div class="detail-label reference-label">Incident evidence</div>',
        unsafe_allow_html=True,
    )
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
        _render_evidence_image(record)
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
    _render_evidence_image(record)


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


def main() -> None:
    st.set_page_config(
        page_title="Site Sense",
        page_icon=str(LOGO_PATH),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    inject_css()
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
