/**
 * Shared className fragments for the three data tables (Agent Registry,
 * Application Tracker, Audit Trail). Before this, each table hand-typed
 * its own header/row padding and they'd drifted apart (py-2.5/py-3 vs
 * py-2/py-2.5 vs py-2/py-2 for header/body respectively) -- these
 * constants are now the one place that spacing is defined, so the three
 * tables render with identical row rhythm.
 */
export const TABLE_HEAD_ROW = 'text-xs uppercase tracking-wide text-[var(--gf-text-faint)]'
export const TABLE_TH = 'px-4 py-2.5 font-medium'
export const TABLE_TD = 'px-4 py-2.5'
export const TABLE_BODY_DIVIDER = 'divide-y divide-[var(--gf-border)]'
