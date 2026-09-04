import { useEffect, useMemo, useState } from 'react'
import { applyAIMeetingDraft, generateAIMeetingDraft, getAIDraftingStatus } from '../api'
import type { AIDraftCandidate, AIDraftStyle, AIDraftingProviderStatus, MeetingPackage, SimulatedRole } from '../types'

const styles: { value: AIDraftStyle; label: string }[] = [
  { value: 'clear_concise', label: 'Clear and concise' },
  { value: 'warm_respectful', label: 'Warm and respectful' },
  { value: 'formal_concise', label: 'Formal and concise' },
]

export function AIMeetingDrafting({ package: item, role, busy, onApplied }: {
  package: MeetingPackage
  role: SimulatedRole
  busy: boolean
  onApplied: (item: MeetingPackage) => void
}) {
  const current = item.versions.find((version) => version.version === item.current_version) ?? item.versions[item.versions.length - 1]
  const targets = useMemo(() => [
    ...current.sections.map((section) => ({ key: section.key, label: `Internal: ${section.title}`, content: section.content })),
    ...current.communications.map((variant) => ({ key: variant.channel, label: `Client-facing: ${variant.label}`, content: variant.content })),
  ], [current])
  const [status, setStatus] = useState<AIDraftingProviderStatus | null>(null)
  const [targetKey, setTargetKey] = useState(targets[0]?.key ?? '')
  const [style, setStyle] = useState<AIDraftStyle>('clear_concise')
  const [draft, setDraft] = useState<AIDraftCandidate | null>(null)
  const [rationale, setRationale] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const target = targets.find((candidate) => candidate.key === targetKey)

  useEffect(() => { void getAIDraftingStatus().then(setStatus).catch((error) => setMessage(String(error))) }, [])
  useEffect(() => { setTargetKey(targets[0]?.key ?? ''); setDraft(null); setRationale('') }, [item.id, item.current_version, targets])

  const generate = async () => {
    if (!status?.available || role !== 'rm' || !targetKey) return
    setWorking(true); setMessage(null)
    try {
      const result = await generateAIMeetingDraft(item.id, targetKey, style, role)
      setDraft(result.draft)
      setMessage(result.draft.can_apply ? 'AI preview is ready for RM review. It has not changed the package.' : 'AI output was blocked and was not made available for application.')
    } catch (error) { setMessage(String(error)) } finally { setWorking(false) }
  }

  const apply = async () => {
    if (!draft?.can_apply || !rationale.trim()) return
    setWorking(true); setMessage(null)
    try {
      onApplied((await applyAIMeetingDraft(item.id, draft.id, rationale, role)).package)
      setMessage('AI wording applied as a new immutable package version. Run communication preflight again before copy or hand-off.')
      setDraft(null); setRationale('')
    } catch (error) { setMessage(String(error)) } finally { setWorking(false) }
  }

  return <div className="card">
    <div className="card-head"><h2>Optional AI drafting</h2><span className="sub">RM-controlled rewrite from this approved package only</span></div>
    <div className="card-body">
      <p className="footnote" style={{ marginTop: 0 }}>AI receives only the selected package surface and its existing wording. It never receives CSVs, RM notes, the full dossier, or web/retrieval content; it cannot send, advise, trade, or change a decision.</p>
      {!status ? <p className="muted">Checking local AI drafting availability…</p> : !status.available ? <div className="banner"><strong>AI drafting is disabled.</strong> {status.detail} Use “Reset deterministic wording” to restore the controlled local draft.</div> : <>
        <div className="grid2">
          <label className="fact"><span>Package surface</span><select className="select" value={targetKey} onChange={(event) => { setTargetKey(event.target.value); setDraft(null) }} disabled={working || busy}>{targets.map((candidate) => <option value={candidate.key} key={candidate.key}>{candidate.label}</option>)}</select></label>
          <label className="fact"><span>Writing style</span><select className="select" value={style} onChange={(event) => setStyle(event.target.value as AIDraftStyle)} disabled={working || busy}>{styles.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></label>
        </div>
        {role !== 'rm' ? <p className="footnote">Only the simulated RM role can generate or apply an AI draft. Compliance/Audit can inspect provenance in the audit timeline.</p> : <button className="btn" disabled={working || busy} onClick={() => void generate()}>Generate controlled AI preview</button>}
      </>}
      {draft && <div className="stack" style={{ marginTop: 16 }}>
        <div className="card" style={{ background: 'var(--surface-sunk)' }}><div className="card-head"><h3>Guardrail result</h3><span className="sub">{draft.can_apply ? 'Passed for RM review' : 'Blocked'}</span></div><div className="card-body">{draft.guardrails.map((check) => <div className="check" key={check.id}><span className={`mark ${check.status === 'pass' ? 'pass' : 'fail'}`}>{check.status === 'pass' ? '✓' : '!'}</span><div><div>{check.label}</div><div className="d">{check.detail}</div></div></div>)}</div></div>
        {draft.content && target && <><div className="grid2"><label className="fact"><span>Approved current wording</span><textarea className="draft" readOnly value={target.content} aria-label="Approved current wording" /></label><label className="fact"><span>AI preview — not saved</span><textarea className="draft" readOnly value={draft.content} aria-label="AI draft preview" /></label></div><p className="footnote">Provider: {draft.provenance?.provider} · model: {draft.provenance?.model} · expires {new Date(draft.expires_at).toLocaleTimeString()}.</p><label className="fact"><span>RM rationale for applying this wording</span><textarea className="rmnote" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why is this controlled rewrite appropriate for this conversation?" /></label><button className="btn primary" disabled={working || busy || !rationale.trim()} onClick={() => void apply()}>Apply AI draft as new version</button></>}
      </div>}
      {message && <div className="banner" role="status" style={{ marginTop: 12 }}>{message}</div>}
    </div>
  </div>
}
