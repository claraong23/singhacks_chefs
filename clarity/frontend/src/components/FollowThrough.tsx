import { FormEvent, useEffect, useState } from 'react'
import {
  createEvidenceUpdate, createFollowTask, createOutcome, createReferral,
  getFollowThrough, updateFollowRecord,
} from '../api'
import type { Dossier, FollowThroughRecord, FollowThroughView, SimulatedRole, WorkStatus } from '../types'

const ownerLabels: Record<string, string> = { rm: 'RM', credit: 'Credit desk', wealth_planning: 'Wealth planning', investment: 'Investment specialist', operations: 'Product operations' }
function text(record: FollowThroughRecord, key: string) { return String(record[key] ?? '') }

function Records({ title, records, role, onUpdate }: { title: string; records: FollowThroughRecord[]; role: SimulatedRole; onUpdate: () => void }) {
  const update = async (record: FollowThroughRecord, status: WorkStatus | 'queued' | 'acknowledged' | 'complete') => {
    const reason = (status === 'completed' || status === 'cancelled' || status === 'complete') ? window.prompt('Record the completion rationale.') ?? '' : ''
    try { await updateFollowRecord(record.kind === 'reevaluation' ? 'reevaluations' : record.kind === 'referral' ? 'referrals' : 'tasks', record.id, role, status, reason); onUpdate() } catch { /* board refresh retains visible state */ }
  }
  return <div className="card"><div className="card-head"><h3>{title}</h3><span className="sub">{records.length}</span></div><div className="card-body">{records.length === 0 ? <p className="muted small" style={{ margin: 0 }}>Nothing recorded.</p> : <table className="postable"><thead><tr><th>Work</th><th>Owner</th><th>Due/status</th><th /></tr></thead><tbody>{records.map((record) => <tr key={record.id}><td><strong>{text(record, 'title') || text(record, 'summary') || text(record, 'outcome_type')}</strong><div className="muted small">{text(record, 'description') || text(record, 'statement')}</div></td><td>{ownerLabels[text(record, 'owner_role')] ?? text(record, 'owner_role')}</td><td>{text(record, 'due_date')}<br /><span className="pill ghost">{text(record, 'status')}</span></td><td>{(role === 'rm' || text(record, 'owner_role') === role || (role === 'operations' && text(record, 'kind') === 'reevaluation')) && ['open', 'in_progress', 'waiting', 'queued', 'acknowledged'].includes(text(record, 'status')) && <button className="btn quiet" onClick={() => void update(record, text(record, 'kind') === 'reevaluation' ? 'complete' : 'completed')}>Complete</button>}</td></tr>)}</tbody></table>}</div></div>
}

