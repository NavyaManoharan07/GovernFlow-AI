import type { StepStatus, WorkflowStatus } from '../types/api'

/** The one authoritative status -> color mapping (as hex, for non-Tailwind
 * consumers like SVG `stroke`) -- WorkflowGraph's node outlines read this
 * directly instead of keeping their own separate copy of the same six
 * colors. Values match the Tailwind utility classes below (green-500,
 * blue-500, yellow-500, orange-500, red-500, slate-500) and the
 * `--gf-status-*` custom properties in index.css -- keep all three in sync
 * if a status color ever changes. */
export const STEP_STATUS_HEX: Record<StepStatus, string> = {
  COMPLETED: '#22c55e',
  RUNNING: '#3b82f6',
  WAITING: '#eab308',
  BLOCKED: '#f97316',
  FAILED: '#ef4444',
  PENDING: '#4b5568',
}

const WORKFLOW_STYLES: Record<WorkflowStatus, string> = {
  RUNNING: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  WAITING_FOR_USER: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  BLOCKED: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  COMPLETED: 'bg-green-500/15 text-green-400 border-green-500/30',
  FAILED: 'bg-red-500/15 text-red-400 border-red-500/30',
}

const STEP_STYLES: Record<StepStatus, string> = {
  COMPLETED: 'bg-green-500/15 text-green-400 border-green-500/30',
  RUNNING: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  WAITING: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
  BLOCKED: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  FAILED: 'bg-red-500/15 text-red-400 border-red-500/30',
  PENDING: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
}

export function WorkflowStatusBadge({ status }: { status: WorkflowStatus | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center rounded-full border border-[var(--gf-border)] px-2.5 py-0.5 text-xs font-medium text-[var(--gf-text-faint)]">
        No workflow
      </span>
    )
  }
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${WORKFLOW_STYLES[status]}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export function StepStatusBadge({ status }: { status: StepStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${STEP_STYLES[status]}`}
    >
      {status}
    </span>
  )
}
