import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getAudit, getFollowThrough } from '../api'
import { AuditConsole } from './AuditConsole'
import { FollowThroughPanel } from './FollowThrough'
import type { Dossier, FollowThroughView } from '../types'

vi.mock('../api', () => ({
  createEvidenceUpdate: vi.fn(), createFollowTask: vi.fn(), createOutcome: vi.fn(), createReferral: vi.fn(),
  getAudit: vi.fn(), getFollowThrough: vi.fn(), updateFollowRecord: vi.fn(),
}))

const empty: FollowThroughView = { tasks: [], referrals: [], outcomes: [], evidence_updates: [], reevaluations: [] }
const dossier = { client: { client_id: 'CL-0014' }, insights: [{ id: 'CL-0014-demo', headline: 'Funding review' }], follow_through: empty } as unknown as Dossier

describe('Follow-through roles and audit', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(getFollowThrough).mockResolvedValue(empty); vi.mocked(getAudit).mockResolvedValue({ audit: [{ id: 'a1', timestamp: '2026-08-26T10:00:00Z', origin: 'source_data', object_type: 'evidence_update', object_id: 'e1', action: 'created', actor: 'OPS-SG-001', client_id: 'CL-0014', insight_id: 'CL-0014-demo', detail: {} }] }) })
  afterEach(cleanup)

  it('lets the RM assign follow-up work but keeps specialist creation controls hidden', async () => {
    const { rerender } = render(<FollowThroughPanel dossier={dossier} role="rm" />)
    expect(await screen.findByText('Assign follow-up task')).toBeInTheDocument()
    rerender(<FollowThroughPanel dossier={dossier} role="credit" />)
    expect(screen.queryByText('Assign follow-up task')).not.toBeInTheDocument()
  })

  it('shows origin-labelled audit records and filters by origin', async () => {
    const user = userEvent.setup()
    render(<AuditConsole role="compliance_audit" />)
    expect(await screen.findByText('evidence_update · CL-0014')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Origin'), 'source_data')
    await waitFor(() => expect(getAudit).toHaveBeenLastCalledWith({ origin: 'source_data' }))
  })
})
