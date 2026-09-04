import { useEffect } from 'react'
import type { Insight } from '../types'
import { CONFIDENCE_HINT, CONFIDENCE_LABEL, titleCase } from '../format'

const CHECK_MARK: Record<string, string> = {
  pass: '✓',
  fail: '✕',
  attention: '!',
  not_assessed: '–',
}

export function EvidenceDrawer({
  insight,
  onClose,
}: {
  insight: Insight
  onClose: () => void
}) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Evidence">
        <div className="drawer-head">
          <div style={{ flex: 1 }}>
            <div className="eyebrow">Evidence and basis</div>
            <h3 style={{ fontSize: 15, marginTop: 6, lineHeight: 1.35 }}>{insight.headline}</h3>
          </div>
          <button className="btn quiet" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>

        <div className="drawer-body">
          <section style={{ marginBottom: 26 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Why this ranks where it does</div>
            <ul className="brieflist">
              {insight.priority_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <div className="footnote">
              Score {insight.priority_score.toFixed(1)} of 100 = 0.45 × severity + 0.30 ×
              materiality + 0.25 × urgency. The weights are a judgement and are published
              so they can be argued with. Active weights are shown in the Morning Book and Calibration Lab.
            </div>
            {insight.priority_factors && <div className="footnote" style={{ marginTop: 6 }}>Immutable score inputs: severity weight {insight.priority_factors.severity_weight.toFixed(2)} · materiality {insight.priority_factors.materiality_pct === null ? 'not quantified' : `${insight.priority_factors.materiality_pct.toFixed(1)}%`} · urgency {insight.priority_factors.days_until === null ? 'no dated deadline' : `${insight.priority_factors.days_until} days`}.</div>}
          </section>

          <section style={{ marginBottom: 26 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              Confidence: {CONFIDENCE_LABEL[insight.confidence]}
            </div>
            <p className="small muted" style={{ margin: 0 }}>
              {CONFIDENCE_HINT[insight.confidence]}
            </p>
          </section>

          {insight.suitability_checks.length > 0 && (
            <section style={{ marginBottom: 26 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Suitability checks</div>
              {insight.suitability_checks.map((check) => (
                <div className="check" key={check.check}>
                  <span className={`mark ${check.result}`}>{CHECK_MARK[check.result]}</span>
                  <div>
                    <div>{check.check}</div>
                    <div className="d">{check.detail}</div>
                    {check.reference && <div className="d">Source: {check.reference}</div>}
                  </div>
                </div>
              ))}
            </section>
          )}

          {insight.assumptions.length > 0 && (
            <section style={{ marginBottom: 26 }}>
              <div className="eyebrow" style={{ marginBottom: 10 }}>Assumptions</div>
              {insight.assumptions.map((assumption) => (
                <div className="assumption" key={assumption.statement}>
                  <div>{assumption.statement}</div>
                  <div className="b">Basis: {assumption.basis}</div>
                  {assumption.impact_if_wrong && (
                    <div className="b">If wrong: {assumption.impact_if_wrong}</div>
                  )}
                </div>
              ))}
            </section>
          )}

          {insight.open_questions.length > 0 && (
            <section style={{ marginBottom: 26 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>What we could not settle from the data</div>
              <ul className="brieflist">
                {insight.open_questions.map((question) => (
                  <li key={question}>{question}</li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              Source rows ({insight.evidence.length})
            </div>
            {insight.evidence.map((item, index) => (
              <div className="evidence" key={`${item.source_file}-${item.row_or_id}-${item.field}-${index}`}>
                <div>
                  <span className="src">{item.source_file}</span>
                  <span className="fld"> · {item.row_or_id} · {item.field}</span>
                  {item.snapshot_date && <span className="fld"> · {item.snapshot_date}</span>}
                </div>
                <div className="val">{String(item.value)}</div>
                {item.note && <div className="note">{item.note}</div>}
              </div>
            ))}
            {insight.evidence.length === 0 && (
              <p className="small muted">
                No source rows attached. This finding is derived from the client profile
                alone.
              </p>
            )}
          </section>

          {insight.related_event_ids.length > 0 && (
            <p className="footnote">
              Linked events: {insight.related_event_ids.join(', ')} — see the event log on
              the “What changed” tab. Event descriptions come from event_log.csv, which is
              the authoritative source for 2026.
            </p>
          )}

          <p className="footnote">
            Category {titleCase(insight.category)} · insight id {insight.id}
          </p>
        </div>
      </aside>
    </>
  )
}
