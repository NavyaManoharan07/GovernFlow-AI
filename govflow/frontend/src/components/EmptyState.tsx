export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-[var(--gf-border)] px-6 py-12 text-center">
      <p className="text-sm font-medium text-[var(--gf-text-dim)]">{title}</p>
      {description ? <p className="text-xs text-[var(--gf-text-faint)]">{description}</p> : null}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
      {message}
    </div>
  )
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-6 text-sm text-[var(--gf-text-dim)]">
      <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--gf-accent)]" />
      {label}
    </div>
  )
}
