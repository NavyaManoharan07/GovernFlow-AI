import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { WorkflowStatusBadge } from '../components/StatusBadge'
import { Button } from '../components/ui/Button'
import { Card, CardHeaderBar } from '../components/ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../components/EmptyState'
import { PageHeader, SectionLabel } from '../components/ui/PageHeader'
import { TABLE_BODY_DIVIDER, TABLE_HEAD_ROW, TABLE_TD, TABLE_TH } from '../components/ui/table'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useDashboardSummary } from '../hooks/useDashboardSummary'
import { ApiError, runDemo } from '../services/api'
import type { WorkflowStatus } from '../types/api'

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function StatCard({ label, value, colorVar }: { label: string; value: number; colorVar?: string }) {
  return (
    <Card padded className="flex flex-col gap-1">
      <SectionLabel>{label}</SectionLabel>
      <p className="text-3xl font-semibold" style={{ color: colorVar ? `var(${colorVar})` : 'var(--gf-text)' }}>
        {value}
      </p>
    </Card>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const { setActiveWorkflowId } = useActiveWorkflow()
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)

  // Refetches immediately once `refreshTick` changes (right after Run Demo
  // is triggered), on top of the hook's own periodic polling -- see
  // hooks/useDashboardSummary.ts for why polling (not a global WS
  // channel) is what actually keeps this page live.
  const [refreshTick, setRefreshTick] = useState(0)
  const { summary, loading, error } = useDashboardSummary(refreshTick)

  async function handleRunDemo() {
    setStarting(true)
    setStartError(null)
    try {
      const response = await runDemo('clean')
      setActiveWorkflowId(response.workflow_id)
      setRefreshTick((t) => t + 1)
      navigate('/command-center')
    } catch (err) {
      setStartError(err instanceof ApiError ? err.message : 'Failed to start the demo')
    } finally {
      setStarting(false)
    }
  }

  function openWorkflow(workflowId: string) {
    setActiveWorkflowId(workflowId)
    navigate('/command-center')
  }

  const byStatus = summary?.by_status ?? {}
  const blockedOrWaiting = (byStatus.BLOCKED ?? 0) + (byStatus.WAITING_FOR_USER ?? 0)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Dashboard"
        subtitle="Overview across every workflow GovFlow AI has run — all numbers computed live from persisted data."
      />

      <Card padded className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-[var(--gf-text)]">New here?</p>
          <p className="mt-1 text-sm text-[var(--gf-text-dim)]">
            Run the deterministic judging demo to watch the full autonomous agent chain complete a real workflow.
          </p>
          {startError ? <p className="mt-2 text-xs text-red-400">{startError}</p> : null}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="ghost" onClick={() => navigate('/command-center')}>
            Open Command Center
          </Button>
          <Button variant="primary" onClick={() => void handleRunDemo()} disabled={starting}>
            {starting ? 'Starting demo…' : '▶ Run Demo'}
          </Button>
        </div>
      </Card>

      {error ? <ErrorState message={error} /> : null}
      {loading && !summary ? <LoadingState label="Loading dashboard…" /> : null}

      {summary ? (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total workflows" value={summary.total_workflows} />
            <StatCard label="Completed" value={byStatus.COMPLETED ?? 0} colorVar="--gf-status-completed" />
            <StatCard label="Running" value={byStatus.RUNNING ?? 0} colorVar="--gf-status-running" />
            <StatCard label="Blocked / waiting" value={blockedOrWaiting} colorVar="--gf-status-blocked" />
            <StatCard label="Failed" value={byStatus.FAILED ?? 0} colorVar="--gf-status-failed" />
          </div>

          <div>
            <div className="mb-2">
              <SectionLabel>Recent workflows</SectionLabel>
            </div>

            {summary.total_workflows === 0 ? (
              <EmptyState
                title="No workflows yet"
                description="Run the demo above, or start one from Command Center, to see it here."
              />
            ) : (
              <Card className="overflow-hidden">
                <CardHeaderBar
                  left={<SectionLabel>Last {summary.recent_workflows.length} of {summary.total_workflows}</SectionLabel>}
                />
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className={TABLE_HEAD_ROW}>
                      <th className={TABLE_TH}>Goal</th>
                      <th className={TABLE_TH}>Status</th>
                      <th className={TABLE_TH}>Last updated</th>
                      <th className={TABLE_TH} />
                    </tr>
                  </thead>
                  <tbody className={TABLE_BODY_DIVIDER}>
                    {summary.recent_workflows.map((w) => (
                      <tr
                        key={w.workflow_id}
                        onClick={() => openWorkflow(w.workflow_id)}
                        className="cursor-pointer transition-colors hover:bg-white/5"
                      >
                        <td className={`${TABLE_TD} max-w-md truncate text-[var(--gf-text)]`} title={w.goal}>
                          {w.goal}
                        </td>
                        <td className={TABLE_TD}>
                          <WorkflowStatusBadge status={w.status as WorkflowStatus} />
                        </td>
                        <td className={`whitespace-nowrap ${TABLE_TD} font-mono text-xs text-[var(--gf-text-faint)]`}>
                          {formatTime(w.updated_at)}
                        </td>
                        <td className={`whitespace-nowrap ${TABLE_TD} text-right`}>
                          <span className="text-xs font-medium text-[var(--gf-accent)] hover:underline">View →</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-2">
            <Card padded className="flex flex-col gap-1">
              <SectionLabel>Applications submitted (all workflows)</SectionLabel>
              <p className="text-xl font-semibold text-[var(--gf-text)]">{summary.total_applications_submitted}</p>
            </Card>
            <Card padded className="flex flex-col gap-1">
              <SectionLabel>Audit entries recorded (all workflows)</SectionLabel>
              <p className="text-xl font-semibold text-[var(--gf-text)]">{summary.total_audit_entries}</p>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  )
}
