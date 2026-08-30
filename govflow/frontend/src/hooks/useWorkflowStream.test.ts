import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useWorkflowStream } from './useWorkflowStream'
import type { WsMessage } from '../types/websocket'

// Capture the onMessage listener the hook registers so the test can push
// real envelope-shaped messages through it, exactly as the real
// WorkflowSocket would after parsing a WS frame.
let capturedListener: ((message: WsMessage) => void) | null = null

vi.mock('../services/websocket', () => {
  // A real `function` (not an arrow function) so `new WorkflowSocket(...)`
  // works -- explicitly returning an object from a constructor function
  // makes `new` yield that object instead of `this`, which is exactly
  // what a mock constructor needs here.
  function WorkflowSocket() {
    return {
      connect: vi.fn(),
      disconnect: vi.fn(),
      onMessage: vi.fn((listener: (message: WsMessage) => void) => {
        capturedListener = listener
        return () => {
          capturedListener = null
        }
      }),
      onConnectionChange: vi.fn(() => () => {}),
    }
  }
  return { WorkflowSocket }
})

vi.mock('../services/api', () => ({
  getWorkflowGraph: vi.fn().mockResolvedValue({ workflow_id: 'wf-1', available: true, steps: [] }),
}))

beforeEach(() => {
  capturedListener = null
})

function emit(message: WsMessage) {
  act(() => {
    capturedListener?.(message)
  })
}

describe('useWorkflowStream message routing', () => {
  it('routes an "event" message into the events list', () => {
    const { result } = renderHook(() => useWorkflowStream('wf-1'))

    emit({
      type: 'event',
      timestamp: '2026-01-01T00:00:00Z',
      payload: {
        event_id: 'e1',
        workflow_id: 'wf-1',
        event_type: 'GOAL_ANALYZED',
        source_agent: 'GoalInterpreterAgent',
        payload: { goal: 'start a business' },
        timestamp: '2026-01-01T00:00:00Z',
      },
    })

    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0].event_type).toBe('GOAL_ANALYZED')
    expect(result.current.agentActivity).toHaveLength(0)
    expect(result.current.audit).toHaveLength(0)
    expect(result.current.hasReceivedData).toBe(true)
  })

  it('routes an "agent_activity" message into agentActivity, not events', () => {
    const { result } = renderHook(() => useWorkflowStream('wf-1'))

    emit({
      type: 'agent_activity',
      timestamp: '2026-01-01T00:00:00Z',
      payload: { workflow_id: 'wf-1', agent: 'RegulationAgent', action: 'REQUIREMENTS_IDENTIFIED', timestamp: '2026-01-01T00:00:00Z' },
    })

    expect(result.current.agentActivity).toHaveLength(1)
    expect(result.current.agentActivity[0].agent).toBe('RegulationAgent')
    expect(result.current.events).toHaveLength(0)
  })

  it('routes an "audit" message into audit', () => {
    const { result } = renderHook(() => useWorkflowStream('wf-1'))

    emit({
      type: 'audit',
      timestamp: '2026-01-01T00:00:00Z',
      payload: {
        workflow_id: 'wf-1',
        timestamp: '2026-01-01T00:00:00Z',
        event: 'GOAL_ANALYZED',
        agent: 'GoalInterpreterAgent',
        decision: 'business_type=food_processing',
        source: 'agent',
        tool: 'gemini:GoalAnalysis',
        api_result: null,
      },
    })

    expect(result.current.audit).toHaveLength(1)
    expect(result.current.audit[0].decision).toContain('food_processing')
  })

  it('routes a "state_change" message into the flat status fields and refetches the graph', async () => {
    const { result } = renderHook(() => useWorkflowStream('wf-1'))

    emit({
      type: 'state_change',
      timestamp: '2026-01-01T00:00:00Z',
      payload: {
        workflow_id: 'wf-1',
        status: 'COMPLETED',
        current_step: null,
        completed_steps: ['business_registration'],
        pending_steps: [],
        failed_steps: [],
      },
    })

    expect(result.current.status).toBe('COMPLETED')
    expect(result.current.completedSteps).toEqual(['business_registration'])

    await waitFor(() => {
      expect(result.current.graphAvailable).toBe(true)
    })
  })
})
