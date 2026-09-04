import { useEffect, useState } from 'react'
import { createPriorityPolicy, getPriorityPolicies, getPriorityPolicyEvaluation, priorityPolicyAction } from '../api'
import type { PriorityPolicy, PriorityPolicyEvaluation, SimulatedRole } from '../types'

type PolicyView = { active_policy: PriorityPolicy; policies: PriorityPolicy[]; templates: Record<string, { name: string; weights: PriorityPolicy['weights'] }> }
const emptyWeights = { severity: 0.45, materiality: 0.30, urgency: 0.25 }

export function CalibrationLab({ role, onActivePolicyChanged }: { role: SimulatedRole; onActivePolicyChanged: () => void }) {
  const [view, setView] = useState<PolicyView | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [evaluation, setEvaluation] = useState<PriorityPolicyEvaluation | null>(null)
  const [template, setTemplate] = useState('baseline')
  const [name, setName] = useState('')
  const [weights, setWeights] = useState(emptyWeights)
  const [rationale, setRationale] = useState('')
  const [decisionRationale, setDecisionRationale] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  const refresh = () => void getPriorityPolicies().then((next) => {
    setView(next)
    if (!selected) setSelected(next.active_policy.id)
  }).catch((error) => setMessage(String(error)))
  useEffect(refresh, []) // eslint-disable-line react-hooks/exhaustive-deps

  const loadEvaluation = (policyId: string) => {
    setSelected(policyId)
    void getPriorityPolicyEvaluation(policyId).then(({ evaluation: next }) => setEvaluation(next)).catch((error) => setMessage(String(error)))
  }

  useEffect(() => { if (selected) loadEvaluation(selected) }, [selected]) // eslint-disable-line react-hooks/exhaustive-deps

  const selectedPolicy = view?.policies.find((policy) => policy.id === selected) ?? null
  const applyTemplate = (key: string) => {
    setTemplate(key)
    if (key !== 'custom' && view?.templates[key]) setWeights(view.templates[key].weights)
  }
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      const payload = template === 'custom'
        ? { role: 'rm', name, weights, rationale }
        : { role: 'rm', template, name, rationale }
      const response = selectedPolicy?.status === 'draft'
        ? await priorityPolicyAction(selectedPolicy.id, 'revise', { role: 'rm', name, weights, rationale })
        : await createPriorityPolicy(payload)
      setSelected(response.policy.id)
      setEvaluation(response.evaluation ?? null)
      setMessage('Draft policy saved. Compare its shadow ranking before submitting it.')
      refresh()
    } catch (error) { setMessage(String(error)) }
  }
  const act = async (action: 'submit' | 'approve' | 'reject') => {
    if (!selectedPolicy) return
    try {
      await priorityPolicyAction(selectedPolicy.id, action, { role, rationale: decisionRationale })
      setMessage(action === 'approve' ? 'Policy activated. The live Book will now use this published version.' : `Policy ${action}ed.`)
      setDecisionRationale('')
      refresh()
      loadEvaluation(selectedPolicy.id)
      if (action === 'approve') onActivePolicyChanged()
    } catch (error) { setMessage(String(error)) }
  }

  return <div className="stack">
    <div className="card"><div className="card-head"><h1>Calibration Lab</h1><span className="sub">Transparent policy validation — no predictive model</span></div><div className="card-body">
      <p style={{ marginTop: 0 }}>The active Book uses <strong>{view?.active_policy.name ?? 'the published baseline'}</strong>. Candidates re-score the same deterministic signals; they never alter thresholds, evidence, client decisions, or action gates.</p>
      <div className="facts"><div className="fact"><div className="k">Severity</div><div className="v">{((view?.active_policy.weights.severity ?? .45) * 100).toFixed(0)}%</div></div><div className="fact"><div className="k">Materiality</div><div className="v">{((view?.active_policy.weights.materiality ?? .30) * 100).toFixed(0)}%</div></div><div className="fact"><div className="k">Urgency</div><div className="v">{((view?.active_policy.weights.urgency ?? .25) * 100).toFixed(0)}%</div></div></div>
    </div></div>

    {role === 'rm' && <form className="card" onSubmit={(event) => void save(event)}><div className="card-head"><h2>{selectedPolicy?.status === 'draft' ? 'Revise selected draft' : 'Propose a policy'}</h2><span className="sub">Weights must be non-negative and total 100%</span></div><div className="card-body">
      <div className="grid2"><label className="fact"><span>Starting template</span><select className="select" value={template} onChange={(event) => applyTemplate(event.target.value)}><option value="baseline">Published baseline</option><option value="urgency_first">Urgency-first</option><option value="materiality_first">Materiality-first</option><option value="custom">Custom weights</option></select></label><label className="fact"><span>Policy name</span><input className="input" value={name} onChange={(event) => setName(event.target.value)} required placeholder="e.g. Review-period candidate" /></label></div>
      <div className="grid2">{(['severity', 'materiality', 'urgency'] as const).map((key) => <label className="fact" key={key}><span>{key[0].toUpperCase() + key.slice(1)} weight</span><input className="input" type="number" min="0" max="1" step="0.01" disabled={template !== 'custom'} value={weights[key]} onChange={(event) => setWeights({ ...weights, [key]: Number(event.target.value) })} /></label>)}</div>
      <textarea className="rmnote" required value={rationale} onChange={(event) => setRationale(event.target.value)} placeholder="Why should this policy be evaluated?" /><button className="btn primary">{selectedPolicy?.status === 'draft' ? 'Save revision' : 'Create draft candidate'}</button>
    </div></form>}

    <div className="card"><div className="card-head"><h2>Policy versions</h2><span className="sub">One active policy at a time</span></div><div className="card-body"><table className="postable"><thead><tr><th>Policy</th><th>Status</th><th>Weights</th><th /></tr></thead><tbody>{view?.policies.map((policy) => <tr key={policy.id}><td><strong>{policy.name}</strong><div className="muted small">{policy.rationale}</div></td><td><span className="pill ghost">{policy.status}</span></td><td>{Object.values(policy.weights).map((weight) => `${Math.round(weight * 100)}%`).join(' / ')}</td><td><button className="btn quiet" onClick={() => loadEvaluation(policy.id)}>Compare</button></td></tr>)}</tbody></table></div></div>

    {evaluation && <div className="card"><div className="card-head"><h2>Shadow comparison</h2><span className={`pill ${evaluation.activation_eligible ? 'accent' : 'ghost'}`}>{evaluation.activation_eligible ? 'Eligible for approval' : 'Validation incomplete'}</span></div><div className="card-body">
      <div className="facts"><div className="fact"><div className="k">Final feedback</div><div className="v">{evaluation.feedback_count}</div></div><div className="fact"><div className="k">Anchor coverage</div><div className="v">{evaluation.anchor_coverage.length} / 3</div></div><div className="fact"><div className="k">Top-five relevance</div><div className="v">{evaluation.top_five_relevance_rate === null ? 'Not enough labels' : `${Math.round(evaluation.top_five_relevance_rate * 100)}%`}</div></div><div className="fact"><div className="k">Urgency alignment</div><div className="v">{evaluation.urgency_alignment_rate === null ? 'Not enough labels' : `${Math.round(evaluation.urgency_alignment_rate * 100)}%`}</div></div></div>
      {evaluation.warnings.map((warning) => <div className="banner" key={warning} style={{ marginTop: 8 }}>{warning}</div>)}
      <table className="postable" style={{ marginTop: 12 }}><thead><tr><th>Client</th><th>Candidate rank</th><th>Active rank</th><th>Score change</th></tr></thead><tbody>{evaluation.rank_changes.slice(0, 8).map((item) => <tr key={item.client_id}><td>{item.client_id}<div className="muted small">{item.headline}</div></td><td>{item.candidate_rank} ({item.rank_delta >= 0 ? '+' : ''}{item.rank_delta})</td><td>{item.active_rank}</td><td>{item.active_score} → {item.candidate_score}</td></tr>)}</tbody></table>
      {selectedPolicy && (selectedPolicy.status === 'draft' || (selectedPolicy.status === 'submitted' && role === 'compliance_audit')) && <div style={{ marginTop: 14 }}><textarea className="rmnote" value={decisionRationale} onChange={(event) => setDecisionRationale(event.target.value)} placeholder={role === 'rm' ? 'Why submit this candidate for Compliance/Audit review?' : 'Compliance/Audit decision rationale'} />{selectedPolicy.status === 'draft' && role === 'rm' && <button className="btn primary" onClick={() => void act('submit')}>Submit for Compliance/Audit</button>}{selectedPolicy.status === 'submitted' && role === 'compliance_audit' && <><button className="btn primary" disabled={!evaluation.activation_eligible} onClick={() => void act('approve')}>Approve and activate</button><button className="btn" style={{ marginLeft: 8 }} onClick={() => void act('reject')}>Reject candidate</button></>}</div>}
    </div></div>}
    {message && <div className="banner" role="status">{message}</div>}
  </div>
}
