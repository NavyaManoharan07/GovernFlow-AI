/** Unmissable indicator wherever RAG-sourced regulatory content or mock
 * application results are shown, matching the backend's own labeling
 * (every mock API response carries MOCK_DATA: true; every knowledge-base
 * document is headed "MOCK / DEMONSTRATION DATA"). */
export function MockDataBadge({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-400 ${className}`}
      title="This is simulated data for the demo -- not a real government integration or real current law."
    >
      Mock / demonstration data
    </span>
  )
}
