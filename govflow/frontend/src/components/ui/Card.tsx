import { forwardRef, type HTMLAttributes, type ReactNode } from 'react'

/**
 * The single card recipe used everywhere in the app: rounded-lg border +
 * surface background. Every panel on Command Center, Workflow Graph,
 * Agent Registry, Application Tracker, and Audit Trail should render
 * through this component (or, for the one non-<div> case -- Command
 * Center's goal form -- through `cardClassName` directly) instead of
 * re-typing the className by hand. That's what keeps border radius,
 * border color, and background pixel-identical as the app grows.
 *
 * `padded` covers the two real layouts already in use: form/summary
 * panels want the card's own p-4 (Command Center's goal form, the demo
 * panel, the interpreted-goal summary, Workflow Graph's SVG frame);
 * tables and lists own their internal row padding instead, so the card
 * itself stays unpadded (Agent Registry / Application Tracker / Audit
 * Trail / Live Activity Feed).
 */
export function cardClassName(padded = false, className = ''): string {
  return `rounded-lg border border-[var(--gf-border)] bg-[var(--gf-surface)] ${padded ? 'p-4' : ''} ${className}`
}

export const Card = forwardRef<
  HTMLDivElement,
  HTMLAttributes<HTMLDivElement> & { children: ReactNode; padded?: boolean }
>(function Card({ children, padded = false, className = '', ...rest }, ref) {
  return (
    <div ref={ref} className={cardClassName(padded, className)} {...rest}>
      {children}
    </div>
  )
})

/** The small label + optional right-aligned control bar used at the top
 * of every card that contains a table (Applications, Audit Trail) -- now
 * also Agent Registry, which previously skipped it. */
export function CardHeaderBar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-[var(--gf-border)] px-4 py-2.5">
      {left}
      {right}
    </div>
  )
}
