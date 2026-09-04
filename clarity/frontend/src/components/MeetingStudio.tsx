import { useEffect, useMemo, useState } from 'react'
import {
  createMeetingPackage,
  getMeetingPackages,
  handoffMeetingPackage,
  preflightMeetingPackage,
  regenerateMeetingSection,
  restoreMeetingVersion,
  saveMeetingSection,
} from '../api'
import { shortDate } from '../format'
import type { CommunicationChannel, Dossier, Insight, InsightStatus, MeetingPackage, SimulatedRole } from '../types'
import { KnowledgeReferencePanel } from './KnowledgeReference'
import { AIMeetingDrafting } from './AIMeetingDrafting'

function versionOf(item: MeetingPackage) {
  return item.versions.find((version) => version.version === item.current_version) ?? item.versions[item.versions.length - 1]
}

interface SavedPlanCardProps {
  insight: Insight
  busy: boolean
  onDecide?: (
    insight: Insight,
    input: {
      status: InsightStatus
      rmNote: string
      selectedOptionId: string | null
      editedNextStep: string | null
    },
  ) => Promise<void>
  onReset?: (insight: Insight) => Promise<void>
}

function SavedPlanCard({ insight, busy, onDecide, onReset }: SavedPlanCardProps) {
  const [directive, setDirective] = useState(insight.suggested_next_step)
  const [note, setNote] = useState(insight.rm_note ?? '')
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    setDirective(insight.suggested_next_step)
    setNote(insight.rm_note ?? '')
  }, [insight.suggested_next_step, insight.rm_note])

  const hasChanges =
    directive.trim() !== insight.suggested_next_step.trim() ||
    note.trim() !== (insight.rm_note ?? '').trim()

  const handleSave = async () => {
    if (!onDecide) return
    setIsSaving(true)
    setSaveMessage(null)
    setErrorMessage(null)
    try {
      const nextStatus =
        insight.status === 'new' || insight.status === 'opened' ? 'rm_edited' : insight.status
      await onDecide(insight, {
        status: nextStatus,
        rmNote: note,
        selectedOptionId: insight.selected_option_id ?? null,
        editedNextStep: directive.trim() ? directive : null,
      })
      setSaveMessage('✓ Changes saved')
      setTimeout(() => setSaveMessage(null), 3000)
    } catch (err) {
      setErrorMessage(String(err))
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = async () => {
    const confirmed = window.confirm(
      `Reset the action plan for "${insight.headline}"? The finding will return to unreviewed status and remove this directive from the meeting agenda.`,
    )
    if (!confirmed) return
    setIsSaving(true)
    setErrorMessage(null)
    try {
      if (onReset) {
        await onReset(insight)
      } else if (onDecide) {
        await onDecide(insight, {
          status: 'opened',
          rmNote: '',
          selectedOptionId: null,
          editedNextStep: null,
        })
      }
    } catch (err) {
      setErrorMessage(String(err))
    } finally {
      setIsSaving(false)
    }
  }

  const statusLabel = () => {
    switch (insight.status) {
      case 'client_ready':
        return (
          <span
            className="pill"
            style={{
              background: 'var(--positive-wash, #e8f5e9)',
              color: 'var(--positive, #1b5e20)',
              borderColor: '#c8e6c9',
            }}
          >
            ✓ Client Ready
          </span>
        )
      case 'rm_reviewed':
        return <span className="pill accent">RM Reviewed</span>
      case 'rm_edited':
        return <span className="pill high">Draft Plan</span>
      case 'escalated':
        return <span className="pill high">Specialist Escalated</span>
      case 'deferred':
        return <span className="pill">Deferred</span>
      default:
        return <span className="pill ghost">{insight.status.replace('_', ' ')}</span>
    }
  }

  return (
    <div
      className="card"
      style={{
        marginBottom: 16,
        borderLeft: '4px solid var(--accent)',
        background: 'var(--surface)',
      }}
    >
      <div className="card-head" style={{ padding: '12px 16px', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span className="tag" style={{ textTransform: 'capitalize' }}>
            {insight.category}
          </span>
          <strong style={{ fontSize: 13.5 }}>{insight.headline}</strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
          <span
            className="pill"
            style={{
              background: 'var(--surface-sunk)',
              border: '1px solid var(--rule-strong)',
              fontSize: 11,
              fontWeight: 700,
            }}
          >
            Priority {insight.priority_score} / 100
          </span>
          <span className={`pill ${insight.severity}`} style={{ fontSize: 10.5 }}>
            {insight.severity.toUpperCase()}
          </span>
          {statusLabel()}
        </div>
      </div>

      <div className="card-body" style={{ padding: '14px 16px' }}>
        {/* Action Directive */}
        <div style={{ marginBottom: 14 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginBottom: 4,
            }}
          >
            <label
              htmlFor={`agenda-directive-${insight.id}`}
              className="eyebrow"
              style={{ color: 'var(--accent)', fontSize: 11.5 }}
            >
              🗣️ What to Discuss & Action Directive (Editable)
            </label>
            {insight.edited && (
              <span className="pill accent" style={{ fontSize: 10 }}>
                Custom RM Directive
              </span>
            )}
          </div>
          <textarea
            id={`agenda-directive-${insight.id}`}
            className="rmnote"
            rows={3}
            style={{
              minHeight: 74,
              fontSize: 13,
              lineHeight: 1.5,
              width: '100%',
            }}
            value={directive}
            onChange={(e) => setDirective(e.target.value)}
            placeholder="Type your tailored conversation plan, action directive, or proposal for this client…"
            aria-label={`Action directive for ${insight.headline}`}
          />
        </div>

        {/* RM Rationale */}
        <div style={{ marginBottom: 14 }}>
          <label
            htmlFor={`agenda-note-${insight.id}`}
            className="eyebrow"
            style={{ display: 'block', marginBottom: 4, fontSize: 11.5 }}
          >
            📝 RM Decision Rationale & Compliance File Note (Editable)
          </label>
          <textarea
            id={`agenda-note-${insight.id}`}
            className="rmnote"
            rows={2}
            style={{
              minHeight: 60,
              fontSize: 12.5,
              lineHeight: 1.5,
              width: '100%',
            }}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Document reasoning, client preferences, or risk constraints…"
            aria-label={`RM rationale for ${insight.headline}`}
          />
        </div>

        {/* Card Footer Controls */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 10,
            paddingTop: 8,
            borderTop: '1px solid var(--rule)',
          }}
        >
          <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>
            <span>
              {insight.decided_by ? `Decided by ${insight.decided_by}` : 'Formulated by RM'}
              {insight.decided_at && ` · ${shortDate(insight.decided_at)}`}
            </span>
            {saveMessage && (
              <span style={{ color: 'var(--pass, #2e7d32)', fontWeight: 600, marginLeft: 10 }}>
                {saveMessage}
              </span>
            )}
            {errorMessage && (
              <span style={{ color: 'var(--critical)', marginLeft: 10 }}>{errorMessage}</span>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              className="btn primary"
              style={{ fontSize: 11.5, padding: '5px 12px' }}
              disabled={busy || isSaving || !hasChanges}
              onClick={() => void handleSave()}
            >
              {isSaving ? 'Saving…' : 'Save Changes'}
            </button>
            <button
              className="btn quiet"
              style={{ fontSize: 11.5, padding: '5px 10px', color: 'var(--critical)' }}
              disabled={busy || isSaving}
              onClick={() => void handleReset()}
              title="Reset this plan back to unreviewed"
            >
              🗑️ Reset Plan
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export function MeetingStudio({
  dossier,
  onDecide,
  onReset,
  role = 'rm',
}: {
  dossier: Dossier
  onDecide?: (
    insight: Insight,
    input: {
      status: InsightStatus
      rmNote: string
      selectedOptionId: string | null
      editedNextStep: string | null
    },
  ) => Promise<void>
  onReset?: (insight: Insight) => Promise<void>
  role?: SimulatedRole
}) {
  const clientId = String(dossier.client.client_id)
  const eligible = dossier.insights.filter((insight) => insight.status === 'client_ready')
  const [packages, setPackages] = useState<MeetingPackage[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [channel, setChannel] = useState<CommunicationChannel>('email')
  const [preflight, setPreflight] = useState<MeetingPackage['last_preflight']>()
  const [compareVersion, setCompareVersion] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [planTargetId, setPlanTargetId] = useState<string>('')

  // Saved action plans formulated by RM
  const savedInsights = useMemo(() => {
    return dossier.insights.filter(
      (insight) =>
        ['rm_edited', 'rm_reviewed', 'client_ready', 'escalated', 'deferred'].includes(
          insight.status,
        ) ||
        Boolean(insight.rm_note?.trim()) ||
        Boolean(insight.edited),
    )
  }, [dossier.insights])

  useEffect(() => {
    let active = true
    void getMeetingPackages(clientId)
      .then(({ packages: next }) => {
        if (!active) return
        setPackages(next)
        setSelectedId(next[0]?.id ?? null)
      })
      .catch((error: unknown) => active && setMessage(String(error)))
    return () => {
      active = false
    }
  }, [clientId])

  const selected = useMemo(
    () => packages.find((item) => item.id === selectedId) ?? null,
    [packages, selectedId],
  )
  const current = selected ? versionOf(selected) : undefined
  const comparison =
    selected && compareVersion !== null
      ? selected.versions.find((version) => version.version === compareVersion)
      : undefined
  const allowedRefs =
    selected?.source.evidence.map((item) => `${item.source_file}:${item.row_or_id}`) ?? []

  const replace = (item: MeetingPackage) => {
    setPackages((all) => [item, ...all.filter((candidate) => candidate.id !== item.id)])
    setSelectedId(item.id)
    setPreflight(item.last_preflight)
  }

  const create = async (insightId: string) => {
    setBusy(true)
    setMessage(null)
    try {
      replace((await createMeetingPackage(insightId, clientId)).package)
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  const save = async (key: string, content: string, reason = 'RM edit') => {
    if (!selected) return
    setBusy(true)
    setMessage(null)
    try {
      replace((await saveMeetingSection(selected.id, key, content, allowedRefs, reason)).package)
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  const regenerate = async (key: string) => {
    if (!selected) return
    setBusy(true)
    setMessage(null)
    try {
      replace((await regenerateMeetingSection(selected.id, key)).package)
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  const runPreflight = async () => {
    if (!selected) return
    setBusy(true)
    setMessage(null)
    try {
      const result = (await preflightMeetingPackage(selected.id)).preflight
      setPreflight(result)
      setPackages((all) =>
        all.map((item) =>
          item.id === selected.id
            ? {
                ...item,
                last_preflight: result,
                state: result.can_hand_off ? 'preflight_passed' : 'draft',
              }
            : item,
        ),
      )
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  const copy = async () => {
    const variant = current?.communications.find((item) => item.channel === channel)
    if (!variant || !preflight?.can_hand_off) return
    try {
      await navigator.clipboard.writeText(variant.content)
      setMessage('Copied client-ready draft to clipboard.')
    } catch {
      setMessage('Clipboard access was unavailable; the draft remains on screen.')
    }
  }

  const handoff = async () => {
    if (!selected || !preflight?.can_hand_off) return
    setBusy(true)
    setMessage(null)
    try {
      replace((await handoffMeetingPackage(selected.id, channel)).package)
      setMessage('Simulated hand-off recorded locally. Nothing was sent.')
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  // Handle formulating plan directly from MeetingStudio
  const handleCreateDirectPlan = async () => {
    if (!planTargetId || !onDecide) return
    const target = dossier.insights.find((i) => i.id === planTargetId)
    if (!target) return
    setBusy(true)
    try {
      await onDecide(target, {
        status: 'rm_edited',
        rmNote: `Added to meeting agenda by RM.`,
        selectedOptionId: target.selected_option_id ?? null,
        editedNextStep: target.suggested_next_step,
      })
      setPlanTargetId('')
    } catch (error) {
      setMessage(String(error))
    } finally {
      setBusy(false)
    }
  }

  const unreviewedInsights = dossier.insights.filter(
    (i) => !savedInsights.some((s) => s.id === i.id),
  )

  return (
    <div className="stack" style={{ gap: 20 }}>
      {/* SECTION 1: RM Meeting Agenda & Action Directives */}
      <div className="card">
        <div
          className="card-head"
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}
        >
          <div>
            <h2>📋 RM Meeting Agenda & Action Directives</h2>
            <span className="sub" style={{ display: 'block', marginTop: 3 }}>
              Saved conversation directives and file notes for Priscilla’s client discussion
            </span>
          </div>
          <span className="pill accent" style={{ fontSize: 11 }}>
            {savedInsights.length} Saved {savedInsights.length === 1 ? 'Directive' : 'Directives'}
          </span>
        </div>

        <div className="card-body">
          {savedInsights.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '24px 16px',
                background: 'var(--surface-sunk)',
                borderRadius: 'var(--radius)',
                border: '1px dashed var(--rule)',
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }}>📝</div>
              <h3 style={{ fontSize: 15, margin: '0 0 6px', fontWeight: 600 }}>
                No Action Directives Formulated Yet
              </h3>
              <p
                className="muted"
                style={{
                  maxWidth: 520,
                  margin: '0 auto 16px',
                  fontSize: 12.5,
                  lineHeight: 1.5,
                }}
              >
                When you review flagged items in the <strong>Flags to address</strong> tab and save
                your directives, they will automatically appear here as your working meeting agenda.
              </p>
              {unreviewedInsights.length > 0 && onDecide && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    background: 'var(--surface)',
                    padding: '8px 12px',
                    borderRadius: 6,
                    border: '1px solid var(--rule)',
                  }}
                >
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                    Add a flag directly to agenda:
                  </span>
                  <select
                    className="select"
                    style={{ fontSize: 12, padding: '4px 8px', maxWidth: 320 }}
                    value={planTargetId}
                    onChange={(e) => setPlanTargetId(e.target.value)}
                  >
                    <option value="">Select a flag to plan…</option>
                    {unreviewedInsights.map((i) => (
                      <option key={i.id} value={i.id}>
                        [{i.priority_score}/100] {i.headline}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn primary"
                    style={{ fontSize: 11.5, padding: '4px 10px' }}
                    disabled={!planTargetId || busy}
                    onClick={() => void handleCreateDirectPlan()}
                  >
                    + Add to Agenda
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div>
              <p className="footnote" style={{ marginTop: 0, marginBottom: 14 }}>
                Each card below represents a saved advisory plan for this client. You can edit the
                talking directive and compliance note at any time, or reset the plan back to
                unreviewed.
              </p>
              <div className="stack" style={{ gap: 14 }}>
                {savedInsights.map((insight) => (
                  <SavedPlanCard
                    key={insight.id}
                    insight={insight}
                    busy={busy}
                    onDecide={onDecide}
                    onReset={onReset}
                  />
                ))}
              </div>

              {unreviewedInsights.length > 0 && onDecide && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    marginTop: 16,
                    padding: '10px 14px',
                    background: 'var(--surface-sunk)',
                    borderRadius: 'var(--radius)',
                    border: '1px solid var(--rule)',
                    flexWrap: 'wrap',
                  }}
                >
                  <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                    Add another unreviewed flag to this meeting agenda:
                  </span>
                  <select
                    className="select"
                    style={{ fontSize: 12, padding: '4px 8px', maxWidth: 360 }}
                    value={planTargetId}
                    onChange={(e) => setPlanTargetId(e.target.value)}
                  >
                    <option value="">Select an outstanding flag…</option>
                    {unreviewedInsights.map((i) => (
                      <option key={i.id} value={i.id}>
                        [{i.priority_score}/100] {i.headline}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn"
                    style={{ fontSize: 11.5, padding: '4px 10px' }}
                    disabled={!planTargetId || busy}
                    onClick={() => void handleCreateDirectPlan()}
                  >
                    + Add to Agenda
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <KnowledgeReferencePanel role={role} location="meeting_studio" />

      {/* SECTION 2: Client-Facing Communication Package & Preflight */}
      {eligible.length === 0 ? (
        <div className="card">
          <div className="card-head">
            <h2>Meeting Studio</h2>
            <span className="sub">Controlled client communication</span>
          </div>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>No client-ready findings are available for this client.</p>
            <p className="muted small" style={{ marginBottom: 0 }}>
              Complete the RM review and all client-ready checks first. Clarity will not create,
              copy, or hand off client-facing material from a pending finding.
            </p>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <div className="card-head">
              <h2>Meeting Studio</h2>
              <span className="sub">Deterministic, evidence-linked, never sent automatically</span>
            </div>
            <div className="card-body">
              <label className="fact">
                <span>Client-ready finding</span>
                <select
                  className="select"
                  value={selected?.insight_id ?? ''}
                  onChange={(event) => {
                    const existing = packages.find((item) => item.insight_id === event.target.value)
                    if (existing) setSelectedId(existing.id)
                  }}
                >
                  <option value="" disabled>
                    Select an approved finding
                  </option>
                  {eligible.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.headline}
                    </option>
                  ))}
                </select>
              </label>
              <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                {eligible
                  .filter((item) => !packages.some((pack) => pack.insight_id === item.id))
                  .map((item) => (
                    <button
                      className="btn primary"
                      disabled={busy}
                      onClick={() => void create(item.id)}
                      key={item.id}
                    >
                      Create package: {item.headline}
                    </button>
                  ))}
              </div>
              {packages.length === 0 && (
                <p className="footnote">
                  Select a client-ready finding above to create its first evidence snapshot.
                </p>
              )}
            </div>
          </div>

          {selected && current && (
            <>
              <div className="card">
                <div className="card-head">
                  <h2>Evidence snapshot</h2>
                  <span className="sub">
                    Package v{current.version} · {selected.state.replace('_', ' ')}
                  </span>
                </div>
                <div className="card-body">
                  <p className="footnote" style={{ marginTop: 0 }}>
                    Option: {selected.source.selected_option_id ?? 'none'} · Evidence:{' '}
                    {selected.source.evidence_version ?? 'not recorded'}
                    {selected.source.selected_scenario_id
                      ? ` · Scenario: ${selected.source.scenario_calculation_version}`
                      : ''}
                  </p>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {allowedRefs.map((ref) => (
                      <span className="tag" key={ref}>
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <AIMeetingDrafting package={selected} role={role} busy={busy} onApplied={replace} />

              <div className="grid2">
                {current.sections.map((section) => (
                  <div className="card" key={section.key}>
                    <div className="card-head">
                      <h3>{section.title}</h3>
                      <button
                        className="btn quiet"
                        disabled={busy}
                        onClick={() => void regenerate(section.key)}
                      >
                        Reset deterministic wording
                      </button>
                    </div>
                    <div className="card-body">
                      <textarea
                        className="draft"
                        style={{ minHeight: 140 }}
                        defaultValue={section.content}
                        onBlur={(event) => {
                          if (event.currentTarget.value !== section.content)
                            void save(section.key, event.currentTarget.value)
                        }}
                        aria-label={section.title}
                      />
                      <div className="footnote">
                        Edit is saved on leaving this field and keeps this package’s evidence
                        references.
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="card">
                <div className="card-head">
                  <h2>Client-facing draft</h2>
                  <span className="sub">
                    Copy and simulated hand-off require a passing preflight
                  </span>
                </div>
                <div className="card-body">
                  <label className="fact">
                    <span>Channel</span>
                    <select
                      className="select"
                      value={channel}
                      onChange={(event) => setChannel(event.target.value as CommunicationChannel)}
                    >
                      {current.communications.map((item) => (
                        <option key={item.channel} value={item.channel}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {current.communications
                    .filter((item) => item.channel === channel)
                    .map((item) => (
                      <div key={item.channel} style={{ marginTop: 12 }}>
                        <textarea
                          className="draft"
                          style={{ minHeight: 240 }}
                          defaultValue={item.content}
                          onBlur={(event) => {
                            if (event.currentTarget.value !== item.content)
                              void save(item.channel, event.currentTarget.value)
                          }}
                          aria-label={`${item.label} draft`}
                        />
                        <div className="footnote">
                          Internal evidence IDs are retained in the package but never inserted
                          into this client-facing draft.
                        </div>
                      </div>
                    ))}
                  <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                    <button className="btn" disabled={busy} onClick={() => void runPreflight()}>
                      Run communication preflight
                    </button>
                    <button
                      className="btn primary"
                      disabled={busy || !preflight?.can_hand_off}
                      onClick={() => void copy()}
                    >
                      Copy client-ready draft
                    </button>
                    <button
                      className="btn primary"
                      disabled={busy || !preflight?.can_hand_off}
                      onClick={() => void handoff()}
                    >
                      Record simulated hand-off
                    </button>
                  </div>
                  {preflight && (
                    <div
                      className="card"
                      style={{ marginTop: 16, background: 'var(--surface-sunk)' }}
                    >
                      <div className="card-head">
                        <h3>Preflight checks</h3>
                        <span className="sub">
                          {preflight.can_hand_off ? 'Passed' : 'Blocked'}
                        </span>
                      </div>
                      <div className="card-body">
                        {preflight.checks.map((check) => (
                          <div className="check" key={check.id}>
                            <span className={`mark ${check.status === 'pass' ? 'pass' : 'fail'}`}>
                              {check.status === 'pass' ? '✓' : '!'}
                            </span>
                            <div>
                              <div>{check.label}</div>
                              <div className="d">{check.detail}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-head">
                  <h2>Version history</h2>
                  <span className="sub">Edits and restores are append-only</span>
                </div>
                <div className="card-body">
                  <label className="fact">
                    <span>Compare with version</span>
                    <select
                      className="select"
                      value={compareVersion ?? ''}
                      onChange={(event) =>
                        setCompareVersion(event.target.value ? Number(event.target.value) : null)
                      }
                    >
                      <option value="">Choose a prior version</option>
                      {selected.versions
                        .filter((version) => version.version !== current.version)
                        .map((version) => (
                          <option value={version.version} key={version.id}>
                            v{version.version} · {version.reason}
                          </option>
                        ))}
                    </select>
                  </label>
                  {comparison && (
                    <div style={{ marginTop: 12 }}>
                      <p className="footnote">
                        Comparing v{comparison.version} ({comparison.reason}) with current v
                        {current.version}. Restore creates a new version; history remains intact.
                      </p>
                      <button
                        className="btn"
                        disabled={busy}
                        onClick={() => {
                          setBusy(true)
                          void restoreMeetingVersion(selected.id, comparison.version)
                            .then(({ package: item }) => replace(item))
                            .catch((error) => setMessage(String(error)))
                            .finally(() => setBusy(false))
                        }}
                      >
                        Restore v{comparison.version} as new version
                      </button>
                    </div>
                  )}
                  {selected.handoffs.length > 0 && (
                    <p className="footnote">
                      Latest simulated hand-off:{' '}
                      {selected.handoffs[selected.handoffs.length - 1]?.created_at}. No external
                      message was sent.
                    </p>
                  )}
                </div>
              </div>
            </>
          )}
        </>
      )}
      {message && (
        <div className="banner" role="status">
          {message}
        </div>
      )}
    </div>
  )
}

