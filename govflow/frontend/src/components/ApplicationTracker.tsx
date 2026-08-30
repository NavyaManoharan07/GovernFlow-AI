import { useMemo } from 'react'
import type { ApplicationRecord } from '../types/api'
import type { WsEventPayload } from '../types/websocket'
import { EmptyState } from './EmptyState'
import { MockDataBadge } from './MockDataBadge'

const NEXT_ACTION: Record<string, string> = {
  SUBMITTED: 'Awaiting government review',
  PENDING: 'Awaiting government review',
  APPROVED: 'None — approved',
  REJECTED: 'Human review required (see Audit Trail / resume)',
  DOCUMENT_MISSING: 'Upload the missing documents, then resume',
}

const STATUS_COLOR: Record<string, string> = {
  SUBMITTED: 'text-blue-400',
  PENDING: 'text-blue-400',
  APPROVED: 'text-green-400',
  REJECTED: 'text-red-400',
  DOCUMENT_MISSING: 'text-orange-400',
}

/** workflow.applications[].status is only ever "SUBMITTED" -- it's
 * written once by ApplicationAgent and never updated afterward (only
 * events change, not the stored record). The real current status lives
 * in the event stream (APPLICATION_STATUS_CHANGED / APPLICATION_APPROVED
 * / APPLICATION_REJECTED / DOCUMENT_MISSING), so this derives a live
 * per-application_id status map from real events rather than trusting the
 * static field. */
function deriveLiveStatus(events: WsEventPayload[]): Map<string, string> {
  const statusByApplication = new Map<string, string>()
  for (const event of events) {
    const applicationId = event.payload.application_id
    if (typeof applicationId !== 'string') continue

    if (event.event_type === 'APPLICATION_STATUS_CHANGED' && typeof event.payload.status === 'string') {
      statusByApplication.set(applicationId, event.payload.status)
    } else if (event.event_type === 'APPLICATION_APPROVED') {
      statusByApplication.set(applicationId, 'APPROVED')
    } else if (event.event_type === 'APPLICATION_REJECTED') {
      statusByApplication.set(applicationId, 'REJECTED')
    } else if (event.event_type === 'DOCUMENT_MISSING') {
      statusByApplication.set(applicationId, 'DOCUMENT_MISSING')
    }
  }
  return statusByApplication
}

export function ApplicationTracker({
  applications,
  events,
}: {
  applications: ApplicationRecord[]
  events: WsEventPayload[]
}) {
  const liveStatus = useMemo(() => deriveLiveStatus(events), [events])

  if (applications.length === 0) {
    return (
      <EmptyState
        title="No applications submitted yet"
        description="Applications appear here as ApplicationAgent submits them to the mock government services."
      />
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--gf-border)] px-4 py-2.5">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--gf-text-faint)]">
          Applications ({applications.length})
        </p>
        <MockDataBadge />
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-[var(--gf-text-faint)]">
            <th className="px-4 py-2 font-medium">Application ID</th>
            <th className="px-4 py-2 font-medium">Department</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Next action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--gf-border)]">
          {applications.map((app) => {
            const status = liveStatus.get(app.application_id) ?? app.status
            return (
              <tr key={app.application_id}>
                <td className="px-4 py-2.5 font-mono text-xs text-[var(--gf-text-dim)]">
                  {app.application_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2.5 text-[var(--gf-text)]">{app.department}</td>
                <td className={`px-4 py-2.5 font-medium ${STATUS_COLOR[status] ?? 'text-[var(--gf-text-dim)]'}`}>
                  {status}
                </td>
                <td className="px-4 py-2.5 text-[var(--gf-text-dim)]">{NEXT_ACTION[status] ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
