import type { ReactNode } from 'react'

/**
 * The h1 + subtitle pattern every page (Command Center, Workflow Graph,
 * Agent Registry, Application Tracker, Audit Trail) already opened with.
 * `right` is the optional top-right slot Workflow Graph uses for the
 * workflow status badge -- Command Center's own status badge sits in the
 * "interpreted goal" card below the header instead, since it only makes
 * sense once a workflow is active.
 */
export function PageHeader({ title, subtitle, right }: { title: string; subtitle: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-[var(--gf-text)]">{title}</h1>
        <p className="mt-1 text-sm text-[var(--gf-text-dim)]">{subtitle}</p>
      </div>
      {right}
    </div>
  )
}

/** The small uppercase eyebrow label used above form fields, section
 * groups, and table title bars everywhere in the app. */
export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-xs font-medium uppercase tracking-wide text-[var(--gf-text-faint)]">{children}</p>
  )
}
