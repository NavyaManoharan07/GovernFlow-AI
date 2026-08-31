import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useActiveWorkflow } from '../context/WorkflowContext'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/command-center', label: 'Command Center', icon: '⌂' },
  { to: '/graph', label: 'Workflow Graph', icon: '⌗' },
  { to: '/agents', label: 'Agent Registry', icon: '◈' },
  { to: '/applications', label: 'Application Tracker', icon: '▤' },
  { to: '/audit', label: 'Audit Trail', icon: '≡' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { activeWorkflowId } = useActiveWorkflow()

  return (
    <div className="flex min-h-screen bg-[var(--gf-bg)] text-[var(--gf-text)]">
      <aside className="flex w-60 shrink-0 flex-col border-r border-[var(--gf-border)] bg-[var(--gf-surface)]">
        <div className="border-b border-[var(--gf-border)] px-5 py-5">
          <p className="text-sm font-semibold tracking-wide text-[var(--gf-text)]">GovFlow AI</p>
          <p className="text-xs text-[var(--gf-text-faint)]">Orchestration Command Center</p>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? 'bg-[var(--gf-accent)]/15 text-[var(--gf-text)]'
                    : 'text-[var(--gf-text-dim)] hover:bg-white/5 hover:text-[var(--gf-text)]'
                }`
              }
            >
              <span aria-hidden className="w-4 text-center text-[var(--gf-text-faint)]">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-[var(--gf-border)] px-4 py-4 text-xs">
          <p className="text-[var(--gf-text-faint)]">Active workflow</p>
          <p className="mt-1 truncate font-mono text-[var(--gf-text-dim)]" title={activeWorkflowId ?? undefined}>
            {activeWorkflowId ?? 'none yet'}
          </p>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-8 py-8">{children}</div>
      </main>
    </div>
  )
}
