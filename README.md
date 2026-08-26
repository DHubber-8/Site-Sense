# Site Sense

An AI agent system that monitors construction sites for two categories of worker risk: **PPE non-compliance** and **heat exhaustion**. Built for the 海之子杯 (Son of the Sea Cup) AI Agent Challenge, hosted by China State Construction International.

Using a multi-agent pipeline, Site Sense detects missing safety equipment and elevated body-temperature signals, classifies findings by severity against real safety-code and occupational heat-stress thresholds, and routes alerts to site managers in a way that surfaces genuine risks without drowning them in noise — including a dedicated false-positive filtering layer for heat detection, since ambient sun exposure and sensor drift can easily be mistaken for physiological heat stress.

Every flagged incident is logged with a timestamped compliance trail, giving managers both real-time alerts and a historical record. Built with construction's climate conditions in mind — particularly relevant in high-heat regions where heat exhaustion is an underrepresented but serious site risk alongside traditional PPE compliance.

---

## Status

This project is under active development, now in final polish ahead of submission. Current state:

| Component | Status |
|---|---|
| PPE detection agent | ✅ Implemented — fine-tuned YOLO26 checkpoint (100 epochs), verified against real sample images. Known limitation: `no_boots` detection is unreliable due to limited training data (4 instances). |
| Heat detection agent | ✅ Implemented — two paths: weather-forecast compliance alerts (Open-Meteo default, OpenWeather fallback) and simulated WBGT risk levels with sustained-elevation false-positive filtering |
| Risk scoring agent | ✅ Implemented — normalizes PPE, heat-compliance, and WBGT detections into one shared severity model (`Severity.NONE/MINOR/MODERATE/CRITICAL`), plus a batch-level PPE-coverage check for unverifiable items |
| Alert routing agent | ✅ Implemented — severity-based routing (log-only for minor, active notification for moderate/critical) |
| Logging agent | ✅ Implemented — persists every assessment + routing decision to the SQLite store (`data/site_sense.db`) |
| Dashboard | ✅ Implemented — Streamlit manager UI with real-time alerts, incident history, PPE vs. heat visual distinction, and a heat-exposure trend chart; refinement ongoing (see `specs/dashboard-refinement/plan.md`) |
| PPE severity taxonomy | ✅ Complete |
| Heat-stress thresholds | ✅ Complete — both WBGT-based and compliance-alert tiers defined |

## How it works (pipeline)

```
Site image / weather + simulated sensor input
        │
   ┌────┴────┐
PPE detection   Heat detection  ✅ both implemented
   └────┬────┘
        │  (scored against /taxonomy)
   Risk scoring          ✅ implemented
        │
   Alert routing         ✅ implemented
        │
   ┌────┴────┐
Dashboard   Logging      ✅ both implemented
```

## Repo structure

```
agents/
  ppe_detection/     PPE detection agent (implemented)
  heat_detection/     Heat detection agent — compliance + WBGT paths (implemented)
  risk_scoring/        Severity classification agent (implemented)
  alert_routing/       Alert dispatch agent (implemented)
  logging/              Compliance/incident logging (implemented)
taxonomy/               Severity + threshold definitions (owned by domain lead,
                         see AGENTS.md — protected from direct AI edits)
data/                   Sample images and synthetic/proxy data (no real site data)
dashboard/              Manager-facing UI (implemented, ongoing refinement)
specs/                  Plan docs produced before implementation (spec-driven workflow),
                         including the risk-scoring integration contract
scripts/                One-off scripts (model training, demo data seeding, reference-image
                         generation, heat scenario export)
tests/                  Test suite
```

## Getting started

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/DHubber-8/Site-Sense.git
cd Site-Sense
uv sync
```

Run the test suite:
```bash
uv run pytest
```

Run the manager dashboard locally:
```bash
cd Site-Sense
uv run streamlit run dashboard/app.py
```

The dashboard reads the existing SQLite logging store in `data/site_sense.db` and will seed a small demo dataset automatically if no alerts have been recorded yet.

Run the PPE detection agent against a sample image — see `agents/ppe_detection/README.md` for usage and current checkpoint notes.

## Project docs

- [`REQUIREMENTS.md`](./REQUIREMENTS.md) — functional and non-functional requirements
- [`TASKS.md`](./TASKS.md) — task breakdown and team ownership
- [`AGENTS.md`](./AGENTS.md) — conventions for AI coding tools working in this repo (spec-driven workflow, protected files, coding standards)

## Contributing / workflow

This project follows a spec-driven workflow: every new agent or feature gets a plan doc under `/specs/` before implementation begins. See `AGENTS.md` for full conventions. Changes to `/taxonomy/` require review from the domain lead.

## Team

Built by a 3-person team across Computer Science and Civil Engineering backgrounds for the 海之子杯 AI Agent Challenge, 2026.