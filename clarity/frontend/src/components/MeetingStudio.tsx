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
import type { CommunicationChannel, Dossier, MeetingPackage } from '../types'

function versionOf(item: MeetingPackage) {
  return item.versions.find((version) => version.version === item.current_version) ?? item.versions[item.versions.length - 1]
}

export function MeetingStudio({ dossier }: { dossier: Dossier }) {
  const clientId = String(dossier.client.client_id)
  const eligible = dossier.insights.filter((insight) => insight.status === 'client_ready')
  const [packages, setPackages] = useState<MeetingPackage[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [channel, setChannel] = useState<CommunicationChannel>('email')
  const [preflight, setPreflight] = useState<MeetingPackage['last_preflight']>()
  const [compareVersion, setCompareVersion] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let active = true
    void getMeetingPackages(clientId).then(({ packages: next }) => {
      if (!active) return
      setPackages(next)
      setSelectedId(next[0]?.id ?? null)
    }).catch((error: unknown) => active && setMessage(String(error)))
    return () => { active = false }
  }, [clientId])

  const selected = useMemo(() => packages.find((item) => item.id === selectedId) ?? null, [packages, selectedId])
  const current = selected ? versionOf(selected) : undefined
  const comparison = selected && compareVersion !== null
    ? selected.versions.find((version) => version.version === compareVersion) : undefined
  const allowedRefs = selected?.source.evidence.map((item) => `${item.source_file}:${item.row_or_id}`) ?? []

  const replace = (item: MeetingPackage) => {
    setPackages((all) => [item, ...all.filter((candidate) => candidate.id !== item.id)])
    setSelectedId(item.id)
    setPreflight(item.last_preflight)
  }

  const create = async (insightId: string) => {
    setBusy(true); setMessage(null)
    try { replace((await createMeetingPackage(insightId, clientId)).package) }
    catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  const save = async (key: string, content: string, reason = 'RM edit') => {
    if (!selected) return
    setBusy(true); setMessage(null)
    try { replace((await saveMeetingSection(selected.id, key, content, allowedRefs, reason)).package) }
    catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  const regenerate = async (key: string) => {
    if (!selected) return
    setBusy(true); setMessage(null)
    try { replace((await regenerateMeetingSection(selected.id, key)).package) }
    catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  const runPreflight = async () => {
    if (!selected) return
    setBusy(true); setMessage(null)
    try {
      const result = (await preflightMeetingPackage(selected.id)).preflight
      setPreflight(result)
      setPackages((all) => all.map((item) => item.id === selected.id ? { ...item, last_preflight: result, state: result.can_hand_off ? 'preflight_passed' : 'draft' } : item))
    } catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  const copy = async () => {
    const variant = current?.communications.find((item) => item.channel === channel)
    if (!variant || !preflight?.can_hand_off) return
    try { await navigator.clipboard.writeText(variant.content); setMessage('Copied client-ready draft to clipboard.') }
    catch { setMessage('Clipboard access was unavailable; the draft remains on screen.') }
  }

  const handoff = async () => {
    if (!selected || !preflight?.can_hand_off) return
    setBusy(true); setMessage(null)
    try { replace((await handoffMeetingPackage(selected.id, channel)).package); setMessage('Simulated hand-off recorded locally. Nothing was sent.') }
    catch (error) { setMessage(String(error)) }
    finally { setBusy(false) }
  }

  if (eligible.length === 0) {
    return <div className="card"><div className="card-head"><h2>Meeting Studio</h2><span className="sub">Controlled client communication</span></div><div className="card-body"><p style={{ marginTop: 0 }}>No client-ready findings are available for this client.</p><p className="muted small" style={{ marginBottom: 0 }}>Complete the RM review and all client-ready checks first. Clarity will not create, copy, or hand off client-facing material from a pending finding.</p></div></div>
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><h2>Meeting Studio</h2><span className="sub">Deterministic, evidence-linked, never sent automatically</span></div>
        <div className="card-body">
          <label className="fact"><span>Client-ready finding</span><select className="select" value={selected?.insight_id ?? ''} onChange={(event) => {
            const existing = packages.find((item) => item.insight_id === event.target.value)
            if (existing) setSelectedId(existing.id)
          }}>
            <option value="" disabled>Select an approved finding</option>
            {eligible.map((item) => <option value={item.id} key={item.id}>{item.headline}</option>)}
          </select></label>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            {eligible.filter((item) => !packages.some((pack) => pack.insight_id === item.id)).map((item) => (
              <button className="btn primary" disabled={busy} onClick={() => void create(item.id)} key={item.id}>Create package: {item.headline}</button>
            ))}
          </div>
          {packages.length === 0 && <p className="footnote">Select a client-ready finding above to create its first evidence snapshot.</p>}
        </div>
      </div>

      {selected && current && <>
        <div className="card">
          <div className="card-head"><h2>Evidence snapshot</h2><span className="sub">Package v{current.version} · {selected.state.replace('_', ' ')}</span></div>
          <div className="card-body"><p className="footnote" style={{ marginTop: 0 }}>Option: {selected.source.selected_option_id ?? 'none'} · Evidence: {selected.source.evidence_version ?? 'not recorded'}{selected.source.selected_scenario_id ? ` · Scenario: ${selected.source.scenario_calculation_version}` : ''}</p><div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{allowedRefs.map((ref) => <span className="tag" key={ref}>{ref}</span>)}</div></div>
        </div>

        <div className="grid2">
          {current.sections.map((section) => <div className="card" key={section.key}>
            <div className="card-head"><h3>{section.title}</h3><button className="btn quiet" disabled={busy} onClick={() => void regenerate(section.key)}>Reset deterministic wording</button></div>
            <div className="card-body"><textarea className="draft" style={{ minHeight: 140 }} defaultValue={section.content} onBlur={(event) => {
              if (event.currentTarget.value !== section.content) void save(section.key, event.currentTarget.value)
            }} aria-label={section.title} /><div className="footnote">Edit is saved on leaving this field and keeps this package’s evidence references.</div></div>
          </div>)}
        </div>

        <div className="card">
          <div className="card-head"><h2>Client-facing draft</h2><span className="sub">Copy and simulated hand-off require a passing preflight</span></div>
          <div className="card-body">
            <label className="fact"><span>Channel</span><select className="select" value={channel} onChange={(event) => setChannel(event.target.value as CommunicationChannel)}>{current.communications.map((item) => <option key={item.channel} value={item.channel}>{item.label}</option>)}</select></label>
            {current.communications.filter((item) => item.channel === channel).map((item) => <div key={item.channel} style={{ marginTop: 12 }}><textarea className="draft" style={{ minHeight: 240 }} defaultValue={item.content} onBlur={(event) => { if (event.currentTarget.value !== item.content) void save(item.channel, event.currentTarget.value) }} aria-label={`${item.label} draft`} /><div className="footnote">Internal evidence IDs are retained in the package but never inserted into this client-facing draft.</div></div>)}
            <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}><button className="btn" disabled={busy} onClick={() => void runPreflight()}>Run communication preflight</button><button className="btn primary" disabled={busy || !preflight?.can_hand_off} onClick={() => void copy()}>Copy client-ready draft</button><button className="btn primary" disabled={busy || !preflight?.can_hand_off} onClick={() => void handoff()}>Record simulated hand-off</button></div>
            {preflight && <div className="card" style={{ marginTop: 16, background: 'var(--surface-sunk)' }}><div className="card-head"><h3>Preflight checks</h3><span className="sub">{preflight.can_hand_off ? 'Passed' : 'Blocked'}</span></div><div className="card-body">{preflight.checks.map((check) => <div className="check" key={check.id}><span className={`mark ${check.status === 'pass' ? 'pass' : 'fail'}`}>{check.status === 'pass' ? '✓' : '!'}</span><div><div>{check.label}</div><div className="d">{check.detail}</div></div></div>)}</div></div>}
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h2>Version history</h2><span className="sub">Edits and restores are append-only</span></div>
          <div className="card-body"><label className="fact"><span>Compare with version</span><select className="select" value={compareVersion ?? ''} onChange={(event) => setCompareVersion(event.target.value ? Number(event.target.value) : null)}><option value="">Choose a prior version</option>{selected.versions.filter((version) => version.version !== current.version).map((version) => <option value={version.version} key={version.id}>v{version.version} · {version.reason}</option>)}</select></label>{comparison && <div style={{ marginTop: 12 }}><p className="footnote">Comparing v{comparison.version} ({comparison.reason}) with current v{current.version}. Restore creates a new version; history remains intact.</p><button className="btn" disabled={busy} onClick={() => { setBusy(true); void restoreMeetingVersion(selected.id, comparison.version).then(({ package: item }) => replace(item)).catch((error) => setMessage(String(error))).finally(() => setBusy(false)) }}>Restore v{comparison.version} as new version</button></div>}{selected.handoffs.length > 0 && <p className="footnote">Latest simulated hand-off: {selected.handoffs[selected.handoffs.length - 1]?.created_at}. No external message was sent.</p>}</div>
        </div>
      </>}
      {message && <div className="banner" role="status">{message}</div>}
    </div>
  )
}
