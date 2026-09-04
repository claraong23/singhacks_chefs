import { useState } from 'react'
import type { ActionOption, Insight, InsightStatus } from '../types'

const CHECK_MARK: Record<string, string> = {
  pass: '✓',
  fail: '✕',
  attention: '!',
  not_assessed: '–',
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
  onDecide: (input: {
    status: InsightStatus
    rmNote: string
    selectedOptionId: string | null
    editedNextStep: string | null
  }) => void
  onClose: () => void
}) {
  const [selected, setSelected] = useState<string | null>(
    insight.selected_option_id ?? null,
  )
  const [note, setNote] = useState(insight.rm_note ?? '')
  const [nextStep, setNextStep] = useState(insight.suggested_next_step)
  const [expanded, setExpanded] = useState<string | null>(options[0]?.id ?? null)

  const edited = nextStep.trim() !== insight.suggested_next_step.trim()

  return (
    <div className="card" style={{ marginTop: 14, background: 'var(--surface-sunk)' }}>
      <div className="card-head" style={{ background: 'var(--surface)' }}>
        <h2>Review and decide</h2>
        <span className="sub">
          Options for review. Clarity does not act; you do.
        </span>
      </div>
      <div className="card-body">
        {options.map((option) => {
          const isOpen = expanded === option.id
          const isSelected = selected === option.id
          return (
            <div className={`option${isSelected ? ' selected' : ''}`} key={option.id}
              style={{ background: 'var(--surface)' }}>
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
                  <div className="small muted" style={{ marginTop: 4 }}>
                    {option.rationale}
                  </div>
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
                      <ul>
                        {option.mechanics.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <div className="eyebrow" style={{ marginBottom: 6 }}>What it costs</div>
                      <ul>
                        {option.trade_offs.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <div style={{ marginTop: 14 }}>
                    <div className="eyebrow" style={{ marginBottom: 6 }}>Suitability</div>
                    {option.suitability_checks.map((check) => (
                      <div className="check" key={`${option.id}-${check.check}`}>
                        <span className={`mark ${check.result}`}>{CHECK_MARK[check.result]}</span>
                        <div>
                          <div>{check.check}</div>
                          <div className="d">{check.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {option.estimated_impact && (
                    <div className="impact">
                      <strong>Expected effect.</strong> {option.estimated_impact}
                    </div>
                  )}

                  <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {option.requires.map((requirement) => (
                      <span className="tag" key={requirement}>{requirement}</span>
                    ))}
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
          <textarea
            className="rmnote"
            value={nextStep}
            onChange={(event) => setNextStep(event.target.value)}
            aria-label="Next step"
          />
          {edited && (
            <div className="footnote">
              Original: “{insight.suggested_next_step}” — the engine's wording is kept in
              the audit trail alongside yours.
            </div>
          )}
        </div>

        <div style={{ marginTop: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Your note for the file</div>
          <textarea
            className="rmnote"
            value={note}
            placeholder="What you decided and why. This is written to the audit trail."
            onChange={(event) => setNote(event.target.value)}
            aria-label="RM note"
          />
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          <button
            className="btn primary"
            disabled={busy || !selected}
            onClick={() =>
              onDecide({
                status: 'actioned',
                rmNote: note,
                selectedOptionId: selected,
                editedNextStep: edited ? nextStep : null,
              })
            }
          >
            Approve selected option
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              onDecide({
                status: 'reviewed',
                rmNote: note,
                selectedOptionId: selected,
                editedNextStep: edited ? nextStep : null,
              })
            }
          >
            Mark reviewed, no action yet
          </button>
          <button
            className="btn"
            disabled={busy}
            onClick={() =>
              onDecide({
                status: 'dismissed',
                rmNote: note,
                selectedOptionId: null,
                editedNextStep: null,
              })
            }
          >
            Dismiss
          </button>
          <button className="btn quiet" onClick={onClose} disabled={busy}>
            Cancel
          </button>
        </div>
        {!selected && (
          <div className="footnote">
            Select an option before approving. Dismissing does not need one.
          </div>
        )}
      </div>
    </div>
  )
}
