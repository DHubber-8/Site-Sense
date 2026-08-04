# AGENTS.md

Steering rules for AI coding tools (Claude Code, Zoo Code, Cline, etc.) working in this repo.
Read this before planning or editing anything.

## Project
Safety Monitoring & Response Agent — construction site PPE compliance + heat exhaustion
detection pipeline. See `REQUIREMENTS.md` and `TASKS.md` for full scope.

## Workflow — spec before code
- For any new feature or agent: **plan first, then implement.**
  - Claude Code: use Plan Mode (Shift+Tab twice) before editing files.
  - Zoo Code: use Architect mode (`/architect`) before switching to Code mode.
- Every planning session should produce a `plan.md` saved under `/specs/<feature-name>/plan.md`.
  Do not skip this step even for small changes — it's also our submission's design documentation.
- Don't start implementation until the plan has been reviewed by a human teammate, not just
  auto-approved.

## Repo structure
```
/agents
  /ppe_detection/
  /heat_detection/
  /risk_scoring/
  /alert_routing/
  /logging/
/taxonomy/
  ppe_severity.md
  heat_thresholds.md
/data/
  sample_images/
  heat_proxy_or_synthetic/
/dashboard/
/specs/
```
- One agent = one folder under `/agents/`. Don't merge multiple agents' logic into one file.
- Inter-agent data must be structured (JSON/dataclass), never passed as free-text strings.

## Protected files — do not edit without flagging
- `/taxonomy/ppe_severity.md` and `/taxonomy/heat_thresholds.md` are owned by the civil
  engineering teammate (C). These encode real safety-code and heat-stress research.
  - AI tools may **read** these freely for context.
  - AI tools must **not modify** these files directly. If a change seems needed, stop and
    flag it in the response rather than editing — a human (ideally C) makes the call.

## Tool-specific config
GitHub Copilot reads this file automatically, but also has its own config under `.github/`:
- `.github/instructions/taxonomy.instructions.md` — scopes the taxonomy protection rule above
  specifically to `/taxonomy/**`, enforced by Copilot directly.
- `.github/agents/planner.agent.md` and `.github/agents/implementer.agent.md` — Copilot's
  version of the plan-before-code workflow (equivalent to Claude Code's Plan Mode / Zoo Code's
  Architect mode).
- `.github/prompts/new-agent.prompt.md` — reusable prompt for starting a new agent module.

These are additive, not a separate set of rules — if you edit a convention in this file, check
whether the matching `.github/` file needs the same update.

## Coding conventions
- Python, managed with `uv` (not manual venv activation).
- Formatting: run `black .` after edits (see hooks below if your tool supports them).
- Commit message prefix: `feat/`, `fix/`, `docs/`, `refactor/` — one prefix per commit.
- No time estimates in planning output — focus plans on approach and file impact, not duration
  guesses.

## Heat detection — handle with care
- This pipeline currently uses a **proxy/simulated** heat-reading method, not live thermal
  camera data (documented in `REQUIREMENTS.md`). Any code touching this must make that
  limitation explicit in comments — don't write code or docs that imply this works on real
  thermal hardware as-is.
- False-positive filtering (duration tracking, ambient-temperature compensation) is a first-class
  requirement, not a nice-to-have. Don't strip it out to simplify a task.

## Data
- No real site data — only sample/public images and synthetic/simulated data live in `/data/`.
- Don't fabricate data that looks like real deployed-site output; keep synthetic data clearly
  synthetic (e.g. obvious placeholder site/worker names).

## Hooks (if your tool supports them)
- Post-edit: run `black .` on touched Python files.
- Pre-edit: block direct writes to `/taxonomy/*.md` (see Protected files above).

## Team
- E1, E2 — CS, own `/agents/` implementation
- C — Civil Engineering, owns `/taxonomy/`, data validation, and false-positive review