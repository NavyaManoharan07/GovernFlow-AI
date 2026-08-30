# GovFlow AI

**Autonomous Government Service Orchestration Agent** — a hackathon prototype.

---

## Problem

Starting a small business (or completing almost any multi-step government
process) means navigating several independent services — business
registration, tax registration, sector-specific licenses, local approvals —
each with its own eligibility rules, document requirements, and processing
timeline, and each often gated on the previous one finishing first. Today
that means a person manually tracking which office to contact next,
re-explaining their situation at every step, and polling for status updates
by hand. There's no single system that plans the whole sequence, knows the
dependencies between services, watches for outcomes, and reacts — a person
has to be the orchestrator.

## Solution

GovFlow AI takes one sentence — *"I want to start a small food-processing
business in Tamil Nadu"* — and autonomously plans, routes, submits, and
tracks the entire multi-step government workflow it implies, reacting to
real events (an application gets approved, rejected, or comes back needing
more documents) rather than running one hardcoded script. Ten specialized
agents communicate exclusively through an event bus, each reacting only to
the event type(s) relevant to its job; a human is looped in only when a
step is genuinely risky or uncertain (a rejection, an ineligibility
finding), never for routine progress. Every decision is logged to an audit
trail with a citation back to the (mock) regulation that justified it.

## Why this is an autonomous agent, not a chatbot

A chatbot answers questions in a turn-by-turn conversation and stops
existing between messages. GovFlow AI does none of that — it is a
standing, event-driven system that keeps running after the user has left.
Concretely, evidenced by the actual code:

- **It plans.** `WorkflowPlannerAgent` (`backend/agents/workflow_planner.py`)
  derives which of the four catalog services a specific goal requires and
  the dependency edges between them via a real Gemini call — not a fixed
  script — then builds an executable `WorkflowGraph`
  (`backend/workflows/graph.py`).
- **It routes.** `DepartmentRouterAgent`
  (`backend/agents/department_router.py`) deterministically maps each
  ready step to the correct mock government service and tool.
- **It calls tools, not just text.** Every agent action that touches the
  outside world goes through a strict, schema-validated tool allowlist
  (`backend/tools/registry.py: invoke_tool`) — an agent can never execute
  arbitrary code or a free-form API call; only a registered tool with a
  Pydantic input/output contract.
- **It changes state.** `WorkflowEngine` (`backend/workflows/engine.py`)
  is a real state machine — `RUNNING` → `WAITING_FOR_USER` / `BLOCKED` →
  `COMPLETED` / `FAILED` — driven entirely by events, not by a human
  clicking "next."
- **It reacts to events, autonomously, asynchronously.** There is no
  single function that runs the whole workflow top to bottom. Publishing
  one `USER_REQUEST_CREATED` event cascades through
  `GoalInterpreterAgent` → `RegulationAgent` → `WorkflowPlannerAgent` →
  `EligibilityAgent` → `DocumentAgent` → `DepartmentRouterAgent` →
  `ApplicationAgent` → `StatusMonitorAgent` → back to
  `WorkflowPlannerAgent`'s graph for the next ready step — each hop a
  *different* agent reacting to an event it subscribed to
  (`backend/agents/wiring.py`), with zero further input from the caller.
  `POST /api/workflows` returns in milliseconds; the agent chain keeps
  running in the background (`WorkflowEngine.start_user_goal_async`).
- **It monitors an external, asynchronous process.** `StatusMonitorAgent`
  (`backend/agents/status_monitor.py`) runs a genuine `asyncio` background
  polling loop against the mock government API — not a fixed delay, not a
  frontend animation — and reacts the moment a real status changes.
- **It maintains audit history.** Every decision, tool call, and state
  transition is written to a durable audit trail
  (`backend/models/audit.py`, `AuditRepository`) — queryable via
  `GET /api/workflows/{id}/audit` and rendered live in the dashboard —
  independent of and in addition to each agent's own logging, via
  `AuditAgent`'s bus-wide safety net (`backend/agents/audit.py`).

