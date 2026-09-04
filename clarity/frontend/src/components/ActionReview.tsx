import { useEffect, useState } from 'react'
import { getDecisionReadiness } from '../api'
import type { ActionOption, DecisionReadiness, Insight, InsightStatus } from '../types'

const TERMINAL: InsightStatus[] = ['client_ready', 'deferred', 'dismissed']

type DecisionInput = {
  status: InsightStatus
  rmNote: string
  selectedOptionId: string | null
  editedNextStep: string | null
}

export function ActionReview({
  insight,
  options,
  busy,
  onDecide,
  onClose,
}: {
  insight: Insight
  options: ActionOption[]
  busy: boolean
  onDecide: (input: DecisionInput) => Promise<void>
  onClose: () => void
}) {
  const [selected, setSelected] = useState<string | null>(insight.selected_option_id ?? null)
  const [note, setNote] = useState(insight.rm_note ?? '')
  const [nextStep, setNextStep] = useState(insight.suggested_next_step)
  const [expanded, setExpanded] = useState<string | null>(options[0]?.id ?? null)
  const [readiness, setReadiness] = useState<DecisionReadiness | null>(null)
  const [readinessError, setReadinessError] = useState<string | null>(null)

  const edited = nextStep.trim() !== insight.suggested_next_step.trim()
  const canWork = ['under_review', 'rm_edited', 'rm_reviewed'].includes(insight.status)
  const isTerminal = TERMINAL.includes(insight.status)
  const hasDraftChanges = Boolean(selected || note.trim() || edited)

  useEffect(() => {
    let active = true
    void getDecisionReadiness(insight.id, {
      clientId: insight.client_id,
      selectedOptionId: selected,
      rmNote: note,
      editedNextStep: edited ? nextStep : null,
    })
      .then((result) => {
        if (active) {
          setReadiness(result)
          setReadinessError(null)
        }
      })
      .catch((error: unknown) => {
        if (active) setReadinessError(String(error))
      })
    return () => {
      active = false
    }
  }, [edited, insight.client_id, insight.id, nextStep, note, selected])

  const submit = async (status: InsightStatus) => {
    await onDecide({
      status,
      rmNote: note,
      selectedOptionId: selected,
      editedNextStep: nextStep.trim() ? nextStep : null,
    })
  }

  return (
    <div className="card" style={{ marginTop: 14, background: 'var(--surface-sunk)' }}>
      <div className="card-head" style={{ background: 'var(--surface)' }}>
        <h2>Review and decide</h2>
        <span className="sub">Options are for RM review. Clarity does not send, advise, or execute.</span>
      </div>
      <div className="card-body">
        {insight.status === 'opened' && (
          <div className="banner" style={{ marginBottom: 16 }}>
            <strong>Finding opened.</strong> Start RM review to compare options and record a controlled outcome.
            <div style={{ marginTop: 10 }}>
              <button className="btn primary" disabled={busy} onClick={() => void submit('under_review')}>
                Start RM review
              </button>
            </div>
          </div>
        )}

        {insight.status === 'escalated' && (
          <div className="banner" style={{ marginBottom: 16 }}>
            <strong>Specialist review pending.</strong> Keep this item out of client-ready status until it returns to the RM.
            <div style={{ marginTop: 10 }}>
              <button className="btn" disabled={busy} onClick={() => void submit('returned_for_review')}>
                Record return to RM
              </button>
            </div>
          </div>
        )}

        {insight.status === 'returned_for_review' && (
          <div className="banner" style={{ marginBottom: 16 }}>
            <strong>Returned for review.</strong> Resume RM review before another decision is made.
            <div style={{ marginTop: 10 }}>
              <button className="btn primary" disabled={busy} onClick={() => void submit('under_review')}>
                Resume RM review
              </button>
            </div>
          </div>
        )}

        {isTerminal && (
          <div className="banner" style={{ marginBottom: 16 }}>
            <strong>Controlled outcome recorded.</strong> This item is {insight.status.replace('_', ' ')} and cannot be changed from the workbench.
          </div>
        )}

        {canWork && (
          <>
            {/* Open-Ended RM Advisory Action Box */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6 }}>
                <label
                  htmlFor={`nextstep-${insight.id}`}
                  className="eyebrow"
                  style={{ color: 'var(--accent)', fontSize: 11.5 }}
                >
                  ✍️ What action should be taken? (RM Advisory Directive)
                </label>
                {edited && (
                  <span className="pill accent" style={{ fontSize: 10.5 }}>
                    RM Custom Directive
                  </span>
                )}
              </div>
              <textarea
                id={`nextstep-${insight.id}`}
                className="rmnote"
                rows={4}
                style={{ minHeight: 90, fontSize: 13, lineHeight: 1.5 }}
                value={nextStep}
                onChange={(event) => setNextStep(event.target.value)}
                placeholder="Type your tailored conversation plan, action directive, or proposal for this client…"
                aria-label="Next step"
              />
              {edited && (
                <div className="footnote" style={{ marginTop: 4 }}>
                  Customized by RM. The original playbook suggestion is preserved in the compliance audit trail.
                </div>
              )}
            </div>

            {/* Open-Ended RM Rationale Box */}
            <div style={{ marginBottom: 16 }}>
              <label
                htmlFor={`note-${insight.id}`}
                className="eyebrow"
                style={{ display: 'block', marginBottom: 6, fontSize: 11.5 }}
              >
                📝 RM Decision Rationale & File Note
              </label>
              <textarea
                id={`note-${insight.id}`}
                className="rmnote"
                rows={3}
                value={note}
                placeholder="Document what you decided and why (e.g. client context, family preferences, risk constraints). Required for compliance and audit trail."
                onChange={(event) => setNote(event.target.value)}
                aria-label="RM rationale"
              />
            </div>

            {/* Optional Collapsible Bank Reference Ideas */}
            {options.length > 0 && (
              <div
                className="card"
                style={{
                  marginBottom: 16,
                  background: 'var(--surface)',
                  border: '1px solid var(--rule)',
                }}
              >
                <div
                  className="card-head"
                  style={{ padding: '10px 14px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  onClick={() => setExpanded((prev) => (prev ? null : options[0]?.id ?? 'open'))}
                >
                  <h4 style={{ fontSize: 12.5, margin: 0, fontWeight: 600 }}>
                    💡 Bank Reference Strategies & Playbook Guidance ({options.length} ideas)
                  </h4>
                  <button
                    className="btn quiet"
                    style={{ marginLeft: 'auto', fontSize: 11 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setExpanded((prev) => (prev ? null : options[0]?.id ?? 'open'))
                    }}
                  >
                    {expanded ? '▲ Hide ideas' : '▼ Browse ideas'}
                  </button>
                </div>

                {expanded && (
                  <div className="card-body" style={{ padding: '12px 14px' }}>
                    <p className="footnote" style={{ marginTop: 0, marginBottom: 10 }}>
                      These reference strategies are calculated from bank playbook rules. You can adopt any strategy as a starting baseline into your action plan above, or write your own custom plan.
                    </p>
                    <div className="stack" style={{ gap: 10 }}>
                      {options.map((option) => (
                        <div
                          key={option.id}
                          className="card"
                          style={{
                            padding: '10px 12px',
                            border: selected === option.id ? '1px solid var(--accent)' : '1px solid var(--rule)',
                            background: selected === option.id ? 'var(--accent-wash)' : 'var(--surface-sunk)',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                            <div>
                              <strong style={{ fontSize: 13 }}>{option.label}</strong>
                              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{option.rationale}</div>
                            </div>
                            <button
                              className="btn"
                              style={{ fontSize: 11, padding: '3px 8px', flexShrink: 0 }}
                              onClick={() => {
                                setSelected(option.id)
                                setNextStep(`${option.label}. ${option.rationale} Next steps: ${option.mechanics.join(' ')}`)
                                if (!note.trim()) {
                                  setNote(`Adopted bank playbook strategy: ${option.label}. Fits client's current profile.`)
                                }
                              }}
                            >
                              📥 Adopt as my plan
                            </button>
                          </div>
                          {/* Mechanics & trade offs preview */}
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 8, fontSize: 11.5 }}>
                            <div>
                              <span className="muted" style={{ fontWeight: 600 }}>Mechanics:</span>
                              <ul style={{ margin: '2px 0 0', paddingLeft: 16 }}>
                                {option.mechanics.slice(0, 2).map((m, i) => <li key={i}>{m}</li>)}
                              </ul>
                            </div>
                            <div>
                              <span className="muted" style={{ fontWeight: 600 }}>Trade-offs:</span>
                              <ul style={{ margin: '2px 0 0', paddingLeft: 16 }}>
                                {option.trade_offs.slice(0, 2).map((t, i) => <li key={i}>{t}</li>)}
                              </ul>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="card" style={{ marginTop: 16, background: 'var(--surface)' }}>
              <div className="card-head"><h3>Client-ready checks</h3><span className="sub">Strict controls — no overrides</span></div>
              <div className="card-body">
                {readiness?.gates.map((gate) => (
                  <div className="check" key={gate.id}>
                    <span className={`mark ${gate.status === 'pass' ? 'pass' : 'fail'}`}>{gate.status === 'pass' ? '✓' : '!'}</span>
                    <div><div>{gate.label}</div><div className="d">{gate.detail}</div></div>
                  </div>
                ))}
                {readinessError && <div className="footnote">Could not refresh controls: {readinessError}</div>}
                {!readiness && !readinessError && <div className="footnote">Checking the current selection against source evidence and controls…</div>}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
              {insight.status !== 'rm_reviewed' && (
                <button className="btn" disabled={busy || !hasDraftChanges} onClick={() => void submit('rm_edited')}>
                  Save review draft
                </button>
              )}
              {insight.status !== 'rm_reviewed' && (
                <button className="btn" disabled={busy} onClick={() => void submit('rm_reviewed')}>
                  Mark RM review complete
                </button>
              )}
              {insight.status === 'rm_reviewed' && (
                <button className="btn" disabled={busy} onClick={() => void submit('rm_reviewed')}>
                  Update review plan & notes
                </button>
              )}
              {insight.status === 'rm_reviewed' && (
                <button
                  className="btn primary"
                  disabled={busy || !readiness?.can_mark_client_ready}
                  onClick={() => void submit('client_ready')}
                >
                  Mark client-ready
                </button>
              )}
              <button className="btn" disabled={busy || !note.trim()} onClick={() => void submit('escalated')}>Escalate</button>
              <button className="btn" disabled={busy || !note.trim()} onClick={() => void submit('deferred')}>Defer</button>
              <button className="btn" disabled={busy || !note.trim()} onClick={() => void submit('dismissed')}>Dismiss</button>
            </div>
            {insight.status === 'rm_reviewed' && readiness && !readiness.can_mark_client_ready && (
              <div className="footnote">Resolve the blocking checks, or record escalation, deferral, or dismissal. Client-ready remains unavailable.</div>
            )}
          </>
        )}

        <div style={{ marginTop: 14 }}><button className="btn quiet" onClick={onClose} disabled={busy}>Close review</button></div>
      </div>
    </div>
  )
}
