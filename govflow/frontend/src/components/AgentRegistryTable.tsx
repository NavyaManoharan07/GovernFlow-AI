import type { AgentInfo } from '../types/api'
import { EmptyState } from './EmptyState'
import { Card, CardHeaderBar } from './ui/Card'
import { SectionLabel } from './ui/PageHeader'
import { TABLE_BODY_DIVIDER, TABLE_HEAD_ROW, TABLE_TD, TABLE_TH } from './ui/table'

const STATUS_DOT: Record<string, string> = {
  idle: 'bg-slate-500',
  running: 'bg-blue-500 animate-pulse',
  error: 'bg-red-500',
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString()
  } catch {
    return iso
  }
}

/** Renders whatever GET /api/agents actually returns -- never a
 * hardcoded agent list, so it stays correct if the backend's roster
 * changes. */
export function AgentRegistryTable({ agents }: { agents: AgentInfo[] }) {
  if (agents.length === 0) {
    return (
      <EmptyState title="No agents reported yet" description="Waiting for GET /api/agents to respond." />
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeaderBar left={<SectionLabel>Agents ({agents.length})</SectionLabel>} />
      <table className="w-full text-left text-sm">
        <thead>
          <tr className={TABLE_HEAD_ROW}>
            <th className={TABLE_TH}>Agent</th>
            <th className={TABLE_TH}>Responsibility</th>
            <th className={TABLE_TH}>Status</th>
            <th className={TABLE_TH}>Last action</th>
            <th className={TABLE_TH}>Last active</th>
          </tr>
        </thead>
        <tbody className={TABLE_BODY_DIVIDER}>
          {agents.map((agent) => (
            <tr key={agent.name}>
              <td className={`${TABLE_TD} font-medium text-[var(--gf-text)]`}>{agent.name}</td>
              <td className={`max-w-xs ${TABLE_TD} text-[var(--gf-text-dim)]`}>{agent.responsibility}</td>
              <td className={TABLE_TD}>
                <span className="inline-flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${STATUS_DOT[agent.status] ?? 'bg-slate-500'}`} />
                  <span className="text-xs capitalize text-[var(--gf-text-dim)]">{agent.status}</span>
                </span>
              </td>
              <td
                className={`max-w-sm truncate ${TABLE_TD} text-xs text-[var(--gf-text-faint)]`}
                title={agent.last_action ?? undefined}
              >
                {agent.last_action ?? '—'}
              </td>
              <td className={`whitespace-nowrap ${TABLE_TD} font-mono text-xs text-[var(--gf-text-faint)]`}>
                {formatTime(agent.last_active_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
