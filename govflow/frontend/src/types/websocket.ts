/**
 * WebSocket message envelope types, matching backend/api/websocket.py's
 * _envelope() + the four _*_payload() builders exactly. Every message on
 * WS /ws/workflows/{id} is { type, timestamp, payload }; route on `type`
 * -- payload shape differs per type.
 */
import type { EventType, StepStatus, WorkflowStatus } from './api'

export interface WsEventPayload {
  event_id: string
  workflow_id: string
  event_type: EventType
  source_agent: string
  payload: Record<string, unknown>
  timestamp: string
}

export interface WsAgentActivityPayload {
  workflow_id: string
  agent: string
  action: string
  timestamp: string
}

export interface WsAuditPayload {
  workflow_id: string
  timestamp: string
  event: string
  agent: string
  decision: string
  source: string
  tool: string | null
  api_result: Record<string, unknown> | null
}

export interface WsStateChangePayload {
  workflow_id: string
  status: WorkflowStatus
  current_step: string | null
  completed_steps: string[]
  pending_steps: string[]
  failed_steps: string[]
}

export type WsMessage =
  | { type: 'event'; timestamp: string; payload: WsEventPayload }
  | { type: 'agent_activity'; timestamp: string; payload: WsAgentActivityPayload }
  | { type: 'audit'; timestamp: string; payload: WsAuditPayload }
  | { type: 'state_change'; timestamp: string; payload: WsStateChangePayload }

export const TERMINAL_STATUSES: WorkflowStatus[] = ['COMPLETED', 'FAILED', 'BLOCKED', 'WAITING_FOR_USER']
export const GATED_STATUSES: WorkflowStatus[] = ['WAITING_FOR_USER', 'BLOCKED']

// Re-exported for components that only need the step-status union.
export type { StepStatus }
