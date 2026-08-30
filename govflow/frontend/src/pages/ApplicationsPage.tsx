import { useEffect, useState } from 'react'
import { ApplicationTracker } from '../components/ApplicationTracker'
import { EmptyState } from '../components/EmptyState'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useWorkflowStream } from '../hooks/useWorkflowStream'
import { getWorkflow } from '../services/api'
import type { ApplicationRecord } from '../types/api'

export function ApplicationsPage() {
  const { activeWorkflowId } = useActiveWorkflow()
  const stream = useWorkflowStream(activeWorkflowId)
  const [applications, setApplications] = useState<ApplicationRecord[]>([])

  // workflow.applications isn't pushed over the socket (only aggregate
  // status is, via state_change) -- refetch it whenever the workflow's
  // status changes, same pattern as the graph refetch in useWorkflowStream.
  useEffect(() => {
    if (!activeWorkflowId) {
      setApplications([])
      return
    }
    let cancelled = false
    getWorkflow(activeWorkflowId)
      .then((workflow) => {
        if (!cancelled) setApplications(workflow.applications)
      })
      .catch(() => {
        /* transient fetch failure -- keep last known applications */
      })
    return () => {
      cancelled = true
    }
  }, [activeWorkflowId, stream.status])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--gf-text)]">Application Tracker</h1>
        <p className="mt-1 text-sm text-[var(--gf-text-dim)]">
          Every application submitted to a mock government service, with live status.
        </p>
      </div>

      {!activeWorkflowId ? (
        <EmptyState
          title="No active workflow"
          description="Start one from Command Center or run the demo to see applications here."
        />
      ) : (
        <ApplicationTracker applications={applications} events={stream.events} />
      )}
    </div>
  )
}
