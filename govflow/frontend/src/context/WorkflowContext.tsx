import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

interface WorkflowContextValue {
  activeWorkflowId: string | null
  setActiveWorkflowId: (id: string | null) => void
}

const WorkflowContext = createContext<WorkflowContextValue | null>(null)

/** Holds the single "currently being watched" workflow_id, set by Command
 * Center when a workflow is created or the demo is run, and read by the
 * other workflow-scoped nav pages (Workflow Graph, Application Tracker,
 * Audit Trail) so they don't each need their own goal-submission UI. */
export function WorkflowProvider({ children }: { children: ReactNode }) {
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null)

  const value = useMemo(() => ({ activeWorkflowId, setActiveWorkflowId }), [activeWorkflowId])

  return <WorkflowContext.Provider value={value}>{children}</WorkflowContext.Provider>
}

export function useActiveWorkflow(): WorkflowContextValue {
  const ctx = useContext(WorkflowContext)
  if (!ctx) {
    throw new Error('useActiveWorkflow must be used within a WorkflowProvider')
  }
  return ctx
}
