import { useState } from 'react'
import { LiveActivityFeed } from '../components/LiveActivityFeed'
import { HumanInTheLoopBanner } from '../components/HumanInTheLoopBanner'
import { MockDataBadge } from '../components/MockDataBadge'
import { WorkflowStatusBadge } from '../components/StatusBadge'
import { Button } from '../components/ui/Button'
import { Card, cardClassName } from '../components/ui/Card'
import { ErrorState } from '../components/EmptyState'
import { PageHeader, SectionLabel } from '../components/ui/PageHeader'
import { useActiveWorkflow } from '../context/WorkflowContext'
import { useLatestEventPayload, useWorkflowStream } from '../hooks/useWorkflowStream'
import { ApiError, createWorkflow, runDemo } from '../services/api'
import type { DemoScenario } from '../types/api'

const SCENARIOS: { value: DemoScenario; label: string; description: string }[] = [
  { value: 'clean', label: 'Clean approval', description: 'Every service approves — full autonomous completion.' },
  {
    value: 'document_missing',
    label: 'Missing documents',
    description: 'A service reports missing documents — workflow gates to WAITING_FOR_USER.',
  },
  { value: 'rejected', label: 'Rejected', description: 'A service rejects the application — workflow gates to BLOCKED.' },
]

export function CommandCenter() {
  const { activeWorkflowId, setActiveWorkflowId } = useActiveWorkflow()
  const stream = useWorkflowStream(activeWorkflowId)
  const goalAnalyzed = useLatestEventPayload(stream.events, 'GOAL_ANALYZED')

  const [goal, setGoal] = useState('')
  const [scenario, setScenario] = useState<DemoScenario>('clean')
  const [submitting, setSubmitting] = useState<'goal' | 'demo' | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmitGoal(e: React.FormEvent) {
    e.preventDefault()
    if (!goal.trim()) return
    setSubmitting('goal')
    setError(null)
    try {
      const response = await createWorkflow({ user_id: 'command-center-user', goal })
      setActiveWorkflowId(response.workflow_id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start workflow')
    } finally {
      setSubmitting(null)
    }
  }

  async function handleRunDemo() {
    setSubmitting('demo')
    setError(null)
    try {
      const response = await runDemo(scenario)
      setActiveWorkflowId(response.workflow_id)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to start the demo')
    } finally {
      setSubmitting(null)
    }
  }

  const totalSteps = stream.graphSteps.length
  const completedCount = stream.completedSteps.length
  const progressPct = totalSteps > 0 ? Math.round((completedCount / totalSteps) * 100) : 0

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Command Center" subtitle="Give GovFlow AI a goal, or run the deterministic judging demo." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <form onSubmit={handleSubmitGoal} className={cardClassName(true, 'flex flex-col gap-3')}>
          <label htmlFor="goal">
            <SectionLabel>Describe your goal</SectionLabel>
          </label>
          <textarea
            id="goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. What do I need to start a food-processing business?"
            rows={3}
            className="resize-none rounded-md border border-[var(--gf-border)] bg-[var(--gf-bg)] px-3 py-2 text-sm text-[var(--gf-text)] outline-none focus:border-[var(--gf-accent)]"
          />
          <Button type="submit" disabled={submitting !== null || !goal.trim()} className="self-start">
            {submitting === 'goal' ? 'Starting…' : 'Start workflow'}
          </Button>
        </form>

        <Card padded className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <SectionLabel>One-click demo (judging flow)</SectionLabel>
            <MockDataBadge />
          </div>
          <div className="flex flex-col gap-1.5">
            {SCENARIOS.map((s) => (
              <label key={s.value} className="flex items-start gap-2 text-xs text-[var(--gf-text-dim)]">
                <input
                  type="radio"
                  name="scenario"
                  value={s.value}
                  checked={scenario === s.value}
                  onChange={() => setScenario(s.value)}
                  className="mt-0.5 accent-[var(--gf-accent)]"
                />
                <span>
                  <span className="font-medium text-[var(--gf-text)]">{s.label}</span> — {s.description}
                </span>
              </label>
            ))}
          </div>
          <Button variant="outline" onClick={() => void handleRunDemo()} disabled={submitting !== null} className="self-start">
            {submitting === 'demo' ? 'Starting demo…' : '▶ Run Demo'}
          </Button>
        </Card>
      </div>

      {error ? <ErrorState message={error} /> : null}

      {activeWorkflowId ? (
        <div className="flex flex-col gap-4">
          <Card padded>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <SectionLabel>Interpreted goal</SectionLabel>
                <p className="mt-1 text-sm text-[var(--gf-text)]">
                  {typeof goalAnalyzed?.goal === 'string'
                    ? goalAnalyzed.goal
                    : stream.hasReceivedData
                      ? 'Waiting for GoalInterpreterAgent…'
                      : 'Connecting…'}
                </p>
              </div>
              <WorkflowStatusBadge status={stream.status} />
            </div>

            <div className="mt-4 flex items-center gap-4 text-xs text-[var(--gf-text-dim)]">
              <span>
                Current step: <span className="text-[var(--gf-text)]">{stream.currentStep ?? '—'}</span>
              </span>
              <span>
                Progress: <span className="text-[var(--gf-text)]">{completedCount} / {totalSteps || '?'}</span>
              </span>
            </div>
            {totalSteps > 0 ? (
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-[var(--gf-border)]">
                <div
                  className="h-full rounded-full bg-[var(--gf-status-completed)] transition-all"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
            ) : null}
          </Card>

          <HumanInTheLoopBanner status={stream.status} workflowId={activeWorkflowId} events={stream.events} />

          <div>
            <div className="mb-2">
              <SectionLabel>Live activity</SectionLabel>
            </div>
            <LiveActivityFeed activity={stream.agentActivity} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
