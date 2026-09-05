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
  onNavigateTab,
  onPrepareAttribution,
}: InsightCardProps) {
  const [showFacts, setShowFacts] = useState(true)
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

  // Filter event evidence from event_log.csv
  const eventEvidence = insight.evidence.filter((e) => e.source_file.includes('event_log'))

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
          <h3>{insight.headline}</h3>
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

      {/* SECTION 1: WHY THIS WAS SURFACED (TRIGGER & PROBLEM STATEMENT) */}
      <div
        style={{
          background: 'var(--surface-sunk)',
          borderLeft: '4px solid var(--accent)',
          borderRadius: 'var(--radius)',
          padding: '12px 16px',
          margin: '12px 0',
        }}
      >
        <div
          className="eyebrow"
          style={{
            color: 'var(--accent)',
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.05em',
            marginBottom: 4,
          }}
        >
          🎯 WHY THIS WAS SURFACED · PROBLEM & CLIENT IMPACT
        </div>
        <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.5, color: 'var(--ink)' }}>
          {insight.summary}
        </p>
        {insight.priority_reasons && insight.priority_reasons.length > 0 && (
          <div style={{ fontSize: 11.5, color: 'var(--ink-soft)', marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <span className="muted">Priority drivers:</span>
            {insight.priority_reasons.map((r, i) => (
              <span key={i} style={{ background: 'var(--surface)', padding: '1px 6px', borderRadius: 3, border: '1px solid var(--rule)' }}>
                {r}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* SECTION 2: VERIFIED PORTFOLIO FACTS */}
      {insight.observed_facts.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 6,
            }}
          >
            <span className="eyebrow" style={{ fontSize: 11, color: 'var(--muted)' }}>
              📊 VERIFIED PORTFOLIO FACTS ({insight.observed_facts.length})
            </span>
            <button
              type="button"
              className="btn quiet"
              style={{ fontSize: 10.5, padding: '1px 6px' }}
              onClick={() => setShowFacts((v) => !v)}
            >
              {showFacts ? 'Collapse figures' : 'Expand figures'}
            </button>
          </div>

          {showFacts && (
            <div className="facts" style={{ marginTop: 2 }}>
              {insight.observed_facts.map((fact, index) => (
                <div className="fact" key={`${fact.label}-${index}`}>
                  <div className="k">{fact.label}</div>
                  <div className="v">{fact.value}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SECTION 3: VERIFIED MARKET EVIDENCE (event_log.csv) */}
      <div style={{ marginBottom: 12 }}>
        <div className="eyebrow" style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
          📰 VERIFIED MARKET EVIDENCE (<code>event_log.csv</code>)
        </div>
        {eventEvidence.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {eventEvidence.map((ev, idx) => (
              <div
                key={idx}
                style={{
                  background: 'var(--surface-sunk)',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius)',
                  fontSize: 12,
                  border: '1px solid var(--rule)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <strong>[{ev.row_or_id}] · {ev.snapshot_date}</strong>
                  <span className="pill accent" style={{ fontSize: 9.5 }}>
                    Direct Evidence
                  </span>
                </div>
                <div style={{ color: 'var(--ink-soft)' }}>
                  {ev.note || String(ev.value ?? '')}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            style={{
              padding: '8px 12px',
              background: 'var(--surface-sunk)',
              borderRadius: 'var(--radius)',
              fontSize: 12,
              color: 'var(--ink-soft)',
              border: '1px dashed var(--rule)',
            }}
          >
            🔍 <em>No direct geopolitical shock cited in <code>event_log.csv</code> for this window. Move reflects internal asset allocation, contract terms, or broader market conditions without an isolated recorded external shock.</em>
          </div>
        )}
      </div>

      {/* SECTION 4: CLIENT-SPECIFIC IMPLICATION */}
      {insight.client_relevance && (
        <div
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius)',
            padding: '10px 14px',
            marginBottom: 12,
          }}
        >
          <div className="eyebrow" style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 4 }}>
            👤 CLIENT-SPECIFIC IMPLICATION
          </div>
          <div style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.5 }}>
            {insight.client_relevance}
          </div>
        </div>
      )}

      {/* SECTION 5: CROSS-LINKS TO RELEVANT DOSSIER TABS */}
      {onNavigateTab && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexWrap: 'wrap',
            margin: '10px 0 14px',
          }}
        >
          <span className="muted" style={{ fontSize: 11.5 }}>Jump to deep-dive:</span>
          <button
            type="button"
            className="chip"
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => onNavigateTab('risk')}
          >
            📊 View in Portfolio Exposure
          </button>
          <button
            type="button"
            className="chip"
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => onNavigateTab('liquidity')}
          >
            💧 View in Liquidity & Collateral
          </button>
          <button
            type="button"
            className="chip"
            style={{ fontSize: 11, padding: '3px 10px' }}
            onClick={() => onNavigateTab('changed')}
          >
            📈 View in What Changed
          </button>
        </div>
      )}

      {/* SECTION 6: WHAT THE RM NEEDS TO CHECK NEXT (INVESTIGATION QUESTIONS) */}
      <div
        className="nextstep"
        style={{
          borderLeftColor: 'var(--high, #e65100)',
          background: 'var(--surface-sunk)',
          marginBottom: 14,
        }}
      >
        <div style={{ fontWeight: 700, fontSize: 12.5, color: 'var(--ink)', marginBottom: 4 }}>
          🔍 Things for RM to Investigate & Verify (High Agency Checklist)
        </div>
        <p style={{ margin: '0 0 6px', fontSize: 12.5, color: 'var(--ink-soft)' }}>
          {insight.suggested_next_step}
        </p>
        {insight.open_questions && insight.open_questions.length > 0 && (
          <ul style={{ margin: '4px 0 0', paddingLeft: 18, fontSize: 12, color: 'var(--ink-soft)' }}>
            {insight.open_questions.map((q, idx) => (
              <li key={idx} style={{ marginBottom: 3 }}>{q}</li>
            ))}
          </ul>
        )}
        {insight.suggested_next_step_original && (
          <div className="footnote" style={{ marginTop: 6 }}>
            Engine wording, updated by RM: “{insight.suggested_next_step_original}”
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

      {/* FOOTER ACTION BUTTONS */}
      <div className="insight-foot" style={{ flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        {onPrepareAttribution && (
          <button
            type="button"
            className="btn primary"
            onClick={() => onPrepareAttribution(insight)}
            title="Generate client-ready conversation talking points for this finding"
          >
            ✨ Prepare Client Attribution
          </button>
        )}
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
          {aiBusy ? 'Drafting…' : 'Controlled AI preview'}
        </button>
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
