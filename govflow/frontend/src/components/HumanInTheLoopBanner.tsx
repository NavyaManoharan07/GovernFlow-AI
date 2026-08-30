import { useMemo, useState } from 'react'
import { ApiError, resumeWorkflow } from '../services/api'
import type { WorkflowStatus } from '../types/api'
import type { WsEventPayload } from '../types/websocket'

const GATED_STATUSES: WorkflowStatus[] = ['WAITING_FOR_USER', 'BLOCKED']

function findLatestUserActionRequired(events: WsEventPayload[]): WsEventPayload | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].event_type === 'USER_ACTION_REQUIRED') {
      return events[i]
    }
  }
  return null
}

/** Only rendered for genuinely gated states (WAITING_FOR_USER / BLOCKED)
 * -- routine steps never show this, since those statuses only ever come
 * from WorkflowEngine.block_step/block_workflow, which the backend
 * reserves for a rejection, a missing-documents finding, or an
 * ineligible/needs-information eligibility result (see
 * backend/workflows/engine.py's human-in-the-loop gate). */
export function HumanInTheLoopBanner({
  status,
  workflowId,
  events,
  onResumed,
}: {
  status: WorkflowStatus | null
  workflowId: string
  events: WsEventPayload[]
  onResumed?: () => void
}) {
  const [submitting, setSubmitting] = useState<'retry' | 'abandon' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const gateEvent = useMemo(() => findLatestUserActionRequired(events), [events])

  if (!status || !GATED_STATUSES.includes(status)) {
    return null
  }

  const reason = typeof gateEvent?.payload.reason === 'string' ? gateEvent.payload.reason : 'Review required.'
  const stepId = typeof gateEvent?.payload.step_id === 'string' ? gateEvent.payload.step_id : null

  async function handleAction(action: 'retry' | 'abandon') {
    setSubmitting(action)
    setError(null)
    try {
      await resumeWorkflow(workflowId, stepId, action)
      onResumed?.()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to resume the workflow')
    } finally {
      setSubmitting(null)
    }
  }

  return (
    <div className="rounded-lg border border-orange-500/40 bg-orange-500/10 p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-lg text-orange-400">⚠</span>
        <div className="flex-1">
          <p className="text-sm font-semibold text-orange-300">Human approval required</p>
          <p className="mt-1 text-sm text-[var(--gf-text-dim)]">{reason}</p>
          {stepId ? (
            <p className="mt-1 text-xs text-[var(--gf-text-faint)]">Affected step: {stepId}</p>
          ) : null}

          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => void handleAction('retry')}
              disabled={submitting !== null}
              className="rounded-md bg-[var(--gf-accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--gf-accent-hover)] disabled:opacity-50"
            >
              {submitting === 'retry' ? 'Retrying…' : 'Retry step'}
            </button>
            <button
              type="button"
              onClick={() => void handleAction('abandon')}
              disabled={submitting !== null}
              className="rounded-md border border-[var(--gf-border)] px-3 py-1.5 text-xs font-medium text-[var(--gf-text-dim)] transition-colors hover:bg-white/5 disabled:opacity-50"
            >
              {submitting === 'abandon' ? 'Abandoning…' : 'Abandon step'}
            </button>
          </div>

          {error ? <p className="mt-2 text-xs text-red-400">{error}</p> : null}
        </div>
      </div>
    </div>
  )
}
