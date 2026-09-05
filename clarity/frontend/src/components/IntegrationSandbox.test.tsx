import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { IntegrationSandbox } from './IntegrationSandbox'
import { acknowledgeWorkOrder, dispositionInboundIntegration, dispatchWorkOrder, getFollowThrough, getIntegrations } from '../api'
import type { BookView, IntegrationView } from '../types'

vi.mock('../api', () => ({
  acknowledgeWorkOrder: vi.fn(), dispositionInboundIntegration: vi.fn(), dispatchWorkOrder: vi.fn(),
  getFollowThrough: vi.fn(), getIntegrations: vi.fn(), prepareWorkOrder: vi.fn(), receiveInboundIntegration: vi.fn(),
}))

const book = { clients: [{ client_id: 'CL-0014', client_name: 'Lau Chi Ming' }] } as unknown as BookView
const base: IntegrationView = { inbound: [], work_orders: [], capabilities: { source_systems: ['lending_credit'], destinations: ['crm', 'specialist_queue'], feature_schema_version: 'deterministic-priority-factors-v1', local_simulation: true, model_readiness: { feature_schema_version: 'deterministic-priority-factors-v1', training_eligible: false, reasons: ['Synthetic data'] } } }

describe('Integration Sandbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getIntegrations).mockResolvedValue(base)
    vi.mocked(getFollowThrough).mockResolvedValue({ tasks: [], referrals: [], outcomes: [], evidence_updates: [], reevaluations: [] })
  })
  afterEach(cleanup)

  it('limits inbound acceptance to Operations and clearly labels the simulation', async () => {
    const pending = { ...base, inbound: [{ id: 'IN-1', source_system: 'lending_credit', external_event_id: 'L-1', schema_version: 'v1', client_id: 'CL-0014', affected_insight_ids: ['IN-1'], source_ref: 'sandbox:L-1', summary: 'Update', occurred_at: '2026-08-26', received_at: '2026-08-26', payload_digest: 'digest', validation_state: 'validated' as const, operations_disposition: null, evidence_update_id: null, reevaluation_id: null, history: [] }] }
    vi.mocked(getIntegrations).mockResolvedValue(pending)
    vi.mocked(dispositionInboundIntegration).mockResolvedValue({ event: pending.inbound[0] })
    const user = userEvent.setup()
    render(<IntegrationSandbox role="operations" book={book} />)
    expect(await screen.findByText(/Local simulated integration/)).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('Mandatory Operations rationale'), 'Passed local validation.')
    await user.click(screen.getByRole('button', { name: 'Accept' }))
    await waitFor(() => expect(dispositionInboundIntegration).toHaveBeenCalledWith('IN-1', 'accept', 'operations', 'Passed local validation.'))
  })

  it('shows RM dispatch but does not show inbound controls', async () => {
    const order = { id: 'WO-1', idempotency_key: 'key', destination: 'crm' as const, work_record_type: 'task' as const, work_record_id: 'T-1', work_record_version: '1', client_id: 'CL-0014', insight_id: null, meeting_package_id: null, owner_role: 'rm', evidence_refs: ['clients.csv:CL-0014'], status: 'prepared' as const, external_reference: null, created_at: '2026-08-26', created_by: 'RM-SG-014' }
    vi.mocked(getIntegrations).mockResolvedValue({ ...base, work_orders: [order] })
    vi.mocked(dispatchWorkOrder).mockResolvedValue({ work_order: { ...order, status: 'dispatched', external_reference: 'SIM-CRM-1' }, replayed: false })
    const user = userEvent.setup()
    render(<IntegrationSandbox role="rm" book={book} />)
    expect(await screen.findByText('Prepare local work order')).toBeInTheDocument()
    expect(screen.queryByText('Receive simulated inbound update')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Simulate dispatch' }))
    await waitFor(() => expect(dispatchWorkOrder).toHaveBeenCalledWith('WO-1', 'rm'))
  })

  it('limits acknowledgement to an assigned specialist queue order', async () => {
    const order = { id: 'WO-2', idempotency_key: 'key', destination: 'specialist_queue' as const, work_record_type: 'referral' as const, work_record_id: 'R-1', work_record_version: '1', client_id: 'CL-0014', insight_id: null, meeting_package_id: null, owner_role: 'credit', evidence_refs: ['event_log.csv:EV-001'], status: 'dispatched' as const, external_reference: 'SIM-SPECIALIST-1', created_at: '2026-08-26', created_by: 'RM-SG-014' }
    vi.mocked(getIntegrations).mockResolvedValue({ ...base, work_orders: [order] })
    vi.mocked(acknowledgeWorkOrder).mockResolvedValue({ work_order: { ...order, status: 'acknowledged' } })
    const user = userEvent.setup()
    render(<IntegrationSandbox role="credit" book={book} />)
    await user.click(await screen.findByRole('button', { name: 'Acknowledge' }))
    await waitFor(() => expect(acknowledgeWorkOrder).toHaveBeenCalledWith('WO-2', 'credit'))
  })
})
