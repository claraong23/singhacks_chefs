import { useState } from 'react'
import type { ActionOption, Insight, InsightStatus } from '../types'
import { CONFIDENCE_LABEL, SEVERITY_LABEL, titleCase, usd } from '../format'
import { ActionReview } from './ActionReview'

const STATUS_LABEL: Record<InsightStatus, string> = {
  new: 'New',
  reviewed: 'Reviewed',
  dismissed: 'Dismissed',
  actioned: 'Actioned',
}

export function InsightCard({
  insight,
  options,
  busy,
  onEvidence,
  onDecide,
}: {
  insight: Insight
  options: ActionOption[]
  busy: boolean
  onEvidence: (insight: Insight) => void
  onDecide: (
    insight: Insight,
    input: {
      status: InsightStatus
      rmNote: string
      selectedOptionId: string | null
      editedNextStep: string | null
    },
  ) => void
}) {
  const [showFacts, setShowFacts] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const chosen = options.find((option) => option.id === insight.selected_option_id)

  return (
    <article className={`insight ${insight.severity}${insight.status === 'dismissed' ? ' dismissed' : ''}`}>
      <div className="insight-head">
        <div className="score" title="Priority score out of 100">
          {insight.priority_score.toFixed(0)}
        </div>
        <div style={{ flex: 1 }}>
          <h3>{insight.headline}</h3>
          <div className="meta">
            <span className={`pill ${insight.severity}`}>{SEVERITY_LABEL[insight.severity]}</span>
            <span className="tag">{titleCase(insight.category)}</span>
            <span className="tag" title="How much of this rests on measurement rather than a client statement">
              {CONFIDENCE_LABEL[insight.confidence]}
            </span>
            {insight.amount_usd !== null && (
              <span className="tag">{usd(insight.amount_usd)}</span>
            )}
            {insight.status !== 'new' && (
              <span className="pill accent">{STATUS_LABEL[insight.status]}</span>
            )}
            {insight.edited && <span className="pill ghost">RM edited</span>}
          </div>
        </div>
      </div>

      <p className="insight-summary">{insight.summary}</p>

      {insight.client_relevance && (
        <p className="insight-summary" style={{ paddingTop: 0, color: 'var(--muted)', fontSize: 13 }}>
          {insight.client_relevance}
        </p>
      )}

      {showFacts && insight.observed_facts.length > 0 && (
        <div className="facts">
          {insight.observed_facts.map((fact, index) => (
            <div className="fact" key={`${fact.label}-${index}`}>
              <div className="k">{fact.label}</div>
              <div className="v">{fact.value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="nextstep">
        <strong>Suggested next step.</strong> {insight.suggested_next_step}
        {insight.suggested_next_step_original && (
          <div className="footnote" style={{ marginTop: 6 }}>
            Engine wording, replaced by the RM: “{insight.suggested_next_step_original}”
          </div>
        )}
      </div>

      {insight.rm_note && (
        <div className="nextstep" style={{ background: 'var(--surface-sunk)', borderLeftColor: 'var(--rule-strong)' }}>
          <strong>RM note.</strong> {insight.rm_note}
          {insight.decided_at && (
            <div className="footnote" style={{ marginTop: 5 }}>
              {insight.decided_by} · {insight.decided_at}
              {chosen ? ` · chose “${chosen.label}”` : ''}
            </div>
          )}
        </div>
      )}

      <div className="insight-foot">
        <button className="btn" onClick={() => setShowFacts((value) => !value)}>
          {showFacts ? 'Hide figures' : `Figures (${insight.observed_facts.length})`}
        </button>
        <button className="btn" onClick={() => onEvidence(insight)}>
          Evidence ({insight.evidence.length})
        </button>
        <button
          className={`btn${reviewing ? '' : ' primary'}`}
          onClick={() => setReviewing((value) => !value)}
        >
          {reviewing ? 'Close review' : `Review options (${options.length})`}
        </button>
        <span className="footnote" style={{ marginLeft: 'auto' }}>
          Options for RM review. Nothing is executed by the system.
        </span>
      </div>

      {reviewing && (
        <div style={{ padding: '0 18px 18px 70px' }}>
          <ActionReview
            insight={insight}
            options={options}
            busy={busy}
            onClose={() => setReviewing(false)}
            onDecide={(input) => {
              onDecide(insight, input)
              setReviewing(false)
            }}
          />
        </div>
      )}
    </article>
  )
}
