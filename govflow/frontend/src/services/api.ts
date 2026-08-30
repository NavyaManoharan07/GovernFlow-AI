/**
 * Typed fetch wrappers for every real REST route backend/api/routes.py
 * exposes. No fabricated data anywhere here -- every function is a thin,
 * typed wrapper around an actual HTTP call.
 */
import { API_BASE_URL, API_KEY } from './env'
import type {
  AgentInfo,
  ApiErrorBody,
  AuditLogEntry,
  CreateWorkflowRequest,
  DemoScenario,
  ManualEventRequest,
  ServiceInfo,
  Workflow,
  WorkflowAcceptedResponse,
  WorkflowEvent,
  WorkflowGraphResponse,
} from '../types/api'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown) {
    const detail =
      typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as ApiErrorBody).detail)
        : String(body)
    super(`API error ${status}: ${detail}`)
    this.status = status
    this.body = body
  }
}

function authHeaders(): HeadersInit {
  return API_KEY ? { 'X-API-Key': API_KEY } : {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
  })

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = await response.text().catch(() => null)
    }
    throw new ApiError(response.status, body)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function getHealth(): Promise<{ status: string; service: string }> {
  return request('/health')
}

export async function createWorkflow(body: CreateWorkflowRequest): Promise<WorkflowAcceptedResponse> {
  return request('/api/workflows', { method: 'POST', body: JSON.stringify(body) })
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  return request(`/api/workflows/${encodeURIComponent(workflowId)}`)
}

export async function getWorkflowGraph(workflowId: string): Promise<WorkflowGraphResponse> {
  return request(`/api/workflows/${encodeURIComponent(workflowId)}/graph`)
}

export async function getWorkflowEvents(workflowId: string): Promise<WorkflowEvent[]> {
  return request(`/api/workflows/${encodeURIComponent(workflowId)}/events`)
}

export async function getWorkflowAudit(workflowId: string): Promise<AuditLogEntry[]> {
  return request(`/api/workflows/${encodeURIComponent(workflowId)}/audit`)
}

export async function publishManualEvent(
  workflowId: string,
  body: ManualEventRequest,
): Promise<WorkflowEvent> {
  return request(`/api/workflows/${encodeURIComponent(workflowId)}/events`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function resumeWorkflow(
  workflowId: string,
  stepId: string | null,
  action: 'retry' | 'abandon',
): Promise<WorkflowEvent> {
  return publishManualEvent(workflowId, {
    event_type: 'WORKFLOW_RESUMED',
    payload: { step_id: stepId, action },
  })
}

export async function listAgents(): Promise<AgentInfo[]> {
  return request('/api/agents')
}

export async function listServices(): Promise<ServiceInfo[]> {
  return request('/api/services')
}

export async function runDemo(
  scenario: DemoScenario = 'clean',
  userId = 'demo-user',
): Promise<WorkflowAcceptedResponse> {
  const params = new URLSearchParams({ scenario, user_id: userId })
  return request(`/api/demo/run?${params.toString()}`, { method: 'POST' })
}
