import { useCallback, useEffect, useRef, useState } from 'react'
import { getDashboardSummary } from '../services/api'
import type { DashboardSummary } from '../types/api'

const POLL_INTERVAL_MS = 7000

interface UseDashboardSummaryResult {
  summary: DashboardSummary | null
  loading: boolean
  error: string | null
}

/**
 * GET /api/dashboard/summary on mount, then polls every ~7s so the
 * numbers update live during a demo without a manual refresh -- there is
 * no global "anything changed" WebSocket channel (WS /ws/workflows/{id}
 * is scoped to one workflow), so polling is the honest way to keep this
 * page current rather than claiming a push channel that doesn't exist.
 * `refreshSignal` (e.g. the active workflow's live status) lets a caller
 * force an immediate refetch instead of waiting for the next tick, so
 * the dashboard updates promptly right after Run Demo is clicked.
 */
export function useDashboardSummary(refreshSignal?: unknown): UseDashboardSummaryResult {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const fetchSummary = useCallback(async () => {
    try {
      const result = await getDashboardSummary()
      if (mountedRef.current) {
        setSummary(result)
        setError(null)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard summary')
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    void fetchSummary()
    const interval = window.setInterval(() => void fetchSummary(), POLL_INTERVAL_MS)
    return () => {
      mountedRef.current = false
      window.clearInterval(interval)
    }
  }, [fetchSummary])

  useEffect(() => {
    if (refreshSignal !== undefined) {
      void fetchSummary()
    }
  }, [refreshSignal, fetchSummary])

  return { summary, loading, error }
}
