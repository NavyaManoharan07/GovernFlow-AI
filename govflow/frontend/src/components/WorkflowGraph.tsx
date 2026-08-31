import { useMemo } from 'react'
import type { WorkflowStep } from '../types/api'
import { EmptyState } from './EmptyState'
import { STEP_STATUS_HEX, StepStatusBadge } from './StatusBadge'
import { Card } from './ui/Card'

const NODE_WIDTH = 190
const NODE_HEIGHT = 60
const COLUMN_GAP = 90
const ROW_GAP = 32
const PADDING = 24

interface LaidOutStep {
  step: WorkflowStep
  level: number
  row: number
  x: number
  y: number
}

/** Longest-path-from-root layering: a step's level is one more than the
 * deepest of its dependencies' levels (0 if it has none). This is the
 * REAL dependency structure from WorkflowStep.depends_on -- nothing here
 * is inferred or hardcoded per service name. */
function layoutSteps(steps: WorkflowStep[]): LaidOutStep[] {
  const byId = new Map(steps.map((s) => [s.id, s]))
  const levelCache = new Map<string, number>()

  function levelOf(id: string, guard: Set<string> = new Set()): number {
    if (levelCache.has(id)) return levelCache.get(id) as number
    if (guard.has(id)) return 0 // defensive: a cycle should never happen (engine validates this), but never hang the UI
    guard.add(id)
    const step = byId.get(id)
    if (!step || step.depends_on.length === 0) {
      levelCache.set(id, 0)
      return 0
    }
    const level = 1 + Math.max(...step.depends_on.map((dep) => (byId.has(dep) ? levelOf(dep, guard) : 0)))
    levelCache.set(id, level)
    return level
  }

  const withLevels = steps.map((step) => ({ step, level: levelOf(step.id) }))
  const rowCounters = new Map<number, number>()
  return withLevels.map(({ step, level }) => {
    const row = rowCounters.get(level) ?? 0
    rowCounters.set(level, row + 1)
    return {
      step,
      level,
      row,
      x: PADDING + level * (NODE_WIDTH + COLUMN_GAP),
      y: PADDING + row * (NODE_HEIGHT + ROW_GAP),
    }
  })
}

export function WorkflowGraph({ steps, available }: { steps: WorkflowStep[]; available: boolean }) {
  const laidOut = useMemo(() => layoutSteps(steps), [steps])

  if (!available || steps.length === 0) {
    return (
      <EmptyState
        title="No workflow graph yet"
        description="Start a workflow from Command Center or run the demo to see the live dependency graph."
      />
    )
  }

  const byId = new Map(laidOut.map((n) => [n.step.id, n]))
  const maxLevel = Math.max(...laidOut.map((n) => n.level))
  const maxRows = Math.max(...Array.from(new Set(laidOut.map((n) => n.level))).map(
    (level) => laidOut.filter((n) => n.level === level).length,
  ))
  const width = PADDING * 2 + (maxLevel + 1) * NODE_WIDTH + maxLevel * COLUMN_GAP
  const height = PADDING * 2 + maxRows * NODE_HEIGHT + (maxRows - 1) * ROW_GAP

  return (
    <Card padded className="overflow-x-auto">
      <svg width={width} height={Math.max(height, NODE_HEIGHT + PADDING * 2)} className="min-w-full">
        {/* Edges, drawn first so nodes sit on top */}
        {laidOut.map((node) =>
          node.step.depends_on.map((depId) => {
            const from = byId.get(depId)
            if (!from) return null
            const x1 = from.x + NODE_WIDTH
            const y1 = from.y + NODE_HEIGHT / 2
            const x2 = node.x
            const y2 = node.y + NODE_HEIGHT / 2
            const midX = (x1 + x2) / 2
            return (
              <path
                key={`${depId}->${node.step.id}`}
                d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="var(--gf-border)"
                strokeWidth={2}
                markerEnd="url(#gf-arrow)"
              />
            )
          }),
        )}

        <defs>
          <marker id="gf-arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="var(--gf-border)" />
          </marker>
        </defs>

        {laidOut.map((node) => {
          const isRunningLike = node.step.status === 'RUNNING'
          return (
            <g key={node.step.id} transform={`translate(${node.x}, ${node.y})`}>
              <rect
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={10}
                fill="var(--gf-surface-raised)"
                stroke={STEP_STATUS_HEX[node.step.status]}
                strokeWidth={isRunningLike ? 2.5 : 1.5}
                className={isRunningLike ? 'animate-pulse' : undefined}
              />
              <foreignObject width={NODE_WIDTH} height={NODE_HEIGHT}>
                <div className="flex h-full flex-col justify-center gap-1 px-3">
                  <p className="truncate text-xs font-medium text-[var(--gf-text)]">{node.step.name}</p>
                  <StepStatusBadge status={node.step.status} />
                </div>
              </foreignObject>
            </g>
          )
        })}
      </svg>
    </Card>
  )
}
