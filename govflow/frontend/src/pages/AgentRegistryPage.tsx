import { AgentRegistryTable } from '../components/AgentRegistryTable'
import { ErrorState, LoadingState } from '../components/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useAgents } from '../hooks/useAgents'
import { useWorkflowStream } from '../hooks/useWorkflowStream'

export function AgentRegistryPage() {
  const { activeWorkflowId } = useActiveWorkflow()
  // If a workflow is active, its live activity stream doubles as a
  // "something changed, refresh now" signal instead of waiting for the
  // next 3s poll -- the agent registry itself has no dedicated push
  // channel (see hooks/useAgents.ts).
  const stream = useWorkflowStream(activeWorkflowId)
  const { agents, loading, error } = useAgents(stream.agentActivity.length)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Agent Registry"
        subtitle="Live status for all agents, from GET /api/agents — updates as they actually run."
      />

      {error ? <ErrorState message={error} /> : null}
      {loading && agents.length === 0 ? (
        <LoadingState label="Loading agents…" />
      ) : error ? null : (
        <AgentRegistryTable agents={agents} />
      )}
    </div>
  )
}
