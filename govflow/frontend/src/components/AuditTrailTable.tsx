import { useState } from 'react'
import type { AuditLogEntry } from '../types/api'
import type { WsAuditPayload } from '../types/websocket'
import { EmptyState } from './EmptyState'
import { AgentTag } from './ui/AgentTag'
import { Card, CardHeaderBar } from './ui/Card'
import { SectionLabel } from './ui/PageHeader'
import { TABLE_BODY_DIVIDER, TABLE_HEAD_ROW, TABLE_TD, TABLE_TH } from './ui/table'

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

type AnyAuditEntry = AuditLogEntry | WsAuditPayload

/** Renders GET /api/workflows/{id}/audit's initial fetch, then stays live
 * as WS "audit" messages stream in (see useWorkflowStream) -- both feed
 * the same shape, so the table doesn't care which source a row came from.
 * source="bus_wide_audit_listener" rows (AuditAgent's safety-net entries)
 * are visually de-emphasized rather than hidden, since they're proof the
 * audit trail is complete even when an agent's own logging is the
 * "primary" row for the same event. */
export function AuditTrailTable({ entries }: { entries: AnyAuditEntry[] }) {
  const [showBusWide, setShowBusWide] = useState(false)

  const visible = showBusWide ? entries : entries.filter((e) => e.source !== 'bus_wide_audit_listener')

  return (
    <Card>
      <CardHeaderBar
        left={
          <SectionLabel>
            Audit trail ({visible.length}
            {showBusWide ? '' : ` of ${entries.length}`})
          </SectionLabel>
        }
        right={
          <label className="flex items-center gap-2 text-xs text-[var(--gf-text-faint)]">
            <input
              type="checkbox"
              checked={showBusWide}
              onChange={(e) => setShowBusWide(e.target.checked)}
              className="accent-[var(--gf-accent)]"
            />
            Show AuditAgent's bus-wide safety-net entries
          </label>
        }
      />

      {visible.length === 0 ? (
        <div className="p-4">
          <EmptyState
            title="No audit entries yet"
            description="Every agent decision (and every event, via AuditAgent's safety net) is recorded here."
          />
        </div>
      ) : (
        <div className="max-h-[32rem] overflow-y-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-[var(--gf-surface)]">
              <tr className={TABLE_HEAD_ROW}>
                <th className={TABLE_TH}>Time</th>
                <th className={TABLE_TH}>Event</th>
                <th className={TABLE_TH}>Agent</th>
                <th className={TABLE_TH}>Decision</th>
                <th className={TABLE_TH}>Tool</th>
              </tr>
            </thead>
            <tbody className={TABLE_BODY_DIVIDER}>
              {visible.map((entry, index) => (
                <tr
                  key={`${entry.timestamp}-${index}`}
                  className={entry.source === 'bus_wide_audit_listener' ? 'opacity-50' : undefined}
                >
                  <td className={`whitespace-nowrap ${TABLE_TD} font-mono text-xs text-[var(--gf-text-faint)]`}>
                    {formatTime(entry.timestamp)}
                  </td>
                  <td className={`whitespace-nowrap ${TABLE_TD} text-xs text-[var(--gf-text-dim)]`}>
                    {entry.event}
                  </td>
                  <td className={`whitespace-nowrap ${TABLE_TD}`}>
                    <AgentTag>{entry.agent}</AgentTag>
                  </td>
                  <td className={`${TABLE_TD} text-[var(--gf-text-dim)]`}>{entry.decision}</td>
                  <td className={`whitespace-nowrap ${TABLE_TD} font-mono text-xs text-[var(--gf-text-faint)]`}>
                    {entry.tool ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
