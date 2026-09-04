import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createMeetingPackage, getMeetingPackages, handoffMeetingPackage, preflightMeetingPackage,
  regenerateMeetingSection, saveMeetingSection,
} from '../api'
import { MeetingStudio } from './MeetingStudio'
import type { Dossier, MeetingPackage } from '../types'

vi.mock('../api', () => ({
  createMeetingPackage: vi.fn(), getMeetingPackages: vi.fn(), handoffMeetingPackage: vi.fn(),
  preflightMeetingPackage: vi.fn(), regenerateMeetingSection: vi.fn(),
  restoreMeetingVersion: vi.fn(), saveMeetingSection: vi.fn(),
}))

const insight = {
  id: 'CL-0014-demo', client_id: 'CL-0014', category: 'liquidity', severity: 'high', headline: 'Confirm funding plan', summary: '', priority_score: 90, priority_reasons: [], observed_facts: [], client_relevance: 'the redevelopment funding plan', suggested_next_step: 'Arrange a meeting.', evidence: [], assumptions: [], suitability_checks: [], confidence: 'measured', open_questions: [], related_event_ids: [], portfolio_ids: [], instrument_ids: [], amount_usd: null, status: 'client_ready' as const,
}

const dossier = { client: { client_id: 'CL-0014' }, insights: [insight] } as unknown as Dossier

function packageFixture(): MeetingPackage {
  const refs = ['clients.csv:CL-0014']
  return {
    id: 'meeting-1', client_id: 'CL-0014', insight_id: insight.id, state: 'draft', created_at: '2026-08-26T09:00:00Z', created_by: 'RM-SG-014', current_version: 1,
    source: { decision_status: 'client_ready', selected_option_id: 'option-1', selected_scenario_id: null, scenario_calculation_version: null, evidence_version: 'v1', gate_snapshot: [{ status: 'pass' }], evidence: [{ source_file: 'clients.csv', row_or_id: 'CL-0014', field: 'objectives', value: 'Preserve capital', snapshot_date: null, note: null }] },
    versions: [{ id: 'version-1', version: 1, created_at: '2026-08-26T09:00:00Z', actor: 'RM-SG-014', reason: 'generated', sections: [{ key: 'objective', title: 'Meeting objective', content: 'Confirm objective.', evidence_refs: refs }], communications: [{ channel: 'email', label: 'Concise email', content: 'This is not a recommendation. Information is as at 2026-08-26.', evidence_refs: refs }] }], handoffs: [],
  }
}

describe('MeetingStudio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getMeetingPackages).mockResolvedValue({ packages: [] })
  })
  afterEach(cleanup)

  it('explains why a client-facing package cannot exist before client-ready', () => {
    render(<MeetingStudio dossier={{ ...dossier, insights: [{ ...insight, status: 'under_review' }] } as unknown as Dossier} />)
    expect(screen.getByText('No client-ready findings are available for this client.')).toBeInTheDocument()
  })

  it('creates, preflights, copies, and records a simulated hand-off', async () => {
    const item = packageFixture()
    vi.mocked(createMeetingPackage).mockResolvedValue({ package: item })
    vi.mocked(preflightMeetingPackage).mockResolvedValue({ preflight: { can_hand_off: true, checked_at: '2026-08-26T09:05:00Z', checks: [{ id: 'evidence', label: 'Evidence', status: 'pass', detail: 'Cited.' }] } })
    vi.mocked(handoffMeetingPackage).mockResolvedValue({ package: { ...item, state: 'handed_off', handoffs: [{ id: 'handoff-1', package_id: item.id, channel: 'email', actor: 'RM-SG-014', created_at: '2026-08-26T09:06:00Z', preflight_version: 1 }] } })
    const user = userEvent.setup()
    render(<MeetingStudio dossier={dossier} />)
    await user.click(await screen.findByRole('button', { name: /Create package/ }))
    await user.click(screen.getByRole('button', { name: 'Run communication preflight' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Copy client-ready draft' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Copy client-ready draft' }))
    expect(await screen.findByText(/Copied client-ready draft|Clipboard access was unavailable/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Record simulated hand-off' }))
    expect(handoffMeetingPackage).toHaveBeenCalledWith('meeting-1', 'email')
    expect(await screen.findByText(/Nothing was sent/)).toBeInTheDocument()
  })

  it('saves source-aware edits and offers deterministic regeneration', async () => {
    const item = packageFixture()
    vi.mocked(getMeetingPackages).mockResolvedValue({ packages: [item] })
    vi.mocked(saveMeetingSection).mockResolvedValue({ package: { ...item, current_version: 2, versions: [...item.versions, { ...item.versions[0], id: 'version-2', version: 2, reason: 'RM edit' }] } })
    vi.mocked(regenerateMeetingSection).mockResolvedValue({ package: item })
    const user = userEvent.setup()
    render(<MeetingStudio dossier={dossier} />)
    const editor = await screen.findByLabelText('Meeting objective')
    await user.clear(editor); await user.type(editor, 'Confirm revised objective.'); await user.tab()
    await waitFor(() => expect(saveMeetingSection).toHaveBeenCalled())
    await user.click(screen.getByRole('button', { name: 'Reset deterministic wording' }))
    expect(regenerateMeetingSection).toHaveBeenCalledWith('meeting-1', 'objective')
  })
})
