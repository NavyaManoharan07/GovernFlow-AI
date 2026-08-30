import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { WorkflowGraph } from './WorkflowGraph'
import type { WorkflowStep } from '../types/api'

const SAMPLE_STEPS: WorkflowStep[] = [
  { id: 'business_registration', name: 'Business Registration', service: 'business-registration', depends_on: [], status: 'COMPLETED', metadata: {} },
  { id: 'tax_registration', name: 'Tax Registration', service: 'tax-registration', depends_on: ['business_registration'], status: 'RUNNING', metadata: {} },
  { id: 'food_license', name: 'Food License', service: 'food-license', depends_on: ['business_registration'], status: 'PENDING', metadata: {} },
  { id: 'local_approval', name: 'Local Approval', service: 'local-approval', depends_on: ['tax_registration', 'food_license'], status: 'PENDING', metadata: {} },
]

describe('WorkflowGraph', () => {
  it('shows an empty state when no graph is available', () => {
    render(<WorkflowGraph steps={[]} available={false} />)
    expect(screen.getByText(/no workflow graph yet/i)).toBeInTheDocument()
  })

  it('renders every real step with its name and status', () => {
    render(<WorkflowGraph steps={SAMPLE_STEPS} available={true} />)

    expect(screen.getByText('Business Registration')).toBeInTheDocument()
    expect(screen.getByText('Tax Registration')).toBeInTheDocument()
    expect(screen.getByText('Food License')).toBeInTheDocument()
    expect(screen.getByText('Local Approval')).toBeInTheDocument()

    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText('RUNNING')).toBeInTheDocument()
    expect(screen.getAllByText('PENDING')).toHaveLength(2)
  })

  it('draws one edge per real depends_on relationship', () => {
    const { container } = render(<WorkflowGraph steps={SAMPLE_STEPS} available={true} />)
    // business_registration->tax_registration, business_registration->food_license,
    // tax_registration->local_approval, food_license->local_approval = 4 edges
    const paths = container.querySelectorAll('path[marker-end]')
    expect(paths).toHaveLength(4)
  })
})
