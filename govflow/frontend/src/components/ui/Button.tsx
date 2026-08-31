import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'outline' | 'ghost'
type Size = 'md' | 'sm'

const VARIANT_CLASSES: Record<Variant, string> = {
  // Solid accent -- "Start workflow", "Retry step".
  primary: 'bg-[var(--gf-accent)] text-white hover:bg-[var(--gf-accent-hover)]',
  // Accent-bordered, transparent fill -- "▶ Run Demo".
  outline: 'border border-[var(--gf-accent)] text-[var(--gf-accent)] hover:bg-[var(--gf-accent)]/10',
  // Neutral-bordered -- "Abandon step".
  ghost: 'border border-[var(--gf-border)] text-[var(--gf-text-dim)] hover:bg-white/5',
}

const SIZE_CLASSES: Record<Size, string> = {
  md: 'px-4 py-2 text-sm',
  sm: 'px-3 py-1.5 text-xs',
}

/**
 * The three button treatments already established on Command Center and
 * the Human-in-the-Loop banner, as one component so every button in the
 * app shares identical color, radius, weight, transition, and disabled
 * states instead of each call site retyping the className.
 */
export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={`rounded-md font-medium transition-colors disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...rest}
    />
  )
}
