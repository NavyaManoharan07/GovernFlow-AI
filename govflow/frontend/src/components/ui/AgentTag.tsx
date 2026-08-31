/** The small accent-tinted pill used to show an agent's name -- Live
 * Activity Feed and Audit Trail both render one per row; extracted so
 * they can't drift apart the way the rest of this consistency pass found
 * elsewhere in the app. */
export function AgentTag({ children }: { children: string }) {
  return (
    <span className="rounded bg-[var(--gf-accent)]/15 px-1.5 py-0.5 text-[11px] font-medium text-[var(--gf-accent)]">
      {children}
    </span>
  )
}
