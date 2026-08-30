import type { AgentInfo } from '../types/api'

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
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-[var(--gf-text-faint)]">
            <th className="px-4 py-2.5 font-medium">Agent</th>
            <th className="px-4 py-2.5 font-medium">Responsibility</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
            <th className="px-4 py-2.5 font-medium">Last action</th>
            <th className="px-4 py-2.5 font-medium">Last active</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--gf-border)]">
          {agents.map((agent) => (
            <tr key={agent.name}>
              <td className="px-4 py-3 font-medium text-[var(--gf-text)]">{agent.name}</td>
              <td className="max-w-xs px-4 py-3 text-[var(--gf-text-dim)]">{agent.responsibility}</td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${STATUS_DOT[agent.status] ?? 'bg-slate-500'}`} />
                  <span className="text-xs capitalize text-[var(--gf-text-dim)]">{agent.status}</span>
                </span>
              </td>
              <td className="max-w-sm truncate px-4 py-3 text-xs text-[var(--gf-text-faint)]" title={agent.last_action ?? undefined}>
                {agent.last_action ?? '—'}
              </td>
              <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-[var(--gf-text-faint)]">
                {formatTime(agent.last_active_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