Nothing in this system is a canned response keyed to user text. The RAG
retriever returns nothing rather than inventing a rule; the mock
government API scenario is the only thing forced deterministic for the
demo, and only via an explicit `metadata.scenario` field the frontend
sets when running the demo — a real user's goal always goes through the
same real agent chain with no scripted shortcuts.

## Architecture

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                     React Dashboard                     │
                    │   Command Center · Workflow Graph · Agent Registry ·     │
                    │   Application Tracker · Audit Trail                     │
                    └───────────────┬─────────────────────┬───────────────────┘
                                    │ REST (fetch)          │ WebSocket
                                    ▼                        ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │                      FastAPI backend                     │
                    │  backend/api/routes.py        backend/api/websocket.py  │
                    └───────────────┬─────────────────────┬───────────────────┘
                                    │ publish/subscribe     │ subscribe_all
                                    ▼                        │
                    ┌─────────────────────────────────────────────────────────┐
                    │                Event Bus (InProcessEventBus)             │
                    │        backend/events/bus.py + retry.py + registry.py   │
                    └──┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────────┘
                       │    │    │    │    │    │    │    │    │    │
        ┌──────────────┘    │    │    │    │    │    │    │    │    └────────────┐
        ▼                   ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼                 ▼
   GoalInterpreter    Regulation  WorkflowPlanner  Eligibility  Document   ...   AuditAgent
     Agent (Gemini)   Agent(RAG)   Agent (Gemini)  Agent(Gemini) Agent          (wildcard,
        │                  │             │              │          │            every event)
        │                  ▼             │              │          ▼
        │          knowledge_base/  ┌────┘              │    mock_services/
        │          (TF-IDF RAG)     ▼                    │    (validate_document)
        │                    WorkflowEngine ◄─────────────┘
        │                    (state machine, WorkflowGraph)
        ▼                           │
   Tool Registry ◄───────────────────┘
   (backend/tools/registry.py: strict, schema-validated allowlist)
        │
        ▼
   mock_services/ (FastAPI router simulating 4 government APIs)
        ▲
        │ polled by
   StatusMonitorAgent (real asyncio background loop)
        │
        ▼
   DepartmentRouterAgent → ApplicationAgent → StatusMonitorAgent → (loop back to WorkflowEngine)

   SQLite (backend/services/): Workflow / Event / Audit / Notification repositories
```

> **A separate visual architecture diagram image is required for the
> hackathon submission** (this ASCII sketch is not a substitute). It
> should show: the three tiers above (dashboard → API/WebSocket →
> event bus), the 10 agents as nodes fanning out from the event bus with
> arrows labeled by the event type each one subscribes to (see "Event-driven
> workflow" below for the exact list), the tool registry + mock government
> API layer beneath the agents, the RAG knowledge base feeding
> `RegulationAgent`/`EligibilityAgent`/`DocumentAgent`, and the SQLite
> persistence layer with its four repositories. The human-in-the-loop gate
> (`WorkflowEngine.block_step`/`block_workflow` ⇄ a `WORKFLOW_RESUMED`
> event from the dashboard) is worth calling out explicitly, since it's
> the feature most likely to need explaining to a judge.

## Agent responsibilities

| Agent | Responsibility |
|---|---|
| `GoalInterpreterAgent` | Parses the user's high-level goal into structured intent via Gemini |
| `RegulationAgent` | Retrieves applicable rules from the RAG knowledge base, with citations |
| `WorkflowPlannerAgent` | Derives the required services + dependency graph via Gemini and builds the `WorkflowGraph` |
| `EligibilityAgent` | Checks eligibility against retrieved rules via Gemini |
| `DocumentAgent` | Builds the document checklist and validates provided documents |
| `DepartmentRouterAgent` | Deterministically routes each ready step to the correct mock government service |
| `ApplicationAgent` | Prepares and submits applications to the routed mock service |
| `StatusMonitorAgent` | Polls application status (real asyncio background loop) and reacts to approval/rejection/missing documents |
| `NotificationAgent` | Produces human-readable notifications for workflow events |
| `AuditAgent` | Bus-wide safety net — guarantees every event is recorded in the audit trail |

## Event-driven workflow

The real `EventType` enum (`backend/models/enums.py`), in the order a
typical successful run fires them:

```
USER_REQUEST_CREATED → GOAL_ANALYZED → REQUIREMENTS_IDENTIFIED → WORKFLOW_CREATED
  → ELIGIBILITY_CHECKED → NEXT_ACTION_TRIGGERED → DOCUMENTS_VALIDATED
  → APPLICATION_READY → APPLICATION_SUBMITTED → APPLICATION_STATUS_CHANGED*
  → APPLICATION_APPROVED → (NEXT_ACTION_TRIGGERED, loop per remaining service)
  → WORKFLOW_COMPLETED
