import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getWorkflow, runDemo } from './api'

// A REAL example response captured from a live backend run (see the Part 3
// verification transcript) -- not a guessed shape.
const REAL_WORKFLOW_RESPONSE = {
  workflow_id: 'f960ac51-0fc9-49b2-a2fa-6fde6d819634',
  user_id: 'demo-user',
  goal: 'I want to start a small food-processing business in Tamil Nadu',
  status: 'COMPLETED',
  current_step: null,
  completed_steps: ['business_registration', 'tax_registration', 'food_license', 'local_approval'],
  pending_steps: [],
  failed_steps: [],
  required_documents: [],
  applications: [
    {
      application_id: '68bbbf7d-5d2b-4e4c-8d3a-6b7988ec964b',
      service: 'business-registration',
      department: 'Ministry of Corporate Affairs (Mock)',
      status: 'SUBMITTED',
      scenario: 'clean',
      mock_data: true,
      step_id: 'business_registration',
    },
  ],
  events: [],
  created_at: '2026-08-29T15:15:12.078300Z',
  updated_at: '2026-08-29T15:15:17.544384Z',
  metadata: { scenario: 'clean', demo: true },
}

const REAL_DEMO_RUN_RESPONSE = {
  workflow_id: 'f960ac51-0fc9-49b2-a2fa-6fde6d819634',
  status: 'ACCEPTED',
  user_id: 'demo-user',
  goal: 'I want to start a small food-processing business in Tamil Nadu',
  message: 'Demo started (scenario=clean). Connect to WS /ws/workflows/f960ac51-0fc9-49b2-a2fa-6fde6d819634 to watch it unfold.',
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('getWorkflow', () => {
  it('parses a real GET /api/workflows/{id} response into the typed shape', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => REAL_WORKFLOW_RESPONSE,
    })
    vi.stubGlobal('fetch', fetchMock)

    const workflow = await getWorkflow('f960ac51-0fc9-49b2-a2fa-6fde6d819634')

    expect(workflow.status).toBe('COMPLETED')
    expect(workflow.completed_steps).toHaveLength(4)
    expect(workflow.applications[0].department).toBe('Ministry of Corporate Affairs (Mock)')
    expect(workflow.metadata.scenario).toBe('clean')

    // Correct URL + method
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/workflows/f960ac51-0fc9-49b2-a2fa-6fde6d819634'),
      expect.any(Object),
    )
  })

  it('throws ApiError with the response detail on a non-2xx response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "workflow 'nope' not found" }),
      }),
    )

    await expect(getWorkflow('nope')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('runDemo', () => {
  it('parses a real POST /api/demo/run (202) response and hits the right query params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => REAL_DEMO_RUN_RESPONSE,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await runDemo('clean', 'demo-user')

    expect(result.status).toBe('ACCEPTED')
    expect(result.workflow_id).toBe('f960ac51-0fc9-49b2-a2fa-6fde6d819634')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/demo/run?')
    expect(url).toContain('scenario=clean')
    expect((init as RequestInit).method).toBe('POST')
  })
})
