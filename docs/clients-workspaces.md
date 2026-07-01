# Client Workspaces — CM/AI-Enablement engagements

This subsystem turns Odysseus into a delivery platform for Change-Management &
AI-Enablement engagements built on the Kaldway **"Path 1 — Identity Transition"**
methodology. It adds a first-class **Client** workspace model, an owner-scoped API,
an agent tool, and the methodology rules + synthesis core.

> Status: Phases 00/01 and the Phase 03/04 foundations. The in-app LLM synthesis
> *route* (endpoint-resolved) and the Google/Notion integrations are follow-on work.

## Data model (`core/database.py`)

Methodology-native tables, all owner-scoped (`owner` column), FK-cascaded:

| Table | Purpose | Mirrors |
|---|---|---|
| `clients` | Engagement workspace (sponsor, sector, per-client `model_policy`) | — |
| `client_stakeholders` | Primary stakeholder (archetype, transition stage) | ITM archetype library |
| `itm_records` | Identity Transition Map — 5 dimensions + review state | ITM Template v1.2 |
| `tri_scorecards` | Transition Readiness Instrument scorecard (10 items, total, stage, `tri_version`) | TRI v1.2 |
| `bridging_rituals` | Designed identity-affirming moments | Dashboard Spec DB3 |
| `meeting_transcripts` | Raw synthesis input (source/external_ref for provenance) | — |

The schema deliberately matches the three Notion databases in the methodology's
Transition Dashboard Spec, so the (future) Notion sync is a field-for-field map.

## Service layer (`src/clients.py`)

Strict owner-scoping (confidential client data is **not** shared via null-owner
fall-through, unlike the app-wide `owner_filter`). Key functions: client CRUD;
stakeholder CRUD; `upsert_itm`; `add_tri` (a TRI total auto-derives the stage via
`src/methodology.py`); rituals; `recommend_frames`; transcripts; `portfolio`
(stuck-first, then soonest next-ritual-due); `portfolio_summary`;
`build_synthesis_context`.

## Methodology rules (`src/methodology.py`)

Deterministic, data-driven: `tri_stage(total)` (10–18 stuck / 19–27 moving /
28–34 landing / 35–40 landed) + `recommended_action`; the archetype × stage comms
**frame-selection matrix** (`select_frames`); ITM dimensions / archetypes / stages;
the avoid-frames list.

## Synthesis (`src/synthesis.py`)

`build_synthesis_prompt(context, artifact_kind)` assembles a methodology-grounded
prompt (ITM expected-loss, recommended frames, avoid-list, transcript).
`synthesize(...)` runs the LLM (endpoint supplied by the caller). Artifact kinds:
`session_summary`, `comms_draft`, `journey_update`, `risk_log`, `itm_update`,
`tri_assessment`.

## REST API (`routes/client_routes.py`, prefix `/api/clients`)

All endpoints require an authenticated user; cross-owner access returns `404`.

- `GET /` · `POST /` · `GET|PUT|DELETE /{client_id}`
- `GET /portfolio` · `GET /portfolio/summary`
- `GET /methodology` · `GET /methodology/frames?archetype=&stage=` · `GET /methodology/tri/{total}`
- `GET|POST /{client_id}/stakeholders` · `PUT|DELETE /stakeholders/{id}`
- `GET|PUT /stakeholders/{id}/itm` · `GET|POST /stakeholders/{id}/tri` · `GET /stakeholders/{id}/frames`
- `POST /stakeholders/{id}/rituals` · `POST /rituals/{id}/complete`
- `GET|POST /{client_id}/transcripts` · `GET|DELETE /transcripts/{id}` · `GET /transcripts/{id}/synthesis-context`

## Agent tool — `manage_clients`

Lets the in-app agent operate engagements end to end (the "agentic life-OS").
Single `action` parameter; actions cover the full surface above (portfolio,
client/stakeholder/ITM/TRI/ritual/transcript CRUD, `recommend_frames`,
`synthesis_context`, `portfolio_summary`). Owner-scoped via the agent's resolved
owner. Defined in `src/tool_schemas.py` + `src/tool_implementations.py`, dispatched
in `src/tool_execution.py`.

## Tests

`tests/test_client_workspace_model.py`, `test_clients_service.py`,
`test_client_routes.py`, `test_methodology.py`, `test_manage_clients_tool.py`,
`test_transcripts.py`, `test_synthesis.py`, `test_clients_phase1_extras.py`
(37 tests). Each uses a module-scoped throwaway DB (rebinds `SessionLocal`) so the
suite stays isolated.

## Follow-on (not yet built)

- Synthesis **route/tool** with the user's resolved LLM endpoint.
- **Google** (Gmail OAuth, Calendar+Meet) and **Notion** (transcript ingest + artifact push) integrations.
- Per-client **team RBAC** (so a teammate can be granted access beyond the creator).
- Local-model **sensitivity routing** keyed off `client.model_policy`.
- A **client switcher** + dashboard UI.
