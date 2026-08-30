import { useEffect, useState } from 'react'
import { AuditTrailTable } from '../components/AuditTrailTable'
import { EmptyState } from '../components/EmptyState'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useWorkflowStream } from '../hooks/useWorkflowStream'
import { getWorkflowAudit } from '../services/api'
import type { AuditLogEntry } from '../types/api'

export function AuditPage() {
  const { activeWorkflowId } = useActiveWorkflow()
  const stream = useWorkflowStream(activeWorkflowId)
  const [restAudit, setRestAudit] = useState<AuditLogEntry[]>([])

  // Initial fetch via REST for an immediate paint. The WebSocket's
  // snapshot replay (see useWorkflowStream / backend/api/websocket.py)
  // sends the SAME full history plus live updates, so once it has data
  // it fully supersedes this one-time fetch -- no merge/dedupe needed.
  useEffect(() => {
    if (!activeWorkflowId) {
      setRestAudit([])
      return
    }
    let cancelled = false
    getWorkflowAudit(activeWorkflowId)
      .then((entries) => {
        if (!cancelled) setRestAudit(entries)
      })
      .catch(() => {
        /* WS stream will still populate the table once connected */
      })
    return () => {
      cancelled = true
    }
  }, [activeWorkflowId])

  const entries = stream.audit.length > 0 ? stream.audit : restAudit

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--gf-text)]">Audit Trail</h1>
        <p className="mt-1 text-sm text-[var(--gf-text-dim)]">
          Every decision, tool call, and state transition — the full accountability record.
        </p>
      </div>

      {!activeWorkflowId ? (
        <EmptyState
          title="No active workflow"
          description="Start one from Command Center or run the demo to see the audit trail here."
        />
      ) : (
        <AuditTrailTable entries={entries} />
      )}
    </div>
  )
}
