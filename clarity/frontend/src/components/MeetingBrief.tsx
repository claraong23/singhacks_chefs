import { useState } from 'react'
import type { Dossier } from '../types'

export function MeetingBriefPanel({ dossier }: { dossier: Dossier }) {
  const brief = dossier.brief
  const [draft, setDraft] = useState(brief.draft_follow_up)
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head">
          <h2>Why you are in the room</h2>
          <span className="sub">Generated {brief.generated_at} · as at {brief.as_of}</span>
        </div>
        <div className="card-body">
          <p style={{ marginTop: 0, fontSize: 14.5 }}>{brief.purpose}</p>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-head"><h2>What to say</h2></div>
          <div className="card-body">
            <ul className="brieflist">
              {brief.talking_points.map((point, index) => (
                <li key={index}>{point}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h2>What to ask</h2></div>
          <div className="card-body">
            <ul className="brieflist">
              {brief.questions_to_ask.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>Where the file disagrees with itself</h2>
            <span className="sub">Say these out loud rather than working around them</span>
          </div>
          <div className="card-body">
            {brief.contradictions.length > 0 ? (
              <ul className="brieflist">
                {brief.contradictions.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted small" style={{ margin: 0 }}>
                Nothing in the RM notes contradicts the structured data for this client.
              </p>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>What not to say</h2>
            <span className="sub">Guardrails, not suggestions</span>
          </div>
          <div className="card-body">
            <ul className="brieflist">
              {brief.do_not_say.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h2>Draft follow-up</h2>
          <span className="sub">
            Edit before sending. Assembled from computed facts; the RM owns the wording.
          </span>
        </div>
        <div className="card-body">
          <textarea
            className="draft"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Draft follow-up note"
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
            <button className="btn primary" onClick={copy}>
              {copied ? 'Copied' : 'Copy to clipboard'}
            </button>
            <button className="btn quiet" onClick={() => setDraft(brief.draft_follow_up)}>
              Reset to generated draft
            </button>
            <span className="footnote" style={{ marginLeft: 'auto' }}>
              Nothing is sent from here. Provenance: {brief.provenance}.
            </span>
          </div>
        </div>
      </div>

      {brief.relationship_context.length > 0 && (
        <div className="card">
          <div className="card-head">
            <h2>Last three contacts</h2>
            <span className="sub">Relationship context, not verified fact</span>
          </div>
          <div className="card-body">
            {brief.relationship_context.map((entry, index) => (
              <div className="note-item" key={index}>
                <div className="t">{entry}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