export function FollowThroughPanel({ dossier, role }: { dossier: Dossier; role: SimulatedRole }) {
  const clientId = String(dossier.client.client_id)
  const [view, setView] = useState<FollowThroughView>(dossier.follow_through)
  const [message, setMessage] = useState<string | null>(null)
  const refresh = () => void getFollowThrough(role, clientId).then(setView).catch((error) => setMessage(String(error)))
  useEffect(refresh, [clientId, role]) // eslint-disable-line react-hooks/exhaustive-deps
  const submit = async (event: FormEvent<HTMLFormElement>, kind: 'task' | 'referral' | 'outcome' | 'evidence') => {
    event.preventDefault(); const form = new FormData(event.currentTarget); setMessage(null)
    const base = { role, client_id: clientId, insight_id: String(form.get('insight_id') || '') || undefined }
    try {
      if (kind === 'task') await createFollowTask({ ...base, title: form.get('title'), owner_role: form.get('owner_role'), due_date: form.get('due_date'), description: form.get('description'), evidence_refs: ['clients.csv:' + clientId] })
      if (kind === 'referral') await createReferral({ ...base, referral_type: form.get('referral_type'), owner_role: form.get('owner_role'), due_date: form.get('due_date'), summary: form.get('summary'), evidence_refs: ['clients.csv:' + clientId] })
      if (kind === 'outcome') await createOutcome({ ...base, outcome_type: form.get('outcome_type'), statement: form.get('statement'), requested_documents: String(form.get('documents') || '').split(',').map((item) => item.trim()).filter(Boolean) })
      if (kind === 'evidence') await createEvidenceUpdate({ role, client_id: clientId, source_type: form.get('source_type'), source_ref: form.get('source_ref'), summary: form.get('summary'), affected_insight_ids: [String(form.get('insight_id'))] })
      event.currentTarget.reset(); refresh()
    } catch (error) { setMessage(String(error)) }
  }
  const insights = dossier.insights
  const insightSelect = <select className="select" name="insight_id">{insights.map((item) => <option value={item.id} key={item.id}>{item.headline}</option>)}</select>
  return <div className="stack">
    <div className="card"><div className="card-head"><h2>Follow-through</h2><span className="sub">Historical decisions remain unchanged when new information arrives</span></div><div className="card-body"><p className="footnote" style={{ margin: 0 }}>Current role: <strong>{ownerLabels[role] ?? role}</strong>. Client statements and documents are recorded as workflow evidence, never silently written into source CSVs.</p></div></div>
    {role === 'rm' && <div className="grid2"><form className="card" onSubmit={(event) => void submit(event, 'task')}><div className="card-head"><h3>Assign follow-up task</h3></div><div className="card-body"><input className="input" name="title" required placeholder="Task title" /><label className="fact"><span>Finding</span>{insightSelect}</label><label className="fact"><span>Owner</span><select className="select" name="owner_role" defaultValue="rm">{Object.entries(ownerLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><input className="input" name="due_date" type="date" min="2026-08-26" required /><textarea className="rmnote" name="description" placeholder="Accountable next step" /><button className="btn primary">Create task</button></div></form><form className="card" onSubmit={(event) => void submit(event, 'referral')}><div className="card-head"><h3>Refer specialist</h3></div><div className="card-body"><label className="fact"><span>Finding</span>{insightSelect}</label><select className="select" name="referral_type" defaultValue="credit"><option value="credit">Credit</option><option value="wealth_planning">Wealth planning</option><option value="compliance">Compliance</option><option value="investment">Investment</option><option value="operations">Operations</option></select><select className="select" name="owner_role" defaultValue="credit"><option value="credit">Credit desk</option><option value="wealth_planning">Wealth planning</option><option value="investment">Investment specialist</option><option value="operations">Product operations</option></select><input className="input" name="due_date" type="date" min="2026-08-26" required /><textarea className="rmnote" name="summary" required placeholder="Referral reason and open question" /><button className="btn primary">Create referral</button></div></form></div>}
    {role === 'rm' && <form className="card" onSubmit={(event) => void submit(event, 'outcome')}><div className="card-head"><h3>Record meeting outcome</h3><span className="sub">Client statement, not verified portfolio fact</span></div><div className="card-body"><div className="grid2"><label className="fact"><span>Finding</span>{insightSelect}</label><select className="select" name="outcome_type"><option value="discussed">Discussed</option><option value="preference_confirmed">Preference confirmed</option><option value="preference_changed">Preference changed</option><option value="document_requested">Document requested</option><option value="document_received">Document received</option></select></div><textarea className="rmnote" name="statement" required placeholder="What the client said or agreed" /><input className="input" name="documents" placeholder="Requested documents, comma-separated" /><button className="btn primary">Record outcome</button></div></form>}
    {role === 'operations' && <form className="card" onSubmit={(event) => void submit(event, 'evidence')}><div className="card-head"><h3>Record new evidence</h3><span className="sub">Creates a re-evaluation request; it does not change source data</span></div><div className="card-body"><label className="fact"><span>Affected finding</span>{insightSelect}</label><select className="select" name="source_type"><option value="document">Document</option><option value="client_statement">Client statement</option><option value="specialist_response">Specialist response</option></select><input className="input" name="source_ref" required placeholder="Controlled source reference" /><textarea className="rmnote" name="summary" required placeholder="What was received" /><button className="btn primary">Record evidence update</button></div></form>}
    <Records title="Follow-up tasks" records={view.tasks} role={role} onUpdate={refresh} /><Records title="Specialist referrals" records={view.referrals} role={role} onUpdate={refresh} /><Records title="Meeting outcomes" records={view.outcomes} role={role} onUpdate={refresh} /><Records title="Evidence updates" records={view.evidence_updates} role={role} onUpdate={refresh} /><Records title="Re-evaluation requests" records={view.reevaluations} role={role} onUpdate={refresh} />
    {message && <div className="banner" role="status">{message}</div>}
  </div>
}

export function FollowThroughBoard({ role, onOpenClient }: { role: SimulatedRole; onOpenClient: (id: string) => void }) {
  const [view, setView] = useState<FollowThroughView | null>(null)
  useEffect(() => { void getFollowThrough(role).then(setView) }, [role])
  if (!view) return <div className="loading">Loading follow-through…</div>
  const work = [...view.tasks, ...view.referrals, ...view.reevaluations].filter((item) => !['completed', 'cancelled', 'complete'].includes(text(item, 'status')))
  return <div className="stack"><div className="card"><div className="card-head"><h1>Follow-through board</h1><span className="sub">Open work visible to {ownerLabels[role] ?? role}</span></div><div className="card-body">{work.length === 0 ? <p className="muted">No open work is visible for this role.</p> : <table className="postable"><thead><tr><th>Client</th><th>Work</th><th>Owner</th><th>Due</th></tr></thead><tbody>{work.map((item) => <tr key={item.id}><td><button className="btn quiet" onClick={() => onOpenClient(item.client_id)}>{item.client_id}</button></td><td>{text(item, 'title') || text(item, 'summary') || 'Re-evaluation request'}</td><td>{ownerLabels[text(item, 'owner_role')] ?? text(item, 'owner_role')}</td><td>{text(item, 'due_date') || text(item, 'status')}</td></tr>)}</tbody></table>}</div></div></div>
}
