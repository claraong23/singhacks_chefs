import { useEffect, useMemo, useState } from 'react'
import { getAudit } from '../api'
import type { AuditTimelineEvent, SimulatedRole } from '../types'

export function AuditConsole({ role }: { role: SimulatedRole }) {
  const [events, setEvents] = useState<AuditTimelineEvent[]>([])
  const [origin, setOrigin] = useState('')
  const [clientId, setClientId] = useState('')
  useEffect(() => { void getAudit({ ...(origin ? { origin } : {}), ...(clientId ? { client_id: clientId } : {}) }).then(({ audit }) => setEvents(audit)) }, [origin, clientId])
  const visible = useMemo(() => role === 'compliance_audit' || role === 'rm' || role === 'operations' ? events : events.filter((item) => item.actor.includes(role.toUpperCase().split('_')[0])), [events, role])
  return <div className="stack"><div className="card"><div className="card-head"><h1>Audit Console</h1><span className="sub">Source data, deterministic system activity, and user decisions remain separate</span></div><div className="card-body"><div className="grid2"><label className="fact"><span>Origin</span><select className="select" value={origin} onChange={(event) => setOrigin(event.target.value)}><option value="">All origins</option><option value="source_data">Source data</option><option value="system">System</option><option value="user_decision">User decision</option></select></label><label className="fact"><span>Client ID</span><input className="input" value={clientId} onChange={(event) => setClientId(event.target.value)} placeholder="e.g. CL-0014" /></label></div></div></div><div className="card"><div className="card-head"><h2>Reconstructable timeline</h2><span className="sub">{visible.length} events</span></div><div className="card-body"><table className="postable"><thead><tr><th>When</th><th>Origin</th><th>Action</th><th>Object</th><th>Actor</th></tr></thead><tbody>{visible.map((event) => <tr key={event.id}><td className="muted">{event.timestamp}</td><td><span className="pill ghost">{event.origin.replace('_', ' ')}</span></td><td>{event.action}</td><td>{event.object_type} · {event.client_id ?? 'book'}</td><td>{event.actor}</td></tr>)}</tbody></table>{visible.length === 0 && <p className="muted">No events match these filters.</p>}</div></div></div>
}
