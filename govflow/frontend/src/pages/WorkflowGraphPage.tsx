import { WorkflowGraph } from '../components/WorkflowGraph'
import { WorkflowStatusBadge } from '../components/StatusBadge'
import { EmptyState } from '../components/EmptyState'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useWorkflowStream } from '../hooks/useWorkflowStream'

export function WorkflowGraphPage() {
  const { activeWorkflowId } = useActiveWorkflow()
  const stream = useWorkflowStream(activeWorkflowId)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--gf-text)]">Workflow Graph</h1>
          <p className="mt-1 text-sm text-[var(--gf-text-dim)]">
            The real dependency graph (steps + depends_on edges) for the active workflow.
          </p>
        </div>
        <WorkflowStatusBadge status={stream.status} />
      </div>

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
