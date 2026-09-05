import { useState } from 'react'
import type { ClientAttributionDraft } from '../types'
import { addDraftToMeetingBrief } from '../api'

interface ClientAttributionModalProps {
  draft: ClientAttributionDraft | null
  loading: boolean
  onClose: () => void
  onDraftAdded?: () => void
}

function cleanNarrative(text: string | null | undefined, fallback: string): string {
  if (!text || text.includes('[object Object]')) {
    return fallback
  }
  return text
}

export function ClientAttributionModal({
  draft,
  loading,
  onClose,
  onDraftAdded,
}: ClientAttributionModalProps) {
  const [copied, setCopied] = useState(false)
  const [addingToBrief, setAddingToBrief] = useState(false)
  const [briefAdded, setBriefAdded] = useState(false)

  if (!draft && !loading) return null

  const whatHappenedText = cleanNarrative(
    draft?.what_happened_bullet,
    'Identified portfolio exposure requiring review and verification.',
  )

  const handleCopy = () => {
    if (!draft) return
    const text = `${draft.headline}

1. What Happened:
${whatHappenedText}

2. Why It Matters For You:
${draft.why_it_matters_bullet}

3. Next Steps to Consider:
${draft.next_steps_bullet}

Sources: ${draft.source_chips.join(', ')}
${draft.language_disclaimer ? `Note: ${draft.language_disclaimer}` : ''}`

    void navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleAddToBrief = async () => {
    if (!draft) return
    setAddingToBrief(true)
    try {
      await addDraftToMeetingBrief(draft.client_id, draft)
      setBriefAdded(true)
      if (onDraftAdded) onDraftAdded()
      setTimeout(() => setBriefAdded(false), 2500)
    } catch (err) {
      alert(`Error adding to meeting brief: ${String(err)}`)
    } finally {
      setAddingToBrief(false)
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div
        className="card"
        style={{
          position: 'fixed',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 'min(640px, 94vw)',
          maxHeight: '90vh',
          overflowY: 'auto',
          zIndex: 100,
          boxShadow: '0 16px 40px rgba(0,0,0,0.3)',
          background: 'var(--surface)',
        }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Client Attribution Talking Points"
      >
        <div className="card-head">
          <div>
            <div className="eyebrow" style={{ color: 'var(--accent)' }}>
              Client Conversation Studio · Talking Points
            </div>
            <h2 style={{ fontSize: 16, marginTop: 4 }}>
              {draft?.instrument_name || 'Generating talking points…'}
            </h2>
          </div>
          <button className="btn quiet" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        <div className="card-body">
          {loading || !draft ? (
            <div className="loading">
              Synthesizing client-centric talking points and grounding evidence…
            </div>
          ) : (
            <div className="stack" style={{ gap: 14 }}>
              {/* Language Disclaimer Banner */}
              {draft.language_disclaimer && (
                <div
                  className="banner"
                  style={{
                    background: 'var(--high-wash)',
                    borderColor: '#eccfcb',
                    color: 'var(--high)',
                    fontSize: 12,
                    marginBottom: 4,
                  }}
                >
                  <strong>⚠️ Language Preview Notice:</strong> {draft.language_disclaimer}
                </div>
              )}

              {/* Headline */}
              <div
                style={{
                  padding: '12px 14px',
                  background: 'var(--accent-wash)',
                  borderRadius: 'var(--radius)',
                  borderLeft: '3px solid var(--accent)',
                }}
              >
                <div className="eyebrow" style={{ fontSize: 10, color: 'var(--muted)' }}>
                  RM Discussion Headline
                </div>
                <div
                  style={{
                    fontFamily: 'var(--serif)',
                    fontSize: 16,
                    fontWeight: 600,
                    color: 'var(--accent)',
                    marginTop: 3,
                  }}
                >
                  "{draft.headline}"
                </div>
              </div>

              {/* 3 Conversational Talking Points */}
              <div className="card" style={{ background: 'var(--surface)' }}>
                <div className="card-body" style={{ padding: '14px' }}>
                  <div style={{ marginBottom: 14 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span className="pill accent" style={{ fontSize: 10.5 }}>
                        1. What Happened
                      </span>
                      <span className="muted" style={{ fontSize: 11.5 }}>
                        Plain conversational narrative
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>
                      {whatHappenedText}
                    </p>
                  </div>

                  <div style={{ marginBottom: 14 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span className="pill high" style={{ fontSize: 10.5 }}>
                        2. Why It Matters For You
                      </span>
                      <span className="muted" style={{ fontSize: 11.5 }}>
                        Personalised to client profile & commitments
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>
                      {draft.why_it_matters_bullet}
                    </p>
                  </div>

                  <div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <span className="pill medium" style={{ fontSize: 10.5 }}>
                        3. Next Steps to Discuss
                      </span>
                      <span className="muted" style={{ fontSize: 11.5 }}>
                        Actionable meeting guidance
                      </span>
                    </div>
                    <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>
                      {draft.next_steps_bullet}
                    </p>
                  </div>
                </div>
              </div>

              {/* Grounded Evidence Chips & Confidence */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 8,
                  fontSize: 11.5,
                  padding: '8px 12px',
                  background: 'var(--surface-sunk)',
                  borderRadius: 'var(--radius)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span className="muted">Sources:</span>
                  {draft.source_chips.map((chip, idx) => (
                    <span
                      key={idx}
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 10.5,
                        background: 'var(--surface)',
                        padding: '1px 6px',
                        border: '1px solid var(--rule)',
                        borderRadius: 3,
                      }}
                    >
                      {chip}
                    </span>
                  ))}
                </div>
                <div className="muted">
                  Confidence: <strong>{draft.confidence}</strong>
                </div>
              </div>

              {/* Action Buttons */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  gap: 8,
                  marginTop: 6,
                }}
              >
                <button className="btn quiet" onClick={onClose}>
                  Dismiss
                </button>
                <button
                  className="btn"
                  onClick={handleCopy}
                  title="Copy talking points formatted for notes or client call"
                >
                  {copied ? '✓ Copied to Clipboard!' : '📋 Copy Talking Points'}
                </button>
                <button
                  className="btn primary"
                  onClick={handleAddToBrief}
                  disabled={addingToBrief}
                  title="Insert this narrative into the RM Meeting Studio brief"
                >
                  {briefAdded
                    ? '✓ Added to Meeting Studio!'
                    : addingToBrief
                    ? 'Adding…'
                    : '➕ Add to Meeting Brief'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
