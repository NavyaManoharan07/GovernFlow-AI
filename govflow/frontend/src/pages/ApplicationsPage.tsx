import { useEffect, useState } from 'react'
import { ApplicationTracker } from '../components/ApplicationTracker'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
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
      <PageHeader
        title="Application Tracker"
        subtitle="Every application submitted to a mock government service, with live status."
      />

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
