import { useEffect, useMemo, useRef, useState } from 'react'
import { getWorkflowGraph } from '../services/api'
import { WorkflowSocket } from '../services/websocket'
import type { WorkflowStatus, WorkflowStep } from '../types/api'
import type { WsAgentActivityPayload, WsAuditPayload, WsEventPayload, WsMessage } from '../types/websocket'

const MAX_FEED_ROWS = 200

export interface WorkflowStreamState {
  connected: boolean
  /** True once at least one message has arrived (snapshot or live) --
   * distinguishes "still loading initial history" from "confirmed empty /
   * streaming live" for loading-state UI. */
  hasReceivedData: boolean
  status: WorkflowStatus | null
  currentStep: string | null
  completedSteps: string[]
  pendingSteps: string[]
  failedSteps: string[]
  graphSteps: WorkflowStep[]
  graphAvailable: boolean
  events: WsEventPayload[]
  agentActivity: WsAgentActivityPayload[]
  audit: WsAuditPayload[]
}

const EMPTY_STATE: WorkflowStreamState = {
  connected: false,
  hasReceivedData: false,
  status: null,
  currentStep: null,
  completedSteps: [],
  pendingSteps: [],
  failedSteps: [],
  graphSteps: [],
  graphAvailable: false,
  events: [],
  agentActivity: [],
  audit: [],
}

function capPush<T>(list: T[], item: T, max: number): T[] {
  const next = [...list, item]
  return next.length > max ? next.slice(next.length - max) : next
}

/**
 * Subscribes to WS /ws/workflows/{workflowId} and accumulates its four
 * message types into a single, render-friendly state object. Pass
 * workflowId=null to stay idle (used before any workflow has been
 * started). The graph (steps + depends_on edges) isn't pushed over the
 * socket -- only aggregate status is -- so this refetches
 * GET /api/workflows/{id}/graph via REST whenever a state_change arrives.
 */
export function useWorkflowStream(workflowId: string | null): WorkflowStreamState {
  const [state, setState] = useState<WorkflowStreamState>(EMPTY_STATE)
  const socketRef = useRef<WorkflowSocket | null>(null)

  useEffect(() => {
    setState(EMPTY_STATE)
    if (!workflowId) {
      return
    }

    const socket = new WorkflowSocket(workflowId)
    socketRef.current = socket

    const unsubscribeConnection = socket.onConnectionChange((connected) => {
      setState((prev) => ({ ...prev, connected }))
    })

    const unsubscribeMessage = socket.onMessage((message: WsMessage) => {
      setState((prev) => {
        const next: WorkflowStreamState = { ...prev, hasReceivedData: true }
        switch (message.type) {
          case 'event':
            next.events = capPush(prev.events, message.payload, MAX_FEED_ROWS)
            return next
          case 'agent_activity':
            next.agentActivity = capPush(prev.agentActivity, message.payload, MAX_FEED_ROWS)
            return next
          case 'audit':
            next.audit = capPush(prev.audit, message.payload, MAX_FEED_ROWS)
            return next
          case 'state_change':
            next.status = message.payload.status
            next.currentStep = message.payload.current_step
            next.completedSteps = message.payload.completed_steps
            next.pendingSteps = message.payload.pending_steps
            next.failedSteps = message.payload.failed_steps
            return next
          default:
            return prev
        }
      })

      if (message.type === 'state_change') {
        getWorkflowGraph(workflowId)
          .then((graph) => {
            setState((prev) => ({
              ...prev,
              graphSteps: graph.steps,
              graphAvailable: graph.available,
            }))
          })
          .catch(() => {
            // Graph fetch failing shouldn't break the live stream -- the
            // rest of the UI still reflects real state via state_change.
          })
      }
    })

    socket.connect()

    return () => {
      unsubscribeMessage()
      unsubscribeConnection()
      socket.disconnect()
      socketRef.current = null
    }
  }, [workflowId])

  return state
}

/** Convenience: finds the most recent event of a given type, if any --
 * e.g. the GOAL_ANALYZED payload for showing the interpreted goal, or the
 * USER_ACTION_REQUIRED payload for the human-in-the-loop banner. */
export function useLatestEventPayload(
  events: WsEventPayload[],
  eventType: string,
): Record<string, unknown> | null {
  return useMemo(() => {
    for (let i = events.length - 1; i >= 0; i -= 1) {
      if (events[i].event_type === eventType) {
        return events[i].payload
      }
    }
    return null
  }, [events, eventType])
}
