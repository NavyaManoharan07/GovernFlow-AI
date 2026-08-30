/**
 * TypeScript types matching the REAL backend Pydantic models, hand-written
 * from the actual schemas in govflow/backend/models/*.py and
 * govflow/backend/api/{routes,schemas}.py, and cross-checked against real
 * example payloads captured from a live backend run (see
 * govflow/docs/ for the captured examples) -- not guessed.
 */

// ---------------------------------------------------------------------------
// Enums (backend/models/enums.py)
// ---------------------------------------------------------------------------

export type WorkflowStatus =
  | 'RUNNING'
  | 'WAITING_FOR_USER'
  | 'BLOCKED'
  | 'COMPLETED'
  | 'FAILED'

export type StepStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'WAITING'
  | 'BLOCKED'
  | 'FAILED'

export type EventType =
  | 'USER_REQUEST_CREATED'
  | 'GOAL_ANALYZED'
  | 'WORKFLOW_CREATED'
  | 'REQUIREMENTS_IDENTIFIED'
  | 'ELIGIBILITY_CHECKED'
  | 'DOCUMENTS_VALIDATED'
  | 'APPLICATION_READY'
  | 'APPLICATION_SUBMITTED'
  | 'APPLICATION_STATUS_CHANGED'
  | 'DOCUMENT_MISSING'
  | 'APPLICATION_APPROVED'
  | 'APPLICATION_REJECTED'
  | 'NEXT_ACTION_TRIGGERED'
  | 'USER_ACTION_REQUIRED'
  | 'WORKFLOW_COMPLETED'
  | 'WORKFLOW_FAILED'
  | 'WORKFLOW_RESUMED'

export type AgentStatus = 'idle' | 'running' | 'error'

// ---------------------------------------------------------------------------
// Core resources
// ---------------------------------------------------------------------------

/** One submitted mock-government application, as stored in Workflow.applications[] */
export interface ApplicationRecord {
  application_id: string
  service: string // hyphenated, e.g. "business-registration"
  department: string
  status: string // "SUBMITTED" | "PENDING" | "APPROVED" | "REJECTED" | "DOCUMENT_MISSING" | ...
  scenario: string
  mock_data: boolean
  step_id: string // underscored, e.g. "business_registration"
}

/** GET /api/workflows/{id} -- backend/models/workflow.py: Workflow */
export interface Workflow {
  workflow_id: string
  user_id: string
  goal: string
  status: WorkflowStatus
  current_step: string | null
  completed_steps: string[]
  pending_steps: string[]
  failed_steps: string[]
  required_documents: Record<string, unknown>[]
  applications: ApplicationRecord[]
  events: unknown[] // always [] in practice -- use GET .../events instead
  created_at: string
  updated_at: string
  metadata: Record<string, unknown>
}

/** backend/models/workflow.py: WorkflowStep, as returned by GET .../graph */
export interface WorkflowStep {
  id: string
  name: string
  service: string
  depends_on: string[]
  status: StepStatus
  metadata: Record<string, unknown>
}

/** GET /api/workflows/{id}/graph -- backend/api/schemas.py: WorkflowGraphResponse */
export interface WorkflowGraphResponse {
  workflow_id: string
  available: boolean
  steps: WorkflowStep[]
}

/** GET /api/workflows/{id}/events -- backend/models/event.py: Event */
export interface WorkflowEvent {
  event_id: string
  workflow_id: string
  event_type: EventType
  payload: Record<string, unknown>
  source_agent: string
  timestamp: string
  correlation_id: string | null
}

/** GET /api/workflows/{id}/audit -- backend/models/audit.py: AuditLogEntry */
export interface AuditLogEntry {
  timestamp: string
  workflow_id: string
  event: string
  agent: string
  decision: string
  source: string
  tool: string | null
  api_result: Record<string, unknown> | null
  state_transition: Record<string, unknown> | null
}

/** GET /api/agents -- backend/models/agent.py: AgentInfo */
export interface AgentInfo {
  name: string
  responsibility: string
  status: AgentStatus
  last_action: string | null
  last_active_at: string | null
}

/** GET /api/services -- backend/agents/catalog.py: ServiceInfo */
export interface ServiceInfo {
  service: string
  department: string
  tool_name: string
  description: string
  mock_data: boolean
}

// ---------------------------------------------------------------------------
// Request/response DTOs (backend/api/schemas.py)
// ---------------------------------------------------------------------------

export interface CreateWorkflowRequest {
  user_id: string
  goal: string
}

/** POST /api/workflows and POST /api/demo/run both return this (202) --
 * NOT a full Workflow: no row exists yet at that point (WorkflowPlannerAgent
 * creates it a few hops into the async agent chain). */
export interface WorkflowAcceptedResponse {
  workflow_id: string
  status: 'ACCEPTED'
  user_id: string
  goal: string
  message: string
}

export type DemoScenario = 'clean' | 'document_missing' | 'rejected'

/** The only event type POST /api/workflows/{id}/events accepts. */
export interface WorkflowResumedPayload {
  step_id: string | null
  action: 'retry' | 'abandon'
}

export interface ManualEventRequest {
  event_type: 'WORKFLOW_RESUMED'
  payload: WorkflowResumedPayload
}

export interface ApiErrorBody {
  detail: string | Record<string, unknown>
}
