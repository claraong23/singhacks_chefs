import { useEffect, useMemo, useState } from 'react'
import {
  evaluateScenario,
  getSavedScenarios,
  getScenarioTemplates,
  saveScenario,
} from '../api'
import { usd } from '../format'
import type { Dossier, Insight, SavedScenario, ScenarioMetric, ScenarioTemplate } from '../types'

function displayMetric(metric: ScenarioMetric, value: number | null): string {
  if (value === null || !metric.available) return 'Not available'
  if (metric.unit === 'USD') return usd(value)
  if (metric.unit === '%' || metric.unit === 'pp') return `${value.toFixed(1)}${metric.unit}`
  if (metric.unit === 'HKD' || metric.unit === 'EUR') return `${metric.unit} ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}${metric.unit ? ` ${metric.unit}` : ''}`
}

function defaults(template: ScenarioTemplate | undefined): Record<string, number> {
  return Object.fromEntries((template?.inputs ?? []).map((input) => [input.key, input.default]))
}

export function ScenarioStudio({
  dossier,
  busy,
  onAttach,
}: {
  dossier: Dossier
  busy: boolean
  onAttach: (insight: Insight, scenario: SavedScenario) => Promise<void>
}) {
  const clientId = String(dossier.client.client_id)
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([])
  const [saved, setSaved] = useState<SavedScenario[]>([])
  const [templateId, setTemplateId] = useState('')
  const [optionId, setOptionId] = useState('')
  const [inputs, setInputs] = useState<Record<string, number>>({})
  const [result, setResult] = useState<SavedScenario['result'] | null>(null)
  const [name, setName] = useState('RM scenario')
  const [error, setError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([getScenarioTemplates(clientId), getSavedScenarios(clientId)])
      .then(([templatePayload, savedPayload]) => {
        if (!active) return
        setTemplates(templatePayload.templates)
        setSaved(savedPayload.scenarios)
        const first = templatePayload.templates[0]
        if (first) {
          setTemplateId(first.id)
          setInputs(defaults(first))
          setOptionId(dossier.options[first.insight_id]?.[0]?.id ?? '')
        }
      })
      .catch((reason: unknown) => active && setError(String(reason)))
    return () => { active = false }
  }, [clientId, dossier.options])

  const template = useMemo(() => templates.find((item) => item.id === templateId), [templateId, templates])
  const insight = dossier.insights.find((item) => item.id === template?.insight_id)
  const options = template ? dossier.options[template.insight_id] ?? [] : []
  const attachable = insight?.status === 'under_review' || insight?.status === 'rm_edited'

  const selectTemplate = (nextId: string) => {
    const next = templates.find((item) => item.id === nextId)
    setTemplateId(nextId)
    setInputs(defaults(next))
    setOptionId(next ? dossier.options[next.insight_id]?.[0]?.id ?? '' : '')
    setResult(null)
  }

  const payload = () => template ? {
    templateId: template.id,
    insightId: template.insight_id,
    optionId,
    inputs,
  } : null

  const evaluate = async () => {
    const request = payload()
    if (!request) return
    setWorking(true); setError(null)
    try {
      setResult((await evaluateScenario(clientId, request)).scenario)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setWorking(false)
    }
  }

  const save = async () => {
    const request = payload()
    if (!request || !name.trim()) return
    setWorking(true); setError(null)
    try {
      const scenario = (await saveScenario(clientId, name, request)).scenario
      setSaved((current) => [scenario, ...current])
      setResult(scenario.result)
    } catch (reason) {
      setError(String(reason))
    } finally {
      setWorking(false)
    }
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><h2>Scenario Studio</h2><span className="sub">Current-state arithmetic, not forecasts or recommendations</span></div>
        <div className="card-body">
          {templates.length === 0 && <div className="muted">No supported Scenario Studio comparison exists for this client. Existing RM action options remain available.</div>}
          {templates.length > 0 && template && (
            <>
              <label className="eyebrow" htmlFor="scenario-template">Finding to compare</label>
              <select id="scenario-template" className="select" value={templateId} onChange={(event) => selectTemplate(event.target.value)}>
                {templates.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
              </select>
              <p className="footnote">{template.description}</p>

              <div style={{ marginTop: 14 }}>
                <label className="eyebrow" htmlFor="scenario-option">Action option being explored</label>
                <select id="scenario-option" className="select" value={optionId} onChange={(event) => setOptionId(event.target.value)}>
                  {options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
                </select>
              </div>

              <div className="scenario-inputs" style={{ marginTop: 16 }}>
                {template.inputs.map((input) => (
                  <label className="fact" key={input.key}>
                    <span className="k">{input.label}</span>
                    <input
                      aria-label={input.label}
                      type="number"
                      min={input.minimum}
                      max={input.maximum}
                      step={input.step}
                      value={inputs[input.key] ?? input.default}
                      onChange={(event) => setInputs((current) => ({ ...current, [input.key]: Number(event.target.value) }))}
                    />
                    <span className="footnote">{input.minimum}–{input.maximum} {input.unit}. {input.help_text}</span>
                  </label>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
                <button className="btn primary" disabled={working || busy || !optionId} onClick={() => void evaluate()}>Compare with baseline</button>
                <input aria-label="Scenario name" className="input" value={name} onChange={(event) => setName(event.target.value)} />
                <button className="btn" disabled={working || busy || !result || !name.trim()} onClick={() => void save()}>Save comparison</button>
              </div>
            </>
          )}
          {error && <div className="banner" role="alert" style={{ marginTop: 14 }}>{error}</div>}
        </div>
      </div>

      {result && (
        <div className="card">
          <div className="card-head"><h2>{result.title}</h2><span className="sub">As of {result.as_of_date} · calculation {result.calculation_version}</span></div>
          <div className="card-body">
            <table className="postable">
              <thead><tr><th>Measure</th><th>Baseline</th><th>Scenario</th></tr></thead>
              <tbody>{result.metrics.map((metric) => (
                <tr key={metric.key}>
                  <td>{metric.label}<div className="footnote">{metric.detail}</div></td>
                  <td>{displayMetric(metric, metric.baseline)}</td>
                  <td>{displayMetric(metric, metric.scenario)}</td>
                </tr>
              ))}</tbody>
            </table>
            {result.blocked_checks.length > 0 && <div className="banner" style={{ marginTop: 14 }}><strong>Still unresolved.</strong> {result.blocked_checks.join(' ')}</div>}
            <div className="option-cols" style={{ marginTop: 16 }}>
              <div><div className="eyebrow">Assumptions</div><ul>{result.assumptions.map((item) => <li key={item.statement}>{item.statement}</li>)}</ul></div>
              <div><div className="eyebrow">Evidence</div><ul>{result.evidence.map((item) => <li key={`${item.source_file}-${item.row_or_id}-${item.field}`}>{item.source_file} · {item.row_or_id} · {item.field}</li>)}</ul></div>
            </div>
          </div>
        </div>
      )}

      {saved.length > 0 && (
        <div className="card">
          <div className="card-head"><h2>Saved comparisons</h2><span className="sub">Saving does not change workflow status</span></div>
          <div className="card-body">
            {saved.map((scenario) => {
              const scenarioInsight = dossier.insights.find((item) => item.id === scenario.result.insight_id)
              const canAttach = scenarioInsight?.status === 'under_review' || scenarioInsight?.status === 'rm_edited'
              return <div className="check" key={scenario.id}>
                <span className="mark pass">✓</span>
                <div style={{ flex: 1 }}><div>{scenario.name}</div><div className="d">{scenario.result.title} · {scenario.saved_at} · {scenario.result.calculation_version}</div></div>
                <button className="btn quiet" onClick={() => setResult(scenario.result)}>Load</button>
                <button className="btn" disabled={busy || !canAttach || !scenarioInsight} onClick={() => scenarioInsight && void onAttach(scenarioInsight, scenario)}>Attach to RM review</button>
              </div>
            })}
            {!attachable && insight && <div className="footnote" style={{ marginTop: 10 }}>Start RM review for this finding in “Why now” before attaching a saved comparison.</div>}
          </div>
        </div>
      )}
    </div>
  )
}
