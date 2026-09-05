import { FormEvent, useEffect, useMemo, useState } from 'react'
import {
  acknowledgeWorkOrder, dispositionInboundIntegration, dispatchWorkOrder, getFollowThrough,
  getIntegrations, prepareWorkOrder, receiveInboundIntegration,
} from '../api'
import type { BookView, FollowThroughView, IntegrationView, SimulatedRole } from '../types'

const specialistOwners = [
  ['credit', 'Credit desk'], ['wealth_planning', 'Wealth planning'], ['investment', 'Investment specialist'],
]

function messageFor(error: unknown) { return error instanceof Error ? error.message : String(error) }

export function IntegrationSandbox({ role, book }: { role: SimulatedRole; book: BookView }) {
  const [view, setView] = useState<IntegrationView | null>(null)
  const [follow, setFollow] = useState<FollowThroughView | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [rationale, setRationale] = useState('')
  const [recordType, setRecordType] = useState<'task' | 'referral' | 'client_ready_finding'>('task')
  const refresh = () => {
    void getIntegrations(role).then(setView).catch((error) => setMessage(messageFor(error)))
    if (role === 'rm') void getFollowThrough('rm').then(setFollow).catch((error) => setMessage(messageFor(error)))
  }
  useEffect(refresh, [role]) // eslint-disable-line react-hooks/exhaustive-deps

  const records = useMemo(() => recordType === 'task' ? follow?.tasks ?? [] : follow?.referrals ?? [], [follow, recordType])
  const submitInbound = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const data = new FormData(event.currentTarget); setMessage(null)
    try {
      const result = await receiveInboundIntegration({ role, source_system: data.get('source_system'), external_event_id: data.get('external_event_id'), schema_version: 'v1', client_id: data.get('client_id'), affected_insight_ids: [data.get('insight_id')], source_ref: data.get('source_ref'), summary: data.get('summary'), occurred_at: data.get('occurred_at') })
      setMessage(result.replayed ? 'Replay recognised: the original inbound event was returned.' : 'Inbound event validated locally. Accept or reject it with an Operations rationale.')
      event.currentTarget.reset(); refresh()
    } catch (error) { setMessage(messageFor(error)) }
  }
  const disposition = async (id: string, action: 'accept' | 'reject') => {
    try { await dispositionInboundIntegration(id, action, role, rationale); setMessage(`Inbound event ${action}ed. ${action === 'accept' ? 'A governed evidence update and re-evaluation request were created.' : ''}`); setRationale(''); refresh() } catch (error) { setMessage(messageFor(error)) }
  }
  const submitWorkOrder = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const data = new FormData(event.currentTarget); setMessage(null)
    try {
      const result = await prepareWorkOrder({ role, destination: data.get('destination'), work_record_type: recordType, work_record_id: data.get('work_record_id'), client_id: data.get('client_id'), owner_role: data.get('owner_role') })
      setMessage(result.replayed ? 'Replay recognised: the original work order was returned.' : 'Work order prepared locally. It has not contacted a CRM or specialist system.')
      refresh()
    } catch (error) { setMessage(messageFor(error)) }
  }

  if (!view) return <div className="loading">Loading integration sandbox…</div>
  return <div className="stack">
    <div className="card"><div className="card-head"><h1>Integration Sandbox</h1><span className="sub">Local simulated integration · no bank system, CRM, client message, trade, or execution</span></div><div className="card-body"><p className="footnote" style={{ margin: 0 }}>This replayable boundary records source and schema lineage, then uses the existing evidence-update and re-evaluation workflow. It never rewrites CSV source data or historical decisions, scenarios, or meeting packages.</p></div></div>

    {role === 'operations' && <form className="card" onSubmit={(event) => void submitInbound(event)}><div className="card-head"><h2>Receive simulated inbound update</h2><span className="sub">Product Operations only</span></div><div className="card-body"><div className="grid2"><select className="select" name="source_system" defaultValue="lending_credit">{view.capabilities.source_systems.map((item) => <option key={item} value={item}>{item.replace('_', ' ')}</option>)}</select><input className="input" name="external_event_id" required placeholder="External event ID" /><select className="select" name="client_id" defaultValue="CL-0014">{book.clients.map((client) => <option key={client.client_id} value={client.client_id}>{client.client_id} · {client.client_name}</option>)}</select><input className="input" name="insight_id" required placeholder="Affected finding ID" /><input className="input" name="source_ref" required placeholder="Controlled source reference" /><input className="input" type="date" name="occurred_at" defaultValue="2026-08-26" required /></div><textarea className="rmnote" name="summary" required placeholder="What was received (workflow fact, not an analytics conclusion)" /><button className="btn primary">Validate simulated inbound event</button></div></form>}

    {role === 'rm' && <form className="card" onSubmit={(event) => void submitWorkOrder(event)}><div className="card-head"><h2>Prepare local work order</h2><span className="sub">CRM and specialist hand-offs remain simulated</span></div><div className="card-body"><div className="grid2"><select className="select" name="destination" defaultValue="crm"><option value="crm">CRM</option><option value="specialist_queue">Specialist queue</option></select><select className="select" value={recordType} onChange={(event) => setRecordType(event.target.value as typeof recordType)}><option value="task">Follow-up task</option><option value="referral">Specialist referral</option><option value="client_ready_finding">Client-ready finding</option></select></div><div className="grid2"><select className="select" name="client_id" defaultValue="CL-0014">{book.clients.map((client) => <option key={client.client_id} value={client.client_id}>{client.client_id} · {client.client_name}</option>)}</select>{recordType === 'client_ready_finding' ? <input className="input" name="work_record_id" required placeholder="Client-ready finding ID" /> : <select className="select" name="work_record_id" required><option value="">Choose existing {recordType}</option>{records.map((record) => <option key={record.id} value={record.id}>{String(record.title ?? record.summary ?? record.id)}</option>)}</select>}</div><label className="fact"><span>Assigned owner</span><select className="select" name="owner_role" defaultValue="rm"><option value="rm">RM (required for CRM)</option>{specialistOwners.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><button className="btn primary">Prepare simulated work order</button></div></form>}

    {role === 'operations' && <div className="card"><div className="card-head"><h2>Operations disposition</h2><span className="sub">Acceptance creates a tracked re-evaluation, not a data rewrite</span></div><div className="card-body"><textarea className="rmnote" value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Mandatory Operations rationale" />{view.inbound.length === 0 ? <p className="muted">No inbound events have been received.</p> : <table className="postable"><thead><tr><th>Source / version</th><th>Client</th><th>Validation</th><th>Disposition</th></tr></thead><tbody>{view.inbound.map((item) => <tr key={item.id}><td><strong>{item.source_system}</strong><div className="muted small">{item.external_event_id} · schema {item.schema_version}</div></td><td>{item.client_id}<div className="muted small">{item.source_ref}</div></td><td><span className="pill ghost">{item.validation_state}</span></td><td>{item.operations_disposition ?? <><button className="btn quiet" onClick={() => void disposition(item.id, 'accept')}>Accept</button><button className="btn quiet" onClick={() => void disposition(item.id, 'reject')}>Reject</button></>} {item.operations_disposition && <span className="pill ghost">{item.operations_disposition}</span>}</td></tr>)}</tbody></table>}</div></div>}

    <div className="card"><div className="card-head"><h2>Outbound work orders</h2><span className="sub">Every external reference is local and simulated</span></div><div className="card-body">{view.work_orders.length === 0 ? <p className="muted">No work orders are visible for this role.</p> : <table className="postable"><thead><tr><th>Destination / work</th><th>Owner</th><th>Status</th><th /></tr></thead><tbody>{view.work_orders.map((item) => <tr key={item.id}><td><strong>{item.destination.replace('_', ' ')}</strong><div className="muted small">{item.work_record_type} · v{item.work_record_version}</div></td><td>{item.owner_role}</td><td><span className="pill ghost">{item.status}</span><div className="muted small">{item.external_reference ?? 'Not dispatched'}</div></td><td>{role === 'rm' && item.status === 'prepared' && <button className="btn quiet" onClick={() => void dispatchWorkOrder(item.id, role).then(refresh).catch((error) => setMessage(messageFor(error)))}>Simulate dispatch</button>}{(['credit', 'wealth_planning', 'investment'] as SimulatedRole[]).includes(role) && item.status === 'dispatched' && <button className="btn quiet" onClick={() => void acknowledgeWorkOrder(item.id, role).then(refresh).catch((error) => setMessage(messageFor(error)))}>Acknowledge</button>}</td></tr>)}</tbody></table>}</div></div>
    {role === 'compliance_audit' && <div className="card"><div className="card-body"><p className="footnote" style={{ margin: 0 }}>Read-only reconstruction: inspect the unified Audit Console for inbound receipt, validation, Operations disposition, linked evidence/re-evaluation, work-order replay, dispatch, and acknowledgement events.</p></div></div>}
    {message && <div className="banner" role="status">{message}</div>}
  </div>
}
