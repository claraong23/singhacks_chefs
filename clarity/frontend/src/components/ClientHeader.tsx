import { useState } from 'react'
import type { Dossier, ClientNote, ProposedObjective } from '../types'
import { money, shortDate, usd } from '../format'
import { addClientNote, proposeObjectiveUpdate } from '../api'

interface ClientHeaderProps {
  dossier: Dossier
  onBack: () => void
  onNoteAdded?: (note: ClientNote) => void
  onObjectiveProposed?: (proposal: ProposedObjective) => void
}

export function ClientHeader({
  dossier,
  onBack,
  onNoteAdded,
  onObjectiveProposed,
}: ClientHeaderProps) {
  const [showAdminDetails, setShowAdminDetails] = useState(false)
  const [showNoteModal, setShowNoteModal] = useState(false)
  const [showObjectiveModal, setShowObjectiveModal] = useState(false)

  // Note form state
  const [noteChannel, setNoteChannel] = useState('Client Meeting')
  const [noteText, setNoteText] = useState('')
  const [noteSaving, setNoteSaving] = useState(false)
  const [noteSuccess, setNoteSuccess] = useState(false)

  // Objective proposal state
  const client = dossier.client as Record<string, string | number | null>
  const currentObjectives = String(client.objectives || '')
  const [proposedObjectives, setProposedObjectives] = useState(currentObjectives)
  const [objectiveRationale, setObjectiveRationale] = useState('')
  const [objectiveSaving, setObjectiveSaving] = useState(false)
  const [pendingProposal, setPendingProposal] = useState<ProposedObjective | null>(null)

  // Compute dual currency wealth
  const baseCurrency = String(client.base_currency || 'USD')
  let totalBaseCurrency = 0
  let hasValidBaseSum = false
  if (dossier.portfolios && dossier.portfolios.length > 0) {
    const matchingPortfolios = dossier.portfolios.filter(
      (p) => p.base_currency === baseCurrency,
    )
    if (matchingPortfolios.length === dossier.portfolios.length) {
      totalBaseCurrency = matchingPortfolios.reduce((sum, p) => {
        const latestPoint = p.aum_series[p.aum_series.length - 1]
        return sum + (latestPoint?.value_base || 0)
      }, 0)
      hasValidBaseSum = totalBaseCurrency > 0
    }
  }

  // Count active mandate breaches
  const totalBreaches = dossier.portfolios.reduce((count, p) => {
    const bandBreaches = p.mandate_review?.band_breaches.length || 0
    const posBreaches = p.mandate_review?.position_breaches.length || 0
    return count + bandBreaches + posBreaches
  }, 0)

  // Tax mismatch check
  const hasTaxMismatch =
    Boolean(client.tax_domicile) &&
    Boolean(client.country_of_residence) &&
    client.tax_domicile !== client.country_of_residence

  // KYC due check (if due within 90 days or overdue)
  const kycDue = client.kyc_review_due ? new Date(String(client.kyc_review_due)) : null
  const asOfDate = new Date(dossier.as_of)
  const isKycUrgent =
    kycDue &&
    (kycDue <= asOfDate ||
      (kycDue.getTime() - asOfDate.getTime()) / (1000 * 60 * 60 * 24) <= 90)

  // Liquidity shortfall check
  const hasLiquidityShortfall = (dossier.liquidity?.shortfall_usd || 0) > 0

  const handleSaveNote = async () => {
    if (!noteText.trim()) return
    setNoteSaving(true)
    try {
      const res = await addClientNote(
        String(client.client_id),
        noteText,
        noteChannel,
        String(client.rm_name || 'Priscilla Ong'),
      )
      if (onNoteAdded) onNoteAdded(res.note)
      setNoteText('')
      setNoteSuccess(true)
      setTimeout(() => {
        setNoteSuccess(false)
        setShowNoteModal(false)
      }, 1000)
    } catch (err) {
      alert(`Error saving note: ${String(err)}`)
    } finally {
      setNoteSaving(false)
    }
  }

  const handleProposeObjective = async () => {
    if (!proposedObjectives.trim() || !objectiveRationale.trim()) return
    setObjectiveSaving(true)
    try {
      const res = await proposeObjectiveUpdate(
        String(client.client_id),
        proposedObjectives,
        objectiveRationale,
        String(client.rm_name || 'Priscilla Ong'),
      )
      setPendingProposal(res.proposal)
      if (onObjectiveProposed) onObjectiveProposed(res.proposal)
      setTimeout(() => {
        setShowObjectiveModal(false)
      }, 1200)
    } catch (err) {
      alert(`Error proposing objective: ${String(err)}`)
    } finally {
      setObjectiveSaving(false)
    }
  }

  return (
    <div style={{ marginBottom: 22 }}>
      {/* Breadcrumb navigation */}
      <div className="crumb">
        <button onClick={onBack}>← Book</button>
        <span>/</span>
        <span>{String(client.client_name)}</span>
        <span className="muted" style={{ marginLeft: 'auto', fontSize: 12 }}>
          RM: {String(client.rm_name || 'Priscilla Ong')} ({String(client.rm_desk || 'Asia')})
        </span>
      </div>

      {/* Hero Header Card */}
      <header className="client-head">
        <div>
          <div className="eyebrow">
            {String(client.client_id)} · Client since {shortDate(String(client.client_since))} ·{' '}
            {client.age ? `${client.age} y/o ` : ''}
            {client.gender ? `(${String(client.gender)})` : ''}
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 2 }}>
            <h1>{String(client.client_name)}</h1>
            <span className="pill ghost" style={{ fontSize: 12 }}>
              {String(client.wealth_band)}
            </span>
          </div>

          {/* Key Profile Tags */}
          <div className="who" style={{ marginTop: 10 }}>
            <span className="pill ghost">
              {String(client.risk_profile)} · {client.risk_tolerance_score}/10 Risk
            </span>
            <span className="pill ghost">{String(client.life_stage)}</span>
            <span className="pill ghost">{String(client.booking_centre)} Booking</span>
            <span className="pill ghost">Base {baseCurrency}</span>
            <span className="pill ghost">Horizon {client.investment_horizon_years}y</span>
            <span className="pill ghost">Liquidity: {String(client.liquidity_needs)}</span>
            <button
              className="btn quiet"
              style={{ padding: '2px 8px', fontSize: 11 }}
              onClick={() => setShowAdminDetails((prev) => !prev)}
            >
              {showAdminDetails ? '▲ Hide Admin Info' : '▼ Admin & Domicile Details'}
            </button>
          </div>

          {/* Dynamic Alert Chips */}
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {hasTaxMismatch && (
              <span
                className="pill critical"
                title="Cross-border tax exposure requiring wealth planning verification"
              >
                ⚠️ Tax Domicile: {String(client.tax_domicile)} (Resides in{' '}
                {String(client.country_of_residence)})
              </span>
            )}
            {totalBreaches > 0 && (
              <span
                className="pill critical"
                title="Mandate asset-class band or position limit breached"
              >
                ⚠️ {totalBreaches} Mandate Breach{totalBreaches > 1 ? 'es' : ''} Active
              </span>
            )}
            {hasLiquidityShortfall && (
              <span
                className="pill critical"
                title="Confirmed cash commitments exceed readily realisable liquidity"
              >
                ⚠️ Liquidity Shortfall: {usd(dossier.liquidity.shortfall_usd)}
              </span>
            )}
            {isKycUrgent && (
              <span
                className="pill high"
                title="Periodic KYC review deadline approaching or overdue"
              >
                ⏰ KYC Due: {shortDate(String(client.kyc_review_due))}
              </span>
            )}
            {client.reporting_language && client.reporting_language !== 'English' && (
              <span
                className="pill high"
                title="Preferred reporting language requires language preview check"
              >
                🌐 Prefers {String(client.reporting_language)} Communication
              </span>
            )}
          </div>

          {/* Objectives & Action Buttons */}
          <div
            style={{
              marginTop: 14,
              padding: '12px 14px',
              background: 'var(--surface)',
              border: '1px solid var(--rule)',
              borderRadius: 'var(--radius)',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: 12,
              }}
            >
              <div>
                <strong style={{ color: 'var(--ink)' }}>Primary Objectives:</strong>{' '}
                <span style={{ color: 'var(--ink-soft)' }}>
                  {pendingProposal
                    ? pendingProposal.proposed_objectives
                    : String(client.objectives || 'Preserve capital and support future commitments.')}
                </span>
                {pendingProposal && (
                  <div
                    style={{
                      marginTop: 4,
                      fontSize: 11.5,
                      color: 'var(--high)',
                      fontStyle: 'italic',
                    }}
                  >
                    ⏳ Objective update proposed by {pendingProposal.rm_name} (Pending governance
                    acknowledgement)
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  className="btn"
                  style={{ fontSize: 11.5, padding: '3px 8px' }}
                  onClick={() => setShowObjectiveModal(true)}
                >
                  ✏️ Propose Update
                </button>
                <button
                  className="btn primary"
                  style={{ fontSize: 11.5, padding: '3px 9px' }}
                  onClick={() => setShowNoteModal(true)}
                >
                  📝 Add RM Note
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Total Wealth & Dual Currency Panel */}
        <div className="card">
          <div className="card-body">
            <div className="stat" style={{ marginBottom: 12 }}>
              <span className="v">
                {hasValidBaseSum && baseCurrency !== 'USD'
                  ? money(totalBaseCurrency, baseCurrency)
                  : usd(dossier.wealth.total_usd)}
              </span>
              <span className="k">
                {hasValidBaseSum && baseCurrency !== 'USD' ? (
                  <>
                    Dual Currency: <strong>{usd(dossier.wealth.total_usd)}</strong>
                    <br />
                  </>
                ) : null}
                Across {dossier.portfolios.length} portfolio
                {dossier.portfolios.length === 1 ? '' : 's'} as at {shortDate(dossier.as_of)}
              </span>
            </div>

            <table className="kv">
              <tbody>
                <tr>
                  <td>YTD Performance</td>
                  <td
                    style={{ textAlign: 'right' }}
                    className={dossier.explanation.ytd.change_usd >= 0 ? 'pos' : 'neg'}
                  >
                    {dossier.explanation.ytd.change_usd >= 0 ? '+' : '−'}
                    {usd(Math.abs(dossier.explanation.ytd.change_usd))} (
                    {dossier.explanation.ytd.change_pct !== null
                      ? `${(dossier.explanation.ytd.change_pct).toFixed(1)}%`
                      : '—'}
                    )
                  </td>
                </tr>
                <tr>
                  <td>Realisable (1 wk)</td>
                  <td style={{ textAlign: 'right' }}>
                    {usd(dossier.liquidity.readily_realisable_usd)}
                  </td>
                </tr>
                <tr>
                  <td>Annualised Income</td>
                  <td style={{ textAlign: 'right' }}>
                    {usd(dossier.income.annualised_gross_usd)}
                  </td>
                </tr>
                <tr>
                  <td>KYC Review</td>
                  <td style={{ textAlign: 'right' }}>
                    {shortDate(String(client.kyc_review_due))}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </header>

      {/* Expandable Administrative Details Drawer */}
      {showAdminDetails && (
        <div
          className="card"
          style={{
            marginBottom: 20,
            background: 'var(--surface-sunk)',
            borderLeft: '3px solid var(--accent)',
            animation: 'fade 150ms ease-out',
          }}
        >
          <div className="card-head" style={{ padding: '10px 16px' }}>
            <h2 style={{ fontSize: 13 }}>Administrative & Compliance Dossier</h2>
            <button
              className="btn quiet"
              style={{ marginLeft: 'auto', fontSize: 11 }}
              onClick={() => setShowAdminDetails(false)}
            >
              Close
            </button>
          </div>
          <div className="card-body" style={{ padding: '14px 16px' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 16,
                fontSize: 12.5,
              }}
            >
              <div>
                <span className="muted">Managing RM:</span>{' '}
                <strong>{String(client.rm_name || 'Priscilla Ong')}</strong> (
                {String(client.rm_id || 'RM-014')})
              </div>
              <div>
                <span className="muted">RM Desk:</span>{' '}
                <strong>{String(client.rm_desk || 'Asia Desk')}</strong>
              </div>
              <div>
                <span className="muted">Nationality:</span>{' '}
                <strong>{String(client.nationality || '—')}</strong>
              </div>
              <div>
                <span className="muted">Country of Residence:</span>{' '}
                <strong>{String(client.country_of_residence || '—')}</strong>
              </div>
              <div>
                <span className="muted">Tax Domicile:</span>{' '}
                <strong>{String(client.tax_domicile || '—')}</strong>
              </div>
              <div>
                <span className="muted">Reporting Language:</span>{' '}
                <strong>{String(client.reporting_language || 'English')}</strong>
              </div>
              <div>
                <span className="muted">Booking Centre:</span>{' '}
                <strong>{String(client.booking_centre || 'Singapore')}</strong>
              </div>
              <div>
                <span className="muted">Source of Wealth:</span>{' '}
                <strong>{String(client.source_of_wealth || '—')}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add RM Note Modal */}
      {showNoteModal && (
        <div className="drawer-backdrop" onClick={() => setShowNoteModal(false)}>
          <div
            className="card"
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 'min(520px, 94vw)',
              zIndex: 100,
              boxShadow: '0 12px 36px rgba(0,0,0,0.25)',
              background: 'var(--surface)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-head">
              <h2>Add RM Relationship Note</h2>
              <span className="sub">{String(client.client_name)}</span>
            </div>
            <div className="card-body">
              {noteSuccess ? (
                <div
                  className="banner"
                  style={{
                    background: 'var(--positive-wash, #edf8f3)',
                    color: 'var(--positive)',
                    borderColor: '#c3e6d6',
                  }}
                >
                  ✓ Note saved to client profile and review trail.
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: 12 }}>
                    <label
                      htmlFor="note-channel-select"
                      className="k"
                      style={{ display: 'block', marginBottom: 4 }}
                    >
                      Interaction Channel:
                    </label>
                    <select
                      id="note-channel-select"
                      className="select"
                      value={noteChannel}
                      onChange={(e) => setNoteChannel(e.target.value)}
                    >
                      <option value="Client Meeting">Client Meeting (In-Person / Zoom)</option>
                      <option value="Phone Call">Phone Call</option>
                      <option value="Email / WhatsApp">Email / Client Message</option>
                      <option value="Portfolio Review">Internal Portfolio Review</option>
                    </select>
                  </div>
                  <div style={{ marginBottom: 16 }}>
                    <label
                      htmlFor="rm-note-textarea"
                      className="k"
                      style={{ display: 'block', marginBottom: 4 }}
                    >
                      Note Details:
                    </label>
                    <textarea
                      id="rm-note-textarea"
                      className="rmnote"
                      rows={4}
                      placeholder="e.g. Discussed upcoming tax instalment due Q3 2026. Client expressed preference to de-risk equity overweight before year end."
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'flex-end',
                      gap: 8,
                    }}
                  >
                    <button
                      className="btn quiet"
                      onClick={() => setShowNoteModal(false)}
                      disabled={noteSaving}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn primary"
                      onClick={handleSaveNote}
                      disabled={noteSaving || !noteText.trim()}
                    >
                      {noteSaving ? 'Saving…' : 'Save Note'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Propose Objective Update Modal */}
      {showObjectiveModal && (
        <div className="drawer-backdrop" onClick={() => setShowObjectiveModal(false)}>
          <div
            className="card"
            style={{
              position: 'fixed',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              width: 'min(560px, 94vw)',
              zIndex: 100,
              boxShadow: '0 12px 36px rgba(0,0,0,0.25)',
              background: 'var(--surface)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-head">
              <h2>Propose Objective Update (Governance Review)</h2>
              <span className="sub">{String(client.client_name)}</span>
            </div>
            <div className="card-body">
              <div
                style={{
                  fontSize: 12,
                  marginBottom: 12,
                  color: 'var(--muted)',
                }}
              >
                In private banking, formal mandate and profile objectives require supervisory review
                before legal binding rebalancing. This proposal will be attached to Priscilla's
                audit history.
              </div>

              <div style={{ marginBottom: 12 }}>
                <span className="k" style={{ display: 'block', marginBottom: 4 }}>
                  Current Registered Objectives:
                </span>
                <div
                  style={{
                    padding: '8px 10px',
                    background: 'var(--surface-sunk)',
                    fontSize: 12.5,
                    border: '1px solid var(--rule)',
                  }}
                >
                  {currentObjectives}
                </div>
              </div>

              <div style={{ marginBottom: 12 }}>
                <label
                  htmlFor="proposed-objectives-input"
                  className="k"
                  style={{ display: 'block', marginBottom: 4 }}
                >
                  Proposed Revised Objectives:
                </label>
                <textarea
                  id="proposed-objectives-input"
                  className="rmnote"
                  rows={3}
                  value={proposedObjectives}
                  onChange={(e) => setProposedObjectives(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: 16 }}>
                <label
                  htmlFor="objective-rationale-input"
                  className="k"
                  style={{ display: 'block', marginBottom: 4 }}
                >
                  RM Rationale & Client Consultation Notes:
                </label>
                <textarea
                  id="objective-rationale-input"
                  className="rmnote"
                  rows={2}
                  placeholder="e.g. Client confirmed conservative risk tolerance and stated inheritance tax liability due 2026."
                  value={objectiveRationale}
                  onChange={(e) => setObjectiveRationale(e.target.value)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button
                  className="btn quiet"
                  onClick={() => setShowObjectiveModal(false)}
                  disabled={objectiveSaving}
                >
                  Cancel
                </button>
                <button
                  className="btn primary"
                  onClick={handleProposeObjective}
                  disabled={
                    objectiveSaving ||
                    !proposedObjectives.trim() ||
                    !objectiveRationale.trim()
                  }
                >
                  {objectiveSaving ? 'Submitting…' : 'Submit Proposal'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
