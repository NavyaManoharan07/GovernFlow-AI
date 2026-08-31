import { WorkflowGraph } from '../components/WorkflowGraph'
import { WorkflowStatusBadge } from '../components/StatusBadge'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useWorkflowStream } from '../hooks/useWorkflowStream'

export function WorkflowGraphPage() {
  const { activeWorkflowId } = useActiveWorkflow()
  const stream = useWorkflowStream(activeWorkflowId)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Workflow Graph"
        subtitle="The real dependency graph (steps + depends_on edges) for the active workflow."
        right={<WorkflowStatusBadge status={stream.status} />}
      />

      {!activeWorkflowId ? (
        <EmptyState
          title="No active workflow"
          description="Start one from Command Center or run the demo to see it here."
        />
      ) : (
        <WorkflowGraph steps={stream.graphSteps} available={stream.graphAvailable} />
      )}
    </div>
  )
}
