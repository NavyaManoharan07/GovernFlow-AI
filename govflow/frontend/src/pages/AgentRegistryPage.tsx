import { AgentRegistryTable } from '../components/AgentRegistryTable'
import { ErrorState, LoadingState } from '../components/EmptyState'
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
      <div>
        <h1 className="text-2xl font-semibold text-[var(--gf-text)]">Agent Registry</h1>
        <p className="mt-1 text-sm text-[var(--gf-text-dim)]">
          Live status for all agents, from GET /api/agents — updates as they actually run.
        </p>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {loading && agents.length === 0 ? <LoadingState label="Loading agents…" /> : null}
      {agents.length > 0 ? <AgentRegistryTable agents={agents} /> : null}
    </div>
  )
}
