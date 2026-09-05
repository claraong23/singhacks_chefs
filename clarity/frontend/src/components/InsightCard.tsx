import { useState } from 'react'
import type { ActionOption, Insight, InsightStatus, RMFeedbackInput, SimulatedRole } from '../types'
import {
  CONFIDENCE_LABEL,
  SEVERITY_LABEL,
  formatClientRelevance,
  formatHeadline,
  formatProblemSummary,
  titleCase,
  usd,
} from '../format'
import { ActionReview } from './ActionReview'

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

function renderMarkdownInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} style={{ color: 'var(--ink, #1f2937)', fontWeight: 600 }}>
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

interface InsightCardProps {
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
  onNavigateTab?: (tab: 'why' | 'changed' | 'risk' | 'liquidity' | 'scenario' | 'brief' | 'follow') => void
  onPrepareAttribution?: (insight: Insight) => void
}

export function InsightCard({
  insight,
  options,
  busy,
  onEvidence,
  onDecide,
  role,
  onNavigateTab: _onNavigateTab,
  onPrepareAttribution,
}: InsightCardProps) {
  const [showFacts, setShowFacts] = useState(false)
  const [reviewing, setReviewing] = useState(false)
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
      {/* CARD HEADER */}
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
          <h3>{formatHeadline(insight.headline)}</h3>
          <div className="meta">
            <span className={`pill ${insight.severity}`}>{SEVERITY_LABEL[insight.severity]}</span>
            <span className="tag">{titleCase(insight.category)}</span>
            <span className="tag" title="How much of this rests on measurement rather than an unverified assumption">
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

      <p className="insight-summary">{formatProblemSummary(insight.summary, insight)}</p>

      {insight.reopen_reason && (
        <div className="nextstep" style={{ borderLeftColor: 'var(--high)' }}>
          <strong>Why this returned.</strong> {insight.reopen_reason}
        </div>
      )}

      {insight.client_relevance && (() => {
        const points = formatClientRelevance(insight.client_relevance, insight)
        if (points.length === 0) return null
        return (
          <div
            style={{
              // Matches the 70px / 18px inset the summary, next step and footer
              // all use, so the card has one left edge rather than three.
              margin: '12px 18px 12px 70px',
              padding: '10px 14px',
              background: 'var(--surface-sunk, #f5f7fa)',
              borderLeft: '3px solid var(--accent, #1a4f78)',
              borderRadius: 'var(--radius, 4px)',
              fontSize: 13,
              lineHeight: 1.55,
              color: 'var(--ink, #1f2937)',
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
                color: 'var(--accent, #1a4f78)',
                marginBottom: 6,
                display: 'flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              <span>👤</span>
              <span>Client &amp; Situation Context</span>
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: 18,
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
              }}
            >
              {points.map((point, index) => (
                <li key={index} style={{ lineHeight: 1.5, color: 'var(--ink, #1f2937)' }}>
                  {renderMarkdownInline(point)}
                </li>
              ))}
            </ul>
          </div>
        )
      })()}

      {/* Figures panel when expanded */}
      {showFacts && insight.observed_facts.length > 0 && (
        <div className="facts" style={{ marginTop: 12, marginBottom: 12 }}>
          {insight.observed_facts.map((fact, index) => (
            <div className="fact" key={`${fact.label}-${index}`}>
              <div className="k">{fact.label}</div>
              <div className="v">{fact.value}</div>
            </div>
          ))}
        </div>
      )}

      <div className="nextstep">
        <strong>Next step.</strong> {insight.suggested_next_step}
        {insight.suggested_next_step_original && (
          <div className="footnote" style={{ marginTop: 6 }}>
            Engine wording, updated by RM: “{insight.suggested_next_step_original}”
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

      {/* FOOTER ACTION BUTTONS */}
      <div className="insight-foot" style={{ flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <button className="btn" onClick={() => setShowFacts((v) => !v)}>
          {showFacts ? 'Hide figures' : `Figures (${insight.observed_facts.length})`}
        </button>
        <button className="btn" onClick={() => onEvidence(insight)}>
          Evidence ({insight.evidence.length})
        </button>
        {onPrepareAttribution && (
          <button
            type="button"
            className="btn"
            onClick={() => onPrepareAttribution(insight)}
            title="Generate client-ready conversation talking points for this finding"
          >
            ✨ Prepare Client Attribution
          </button>
        )}
        <button
          className={`btn${reviewing ? '' : ' primary'}`}
          onClick={() => void toggleReview()}
        >
          {reviewing ? 'Close review' : terminal ? 'View controlled outcome' : `Formulate plan (${options.length})`}
        </button>
        <span className="footnote" style={{ marginLeft: 'auto' }}>
          RM retains sole decision authority. No trades executed automatically.
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