```

Alternate/exception events: `DOCUMENT_MISSING`, `APPLICATION_REJECTED`,
`USER_ACTION_REQUIRED` (the human-in-the-loop gate opening),
`WORKFLOW_RESUMED` (the gate closing again, published by
`POST /api/workflows/{id}/events`), `WORKFLOW_FAILED` (unrecoverable —
retry exhaustion or an abandoned step).

No single function drives this sequence — see `backend/agents/wiring.py`
for the full declarative event type → agent-handler mapping.

## RAG architecture

- **Knowledge base** (`knowledge_base/*.md`): six documents, each headed
  "MOCK / DEMONSTRATION DATA — not real current law," covering business
  registration, tax registration, food license, and local approval
  requirements, eligibility rules, required documents, and service
  dependencies. Every requirement line follows
  `- REQ-<PREFIX>-<N>: <text> (Service: <tag>) (Source: <citation>)` — the
  citation is always an invented source like *"Demo Municipal Business
  Code §4.2 (MOCK)"*.
- **Chunking** (`backend/rag/documents.py`): each `REQ-` line becomes one
  precise, citable chunk; surrounding prose (Overview/Processing/Notes
  sections) becomes lower-priority supplementary chunks.
- **Retrieval** (`backend/rag/retriever.py`): a dependency-free,
  pure-Python TF-IDF + cosine-similarity index — no
  sentence-transformers/sklearn install, so the demo runs identically
  offline. A fixed stopword list plus unsmoothed IDF (a term in every
  chunk gets weight exactly 0) keeps a query built mostly of function
  words from picking up false-positive similarity.
- **No hallucination, by construction**: below a confidence floor,
  `retrieve()` returns an empty list rather than a weak match, and every
  agent that consults RAG (`RegulationAgent`, `EligibilityAgent`,
  `DocumentAgent`) only ever forwards what retrieval actually returned —
  never invents a requirement.
- **Citation format surfaced to the API/UI**: `{ "requirement": str,
  "source": str, "confidence": float }` per result
  (`backend/rag/schemas.py: RetrievedRule`).

## Tech stack

**Backend:** Python 3.11, FastAPI 0.115, Pydantic v2.10, SQLite (stdlib
`sqlite3`), `google-genai` 2.20.0 (the current unified Google GenAI SDK —
*not* the older, effectively-frozen `google-generativeai`, and not Google
ADK, since Part 2's event-driven orchestration already replaces what ADK's
own agent loop would provide), `websockets` 16.1 (via
`uvicorn[standard]`), pytest + pytest-asyncio.

**Gemini model:** `gemini-3.5-flash`, configurable via `GEMINI_MODEL`.
**Not verified against a live `models.list()` call** — this development
environment never had a `GEMINI_API_KEY` configured. Every test and every
manual/browser verification in this repo used `StubGeminiClient`
(`backend/agents/llm_client.py`) with deterministic canned responses. If
the real identifier differs, it's a one-line `.env` change — nothing else
hardcodes the model name.

**Frontend:** React 19, TypeScript, Vite 8, Tailwind CSS v4 (via
`@tailwindcss/vite`), react-router-dom v7, Vitest + Testing Library.

**Deployment:** Docker (multi-stage builds for both services), Google
Cloud Run (config-ready — see below), Firestore/Pub/Sub stubs for a
future cloud-mode implementation (**not** wired to real GCP services yet
— see Known Limitations).

## Local setup

```bash
git clone <this repo> && cd govflow

# --- Backend ---
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # optionally set GEMINI_API_KEY

# --- Frontend ---
cd frontend
npm install
cp .env.example .env
cd ..
```

## Environment variables

**Backend** (`.env`, see `.env.example`):

| Variable | Required? | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | Optional | — | Without it, agents use a stub client and LLM-backed agents raise `LLMClientError` if triggered; the server still boots and every non-LLM route works. |
| `GEMINI_MODEL` | Optional | `gemini-3.5-flash` | Model string passed to `google-genai`. |
| `EVENT_BUS_MODE` | Optional | `local` | `local` (`InProcessEventBus`) or `pubsub` (stub — raises `NotImplementedError`). |
| `PERSISTENCE_MODE` | Optional | `local` | `local` (SQLite) or `firestore` (stub — raises `NotImplementedError`). |
| `PORT` | Optional | `8000` | Backend listen port. |
| `STATUS_POLL_INTERVAL_SECONDS` | Optional | `2` | `StatusMonitorAgent` polling cadence — also the demo's visible pacing. |
| `STATUS_MAX_POLLS` | Optional | `10` | Poll attempts before giving up on an application. |
| `MAX_TOOL_CALLS_PER_MINUTE` | Optional | `30` | Per-workflow tool-call rate limit (external mock-API tools only). |
| `API_RATE_LIMIT_PER_MINUTE` | Optional | `10` | Per-IP limit on `POST /api/workflows` and `POST /api/demo/run`. |
| `API_KEY_REQUIRED` | Optional | `false` | Set `true` to require `X-API-Key` on write routes. |
| `API_KEY` | Required if above is `true` | — | The expected key value. |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`, `FIRESTORE_DATABASE`, `PUBSUB_TOPIC` | Required only for cloud mode | — | See Google Cloud deployment. |

**Frontend** (`frontend/.env`, see `frontend/.env.example`):

| Variable | Required? | Default | Purpose |
|---|---|---|---|
| `VITE_API_BASE_URL` | Optional | `http://localhost:8000` | REST API origin. |
| `VITE_WS_BASE_URL` | Optional | `ws://localhost:8000` | WebSocket origin. |
| `VITE_API_KEY` | Only if backend has `API_KEY_REQUIRED=true` | — | Sent as `X-API-Key` on write requests. |

## Running the backend

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
pytest -v   # 87 tests
```

## Running the frontend

```bash
cd frontend
npm run dev      # http://localhost:5173
npm test         # 10 tests (Vitest)
npm run build    # production build
```

## Running the demo

1. Start the backend, then the frontend (above), both pointed at each
   other via the default `.env` values.
2. Open `http://localhost:5173`.
3. Click **▶ Run Demo** on Command Center (the "Clean approval" scenario
   is selected by default).
4. Watch, live, with no page refresh: the interpreted goal appears →
   status badge moves `RUNNING` → the Workflow Graph populates and nodes
   turn green in dependency order → the activity feed scrolls with real
   agent entries → Agent Registry statuses flip `idle`/`running` →
   Application Tracker fills in as each service is submitted and
   approved → Audit Trail fills in → final state `COMPLETED`.
5. To see autonomous failure handling: select **Missing documents** or
   **Rejected** before clicking Run Demo. The workflow gates to
   `WAITING_FOR_USER` / `BLOCKED`, a **Human approval required** banner
   appears on Command Center with the real reason from the backend, and
   **Retry step** / **Abandon step** exercise the resume mechanism
   (`POST /api/workflows/{id}/events`).

This was verified in a real headless-Chromium browser session against
both servers running locally (screenshots captured at each stage); see
"Known limitations" for exactly what that verification did and didn't
cover.

## Google Cloud deployment

**LOCAL MODE** (this repo's default, and all `docker-compose.yml` runs
today) uses `InProcessEventBus` + SQLite — no GCP services involved.
**CLOUD MODE** below is config-ready (env vars, Dockerfiles, Cloud Run
commands) but the `PubSubEventBus` and `Firestore*Repository` classes
remain intentional stubs — see Known Limitations before attempting a real
cloud-mode run.

```bash
# One-time setup
gcloud config set project <YOUR_PROJECT_ID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com

# Backend
gcloud run deploy govflow-backend \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated \
  --min-instances=0 \
  --set-env-vars="EVENT_BUS_MODE=local,PERSISTENCE_MODE=local,GEMINI_API_KEY=<key>,GEMINI_MODEL=gemini-3.5-flash" \
  --port=8000

# Frontend (build-time API URL must point at the backend's Cloud Run URL)
BACKEND_URL=$(gcloud run services describe govflow-backend --region=us-central1 --format='value(status.url)')
gcloud run deploy govflow-frontend \
  --source=./frontend \
  --region=us-central1 \
  --allow-unauthenticated \
  --min-instances=0 \
  --set-build-env-vars="VITE_API_BASE_URL=${BACKEND_URL},VITE_WS_BASE_URL=${BACKEND_URL/https/wss}" \
  --port=8080
```

`--min-instances=0` on both services means they scale to zero (and cost
nothing) when idle, per the hackathon's cost guidance.

For true cloud mode (`EVENT_BUS_MODE=pubsub`, `PERSISTENCE_MODE=firestore`),
also set `GOOGLE_CLOUD_PROJECT`, `FIRESTORE_DATABASE`, `PUBSUB_TOPIC`, and
`GOOGLE_APPLICATION_CREDENTIALS` (or rely on the Cloud Run service
identity's default credentials) — **but see Known Limitations: this path
is not implemented yet**, so `EVENT_BUS_MODE=local` /
`PERSISTENCE_MODE=local` is what the deploy command above actually uses,
even running on Cloud Run.

## Security

- **Input validation**: every tool has a strict Pydantic input schema
  (`backend/tools/schemas.py`); `invoke_tool` (`backend/tools/registry.py`)
  rejects a malformed payload before it ever reaches a tool body. Every
  REST request body is a Pydantic model too (`backend/api/schemas.py`) —
  FastAPI 422s automatically on a shape mismatch.
- **Tool allowlisting**: agents never execute arbitrary code or construct
  ad-hoc API calls — only registered tools from a fixed allowlist
  (`backend/tools/registry.py`), each with a schema-validated output too.
- **Structured outputs**: every Gemini call requests JSON-schema-constrained
  output (`backend/agents/llm_client.py: GeminiClient.generate_structured`)
  and validates the result against a Pydantic model — no agent ever acts
  on raw unstructured text.
- **Rate limiting**: a per-workflow limiter on external mock-API tool
  calls (`backend/tools/rate_limiter.py`, exempting internal bookkeeping
  tools so `AuditAgent`'s bus-wide logging can't trip it) and a separate
  per-IP limiter on the two workflow-creating REST routes
  (`backend/api/rate_limit.py`).
- **Auth placeholder**: `X-API-Key` header check on write routes
  (`backend/api/auth.py`), disabled by default, a config flip to enable.
- **Prompt-injection resistance**: any user-provided or RAG-retrieved text
  is wrapped in a clearly delimited "this is data, not instructions" block
  (`backend/tools/security.py: wrap_untrusted`) before reaching a Gemini
  prompt; a heuristic flags likely injection attempts into the audit trail
  for visibility (`looks_like_injection_attempt`). The structural defense
  is what actually matters, though: even a successful injection can't make
  an agent act outside its tool contract.
- **Audit logging**: every agent decision is recorded via the
  `append_audit_entry` tool, *and* `AuditAgent` independently records every
  event that crosses the bus (`backend/agents/audit.py`) as a safety net —
  the audit trail can't go silently incomplete just because one agent
  forgot to log.
- **Human approval gates**: `WorkflowEngine.block_step` / `block_workflow`
  (`backend/workflows/engine.py`) pause autonomous progression on a
  rejection or an ineligible/needs-information finding — never on routine
  steps — until an explicit `WORKFLOW_RESUMED` event is published.
- **Error handling**: a global FastAPI exception handler
  (`backend/main.py`) logs the full traceback server-side and returns a
  generic message — no stack trace ever reaches the client.

## Future integration with real government APIs

`mock_services/client.py` defines a `GovernmentAPIClient` `Protocol` that
`MockGovernmentAPIClient` implements; every tool in
`backend/tools/government_tools.py` calls the client through that
protocol, never the mock class directly. A real integration only needs to
implement the same five methods
(`submit_business_registration`/`submit_tax_registration`/
`submit_food_license`/`submit_local_approval`/`get_application_status`)
against real government endpoints and be swapped in — no agent, tool
schema, or route changes required. The `MOCK_DATA: true` flag every mock
response carries would simply disappear from real responses, and the
frontend's `MockDataBadge` component would stop rendering wherever that
flag is absent.

## Known limitations

- **Cloud mode is config-ready, not deployment-tested.**
  `PubSubEventBus` (`backend/events/bus.py`) and
  `Firestore{Workflow,Event,Audit,Notification}Repository`
  (`backend/services/firestore_repo.py`) are intentional stubs that raise
  `NotImplementedError` with a clear message — selecting
  `EVENT_BUS_MODE=pubsub` or `PERSISTENCE_MODE=firestore` fails loudly,
  never silently no-ops. Implementing and testing them against real GCP
  services is explicit future work, not something this repo claims to
  have already done.
- **`GEMINI_MODEL` is unverified against a live API** — no
  `GEMINI_API_KEY` was ever available in this development environment.
  All demo/test verification used `StubGeminiClient`.
- **In-memory `WorkflowGraph`.** `WorkflowEngine` keeps each workflow's
  DAG in a process-local dict — correct for a single-instance demo, does
  not survive a restart or scale horizontally without a shared store.
- **`POST /api/workflows` / `POST /api/demo/run` return only a
  `workflow_id`**, not a full `Workflow` object — no row exists yet at
  that point (`WorkflowPlannerAgent` creates it a few agent-hops later).
  `GET /api/workflows/{id}` may briefly 404 right after a POST; the
  frontend relies on the WebSocket connection (usable immediately) rather
  than polling.
- **`ConnectionManager` (WebSocket) state is in-process only** — no
  Redis/shared broker — fine for one backend instance, would need one to
  scale beyond that.
- **Browser verification used a headless Chromium session** (this sandbox
  has no internet access to download Playwright's bundled browser, so the
  system-installed Chrome was used directly) driving the dev server via
  `localhost` — confirmed the full demo (clean completion, "rejected"
  failure path, HITL banner, resume-to-FAILED) with zero console errors,
  using `StubGeminiClient` since no real `GEMINI_API_KEY` was available.
  Not tested against a real Gemini key, a production build served from
  Cloud Run, or a second concurrent viewer.
- **`workflow.applications[].status` is written once and never updated**
  by the backend (only events change) — the frontend's Application
  Tracker deliberately derives live status from
  `APPLICATION_STATUS_CHANGED`/`APPLICATION_APPROVED`/`APPLICATION_REJECTED`/
  `DOCUMENT_MISSING` events instead of trusting that field; a future
  backend pass could update the stored record too, but the current design
  keeps step-status ownership entirely with `WorkflowEngine`/`WorkflowGraph`.
- **Mock government API state is process-local and in-memory** — resets
  on backend restart. Intentional: no real government integration exists
  or is implied anywhere in this repo.

## What a judge should click

1. Open the dashboard, land on **Command Center**.
2. Click **▶ Run Demo** (default "Clean approval" scenario).
3. Watch the goal, status badge, and progress bar update live — no
   refresh.
4. Click **Workflow Graph** in the sidebar mid-run to watch nodes turn
   from gray/blue to green in real dependency order.
5. Click **Agent Registry** to see all 10 agents' real, live status.
6. Wait for `COMPLETED`, then check **Application Tracker** (4 approved
   mock applications) and **Audit Trail** (the full decision-by-decision
   record, ~80 entries).
7. Back on Command Center, select **Rejected** and click **▶ Run Demo**
   again — watch it gate to `BLOCKED` with a **Human approval required**
   banner giving the real rejection reason, then click **Abandon step**
   and watch it resolve to `FAILED` live.
