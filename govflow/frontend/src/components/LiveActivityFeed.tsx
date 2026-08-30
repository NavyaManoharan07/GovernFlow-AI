import { useEffect, useRef } from 'react'
import type { WsAgentActivityPayload } from '../types/websocket'
import { EmptyState } from './EmptyState'

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return iso
  }
}

function describeAction(action: string): string {
  return action
    .toLowerCase()
    .split('_')
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(' ')
}

/** Driven entirely by real WS "agent_activity" messages -- no hardcoded
 * example rows. Each agent_activity message IS one real agent handling
 * one real event (see backend/api/websocket.py: on_event derives it
 * directly from the Event that was actually published). */
export function LiveActivityFeed({ activity }: { activity: WsAgentActivityPayload[] }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [activity.length])

  if (activity.length === 0) {
    return (
      <EmptyState
        title="No activity yet"
        description="Start a workflow or run the demo to see agents react in real time."
      />
    )
  }

  return (
    <div
      ref={scrollRef}
      className="max-h-96 overflow-y-auto rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)]"
    >
      <ul className="divide-y divide-[var(--gf-border)]">
        {activity.map((entry, index) => (
          <li key={`${entry.timestamp}-${index}`} className="flex items-start gap-3 px-4 py-2.5 text-sm">
            <span className="mt-0.5 shrink-0 font-mono text-[11px] text-[var(--gf-text-faint)]">
              {formatTime(entry.timestamp)}
            </span>
            <span className="shrink-0 rounded bg-[var(--gf-accent)]/15 px-1.5 py-0.5 text-[11px] font-medium text-[var(--gf-accent)]">
              {entry.agent}
            </span>
            <span className="text-[var(--gf-text-dim)]">{describeAction(entry.action)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
