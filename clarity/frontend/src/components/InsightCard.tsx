import { useState } from 'react'
import type { ActionOption, Insight, InsightNarrativeDraft, InsightStatus, RMFeedbackInput, SimulatedRole } from '../types'
import { CONFIDENCE_LABEL, SEVERITY_LABEL, titleCase, usd } from '../format'
import { ActionReview } from './ActionReview'
import { draftNarrative } from '../api'

const STATUS_LABEL: Record<InsightStatus, string> = {
  new: 'New',
  opened: 'Opened',
  under_review: 'Under review',
  rm_edited: 'RM edited',
  rm_reviewed: 'RM reviewed',
  escalated: 'Escalated',
  returned_for_review: 'Returned for review',
  client_ready: 'Client-ready',
  deferred: 'Deferred',
  dismissed: 'Dismissed',
}

export function InsightCard({
  insight,
  options,
  busy,
  onEvidence,
  onDecide,
  role,
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
      feedback?: RMFeedbackInput
    },
  ) => Promise<void>
  role: SimulatedRole
}) {
  const [showFacts, setShowFacts] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [aiDraft, setAiDraft] = useState<InsightNarrativeDraft | null>(null)
  const [aiBusy, setAiBusy] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const chosen = options.find((option) => option.id === insight.selected_option_id)
  const terminal = ['client_ready', 'deferred', 'dismissed'].includes(insight.status)

  const toggleReview = async () => {
    if (reviewing) {
      setReviewing(false)
      return
    }
    if (insight.status === 'new') {
      await onDecide(insight, {
        status: 'opened',
        rmNote: '',
        selectedOptionId: null,
        editedNextStep: null,
      })
    }
    setReviewing(true)
  }

  return (
    <article className={`insight ${insight.severity}${insight.status === 'dismissed' ? ' dismissed' : ''}`}>
      <div className="insight-head">
        <div
          className="score"
          title={`Priority score ${insight.priority_score.toFixed(1)} out of 100`}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            minWidth: 54,
            paddingRight: 6,
          }}
        >
          <span
            style={{
              fontSize: 9,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              color: 'var(--muted)',
              fontWeight: 600,
              lineHeight: 1,
            }}
          >
            Priority
          </span>
          <span style={{ fontSize: 22, fontWeight: 700, lineHeight: 1.15 }}>
            {insight.priority_score.toFixed(0)}
          </span>
          <span style={{ fontSize: 9.5, color: 'var(--faint)', lineHeight: 1 }}>/ 100</span>
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
            {insight.selected_scenario_id && <span className="pill ghost">Scenario attached</span>}
            {insight.edited && <span className="pill ghost">RM edited</span>}
            {insight.reopened && <span className="pill high">Reopened</span>}
          </div>
        </div>
      </div>

      <p className="insight-summary">{insight.summary}</p>

      {insight.reopen_reason && (
        <div className="nextstep" style={{ borderLeftColor: 'var(--high)' }}>
          <strong>Why this returned.</strong> {insight.reopen_reason}
        </div>
      )}

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

      {aiDraft?.narrative && (
        <div className="nextstep" style={{ borderLeftColor: 'var(--accent)' }}>
          <strong>Controlled AI preview — not saved.</strong> {aiDraft.narrative}
          <div className="footnote" style={{ marginTop: 6 }}>
            Provider: {aiDraft.provenance.provider} · model: {aiDraft.provenance.model} · {aiDraft.guardrails.length} checks passed
          </div>
        </div>
      )}
      {aiDraft && !aiDraft.can_use && (
        <div className="banner">
          <strong>AI output blocked.</strong> The preview introduced wording that did not pass the controlled checks.
          {aiDraft.guardrails.filter((check) => check.status === 'block').map((check) => (
            <div className="footnote" key={check.id}>{check.label}: {check.detail}</div>
          ))}
        </div>
      )}
      {aiError && <div className="footnote">AI draft unavailable: {aiError}</div>}

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
          className="btn"
          disabled={aiBusy || role !== 'rm'}
          title={role === 'rm' ? 'Generate a guarded explanation from this computed insight' : 'Only the RM role can generate an AI preview'}
          onClick={async () => {
            setAiBusy(true)
            setAiError(null)
            try {
              const result = await draftNarrative(insight.id, role)
              setAiDraft(result)
            } catch (error) {
              setAiError(error instanceof Error ? error.message : 'Request failed')
            } finally {
              setAiBusy(false)
            }
          }}
        >
          {aiBusy ? 'Drafting…' : 'Generate controlled AI preview'}
        </button>
        <button
          className={`btn${reviewing ? '' : ' primary'}`}
          onClick={() => void toggleReview()}
        >
          {reviewing ? 'Close review' : terminal ? 'View controlled outcome' : `Review options (${options.length})`}
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
            role={role}
            onClose={() => setReviewing(false)}
            onDecide={async (input) => {
              await onDecide(insight, input)
              if (['client_ready', 'deferred', 'dismissed'].includes(input.status)) {
                setReviewing(false)
              }
            }}
          />
        </div>
      )}
    </article>
  )
}
