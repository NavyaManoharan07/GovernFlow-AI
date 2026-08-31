import { useMemo } from 'react'
import type { ApplicationRecord } from '../types/api'
import type { WsEventPayload } from '../types/websocket'
import { EmptyState } from './EmptyState'
import { MockDataBadge } from './MockDataBadge'
import { Card, CardHeaderBar } from './ui/Card'
import { SectionLabel } from './ui/PageHeader'
import { TABLE_BODY_DIVIDER, TABLE_HEAD_ROW, TABLE_TD, TABLE_TH } from './ui/table'

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
    <Card className="overflow-hidden">
      <CardHeaderBar
        left={<SectionLabel>Applications ({applications.length})</SectionLabel>}
        right={<MockDataBadge />}
      />
      <table className="w-full text-left text-sm">
        <thead>
          <tr className={TABLE_HEAD_ROW}>
            <th className={TABLE_TH}>Application ID</th>
            <th className={TABLE_TH}>Department</th>
            <th className={TABLE_TH}>Status</th>
            <th className={TABLE_TH}>Next action</th>
          </tr>
        </thead>
        <tbody className={TABLE_BODY_DIVIDER}>
          {applications.map((app) => {
            const status = liveStatus.get(app.application_id) ?? app.status
            return (
              <tr key={app.application_id}>
                <td className={`${TABLE_TD} font-mono text-xs text-[var(--gf-text-dim)]`}>
                  {app.application_id.slice(0, 8)}…
                </td>
                <td className={`${TABLE_TD} text-[var(--gf-text)]`}>{app.department}</td>
                <td className={`${TABLE_TD} font-medium ${STATUS_COLOR[status] ?? 'text-[var(--gf-text-dim)]'}`}>
                  {status}
                </td>
                <td className={`${TABLE_TD} text-[var(--gf-text-dim)]`}>{NEXT_ACTION[status] ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}
