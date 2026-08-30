import { useState } from 'react'
import type { AuditLogEntry } from '../types/api'
import type { WsAuditPayload } from '../types/websocket'
import { EmptyState } from './EmptyState'

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
    <div className="rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)]">
      <div className="flex items-center justify-between border-b border-[var(--gf-border)] px-4 py-2.5">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--gf-text-faint)]">
          Audit trail ({visible.length}
          {showBusWide ? '' : ` of ${entries.length}`})
        </p>
        <label className="flex items-center gap-2 text-xs text-[var(--gf-text-faint)]">
          <input
            type="checkbox"
            checked={showBusWide}
            onChange={(e) => setShowBusWide(e.target.checked)}
            className="accent-[var(--gf-accent)]"
          />
          Show AuditAgent's bus-wide safety-net entries
        </label>
      </div>

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
              <tr className="text-xs uppercase tracking-wide text-[var(--gf-text-faint)]">
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Event</th>
                <th className="px-4 py-2 font-medium">Agent</th>
                <th className="px-4 py-2 font-medium">Decision</th>
                <th className="px-4 py-2 font-medium">Tool</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--gf-border)]">
              {visible.map((entry, index) => (
                <tr
                  key={`${entry.timestamp}-${index}`}
                  className={entry.source === 'bus_wide_audit_listener' ? 'opacity-50' : undefined}
                >
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-[var(--gf-text-faint)]">
                    {formatTime(entry.timestamp)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-xs text-[var(--gf-text-dim)]">{entry.event}</td>
                  <td className="whitespace-nowrap px-4 py-2">
                    <span className="rounded bg-[var(--gf-accent)]/15 px-1.5 py-0.5 text-[11px] font-medium text-[var(--gf-accent)]">
                      {entry.agent}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-[var(--gf-text-dim)]">{entry.decision}</td>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-[var(--gf-text-faint)]">
                    {entry.tool ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
