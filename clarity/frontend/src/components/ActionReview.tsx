import { useEffect, useState } from 'react'
import { getDecisionReadiness } from '../api'
import type { ActionOption, DecisionReadiness, Insight, InsightStatus } from '../types'

const CHECK_MARK: Record<string, string> = {
  pass: '✓',
  fail: '✕',
  attention: '!',
  not_assessed: '–',
}

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
      editedNextStep: edited ? nextStep : null,
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
            {options.map((option) => {
              const isOpen = expanded === option.id
              const isSelected = selected === option.id
              return (
                <div className={`option${isSelected ? ' selected' : ''}`} key={option.id} style={{ background: 'var(--surface)' }}>
                  <div className="option-head">
                    <input
                      type="radio"
                      name={`option-${insight.id}`}
                      checked={isSelected}
                      onChange={() => {
                        setSelected(option.id)
                        setExpanded(option.id)
                      }}
                      style={{ marginTop: 3 }}
                      aria-label={`Select: ${option.label}`}
                    />
                    <div style={{ flex: 1 }}>
                      <h4>{option.label}</h4>
                      <div className="small muted" style={{ marginTop: 4 }}>{option.rationale}</div>
                    </div>
                    <button className="btn quiet" onClick={() => setExpanded(isOpen ? null : option.id)}>
                      {isOpen ? 'Hide detail' : 'Detail'}
                    </button>
                  </div>

                  {isOpen && (
                    <div className="option-body">
                      <div className="option-cols">
                        <div>
                          <div className="eyebrow" style={{ marginBottom: 6 }}>How it would work</div>
                          <ul>{option.mechanics.map((step) => <li key={step}>{step}</li>)}</ul>
                        </div>
                        <div>
                          <div className="eyebrow" style={{ marginBottom: 6 }}>What it costs</div>
                          <ul>{option.trade_offs.map((item) => <li key={item}>{item}</li>)}</ul>
                        </div>
                      </div>
                      <div style={{ marginTop: 14 }}>
                        <div className="eyebrow" style={{ marginBottom: 6 }}>Suitability</div>
                        {option.suitability_checks.map((check) => (
                          <div className="check" key={`${option.id}-${check.check}`}>
                            <span className={`mark ${check.result}`}>{CHECK_MARK[check.result]}</span>
                            <div><div>{check.check}</div><div className="d">{check.detail}</div></div>
                          </div>
                        ))}
                      </div>
                      {option.estimated_impact && <div className="impact"><strong>Expected effect.</strong> {option.estimated_impact}</div>}
                      <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {option.requires.map((requirement) => <span className="tag" key={requirement}>{requirement}</span>)}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}

            <div style={{ marginTop: 18 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>
                Next step {edited && <span className="pill accent" style={{ marginLeft: 6 }}>edited</span>}
              </div>
              <textarea className="rmnote" value={nextStep} onChange={(event) => setNextStep(event.target.value)} aria-label="Next step" />
              {edited && <div className="footnote">The original engine wording stays in the audit trail alongside the RM edit.</div>}
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>RM rationale</div>
              <textarea
                className="rmnote"
                value={note}
                placeholder="What you decided and why. Required for client-ready, escalation, deferral, and dismissal."
                onChange={(event) => setNote(event.target.value)}
                aria-label="RM rationale"
              />
            </div>

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
