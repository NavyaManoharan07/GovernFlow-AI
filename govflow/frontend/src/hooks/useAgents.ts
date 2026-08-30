import { useCallback, useEffect, useRef, useState } from 'react'
import { listAgents } from '../services/api'
import type { AgentInfo } from '../types/api'

const POLL_INTERVAL_MS = 3000

interface UseAgentsResult {
  agents: AgentInfo[]
  loading: boolean
  error: string | null
}

/**
 * GET /api/agents on mount, then polls every 3s so the registry reflects
 * real agent activity as a workflow runs (the backend has no per-agent
 * push channel -- agent status changes are visible through the "event"/
 * "agent_activity" WS messages already, but the registry's aggregate
 * status/last_action is only available via this REST route). Never
 * renders a hardcoded agent list -- whatever the API returns is what's
 * shown, so it stays correct if the backend's agent roster ever changes.
 */
export function useAgents(refreshSignal?: unknown): UseAgentsResult {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const fetchAgents = useCallback(async () => {
    try {
      const result = await listAgents()
      if (mountedRef.current) {
        setAgents(result)
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to load agents')
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void fetchAgents()
    const interval = window.setInterval(() => void fetchAgents(), POLL_INTERVAL_MS)
    return () => {
      mountedRef.current = false
      window.clearInterval(interval)
    }
  }, [fetchAgents])

  // Also refresh immediately when the caller signals a relevant WS event
  // (e.g. a new agent_activity message), instead of waiting for the poll.
  useEffect(() => {
    if (refreshSignal !== undefined) {
      void fetchAgents()
    }
  }, [refreshSignal, fetchAgents])

  return { agents, loading, error }
}
