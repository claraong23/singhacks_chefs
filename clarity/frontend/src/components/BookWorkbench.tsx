import { useMemo, useState } from 'react'
import type { BookView, Severity } from '../types'
import { pct, shortDate, titleCase, usd } from '../format'
import type { EventImpactView, EventSummary } from '../types'
import { getEventImpact, getEvents } from '../api'

const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low', 'info']

export function BookWorkbench({
  book,
  onOpenClient,
}: {
  book: BookView
  onOpenClient: (clientId: string) => void
}) {
  const [filter, setFilter] = useState<string>('all')
  const [centre, setCentre] = useState<string>('all')
  const [eventMode, setEventMode] = useState(false)
  const [events, setEvents] = useState<EventSummary[]>([])
  const [eventImpact, setEventImpact] = useState<EventImpactView | null>(null)
  const [eventBusy, setEventBusy] = useState(false)
  const [eventError, setEventError] = useState<string | null>(null)

  const openEventMode = async () => {
    setEventMode(true)
    if (events.length > 0) return
    setEventBusy(true)
    setEventError(null)
    try {
      const result = await getEvents()
      const newest = [...result.events].reverse()
      setEvents(newest)
      if (newest[0]) setEventImpact(await getEventImpact(newest[0].event_id))
    } catch (error) {
      setEventError(error instanceof Error ? error.message : 'Could not load events')
    } finally {
      setEventBusy(false)
    }
  }

  const chooseEvent = async (eventId: string) => {
    setEventBusy(true)
    setEventError(null)
    try {
      setEventImpact(await getEventImpact(eventId))
    } catch (error) {
      setEventError(error instanceof Error ? error.message : 'Could not map event')
    } finally {
      setEventBusy(false)
    }
  }

  const categories = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of book.clients) {
      for (const [key, value] of Object.entries(row.categories)) {
        counts.set(key, (counts.get(key) ?? 0) + value)
      }
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [book])

  const rows = book.clients.filter((row) => {
    if (centre !== 'all' && row.booking_centre !== centre) return false
    if (filter === 'all') return true
    if (filter === 'critical') return row.severity_counts.critical > 0
    return Boolean(row.categories[filter])
  })

  const [showTooltip, setShowTooltip] = useState(false)
  const [expandedFlags, setExpandedFlags] = useState<Record<string, boolean>>({})

  return (
    <div>
      <div className="book-head">
        <div>
          <div className="eyebrow">Morning brief · {shortDate(book.as_of)}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ margin: 0 }}>Who to call first</h1>
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <button
                type="button"
                aria-label="How priorities are ranked"
                aria-expanded={showTooltip}
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                onFocus={() => setShowTooltip(true)}
                onBlur={() => setShowTooltip(false)}
                onClick={() => setShowTooltip((v) => !v)}
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  border: '1px solid var(--rule-strong, #ccc)',
                  background: 'var(--surface-sunk, #f5f7fa)',
                  color: 'var(--accent, #002b49)',
                  fontWeight: 700,
                  fontSize: 12,
                  cursor: 'help',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                }}
              >
                ?
              </button>
              {showTooltip && (
                <div
                  role="tooltip"
                  style={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    marginTop: 8,
                    width: 360,
                    padding: '12px 14px',
                    background: 'var(--surface, #ffffff)',
                    border: '1px solid var(--rule, #e2e8f0)',
                    borderRadius: 'var(--radius, 6px)',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.18)',
                    zIndex: 999,
                    fontSize: 12,
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 5, color: 'var(--accent)' }}>
                    How Priorities Are Ranked
                  </div>
                  <p style={{ margin: '0 0 6px', color: 'var(--ink)' }}>
                    Priority scores (0–100) are computed deterministically using the bank's active policy:
                  </p>
                  <div style={{ background: 'var(--surface-sunk)', padding: '5px 8px', borderRadius: 4, fontFamily: 'var(--mono)', fontSize: 11, marginBottom: 6, border: '1px solid var(--rule)' }}>
                    Score = 45% Severity + 30% Materiality + 25% Urgency
                  </div>
                  <ul style={{ margin: '0 0 6px', paddingLeft: 16, color: 'var(--ink-soft)' }}>
                    <li><strong>Severity (45%):</strong> Critical (1.00), High (0.78), Medium (0.52), Low (0.30).</li>
                    <li><strong>Materiality (30%):</strong> Ratio of affected capital to total household wealth.</li>
                    <li><strong>Urgency (25%):</strong> Time pressure (e.g., margin call &lt; 30d = 1.0, 90d = 0.8, &gt; 1yr = 0.2).</li>
                  </ul>
                  <div style={{ fontSize: 11, color: 'var(--muted)', borderTop: '1px solid var(--rule)', paddingTop: 5 }}>
                    <strong>Hard overrides:</strong> Imminent Lombard margin calls, unhedged confirmed cash liabilities, and active mandate breaches force top ranking regardless of portfolio size.
                  </div>
                </div>
              )}
            </div>
          </div>
          <p style={{ marginTop: 5, color: 'var(--ink-soft)', fontSize: 13.5 }}>
            {book.totals.clients} clients · {usd(book.totals.aum_usd)} under advice · {book.totals.insights} open findings ({book.totals.critical} critical)
          </p>
        </div>
        <div className="kpis">
          <div className="stat">
            <span className="v">{book.totals.critical}</span>
            <span className="k">Critical</span>
          </div>
          <div className="stat">
            <span className="v">{book.totals.high}</span>
            <span className="k">High</span>
          </div>
          <div className="stat">
            <span className="v">
              {(book.totals.decisions.rm_reviewed ?? 0) + (book.totals.decisions.client_ready ?? 0)}
            </span>
            <span className="k">Reviewed by you</span>
          </div>
        </div>
      </div>

      {book.data_warnings.length > 0 && (
        <div className="banner">
          <strong>Data notice.</strong> {book.data_warnings.length} referential warning(s)
          found on load: {book.data_warnings.slice(0, 2).join('; ')}
        </div>
      )}

      <div className="filters">
        <button className="chip" aria-pressed={!eventMode} onClick={() => setEventMode(false)}>
          Client-first view
        </button>
        <button className="chip" aria-pressed={eventMode} onClick={() => void openEventMode()}>
          Event impact: who should I call?
        </button>
      </div>

      {eventMode && (
        <div className="stack">
          <div className="card">
            <div className="card-head"><h2>Event-to-client detection</h2><span className="sub">From event_log.csv, not live news or AI memory</span></div>
            <div className="card-body">
              <label>
                <span className="k">Select a dated event</span>
                <select
                  value={eventImpact?.event.event_id ?? ''}
                  disabled={eventBusy}
                  onChange={(event) => void chooseEvent(event.target.value)}
                  style={{ display: 'block', width: '100%', marginTop: 7, padding: 9 }}
                >
                  {events.map((event) => <option key={event.event_id} value={event.event_id}>{shortDate(event.event_date)} · {event.description}</option>)}
                </select>
              </label>
              {eventError && <div className="banner" style={{ marginTop: 12 }}>{eventError}</div>}
              {eventBusy && <p className="muted">Mapping the event to current holdings…</p>}
              {eventImpact && !eventBusy && (
                <>
                  <p><strong>{eventImpact.event.description}</strong></p>
                  <p className="muted">Transmission: {eventImpact.event.primary_transmission}. Mapped themes: {eventImpact.themes.map((theme) => theme.name).join(', ') || 'none'}.</p>
                  <table className="postable">
                    <thead><tr><th>Priority</th><th>Client</th><th>Mapped exposure</th><th>Estimated impact</th><th></th></tr></thead>
                    <tbody>
                      {eventImpact.affected_clients.map((item) => (
                        <tr key={`${item.client_id}-${item.theme_key}`}>
                          <td>{item.priority_score.toFixed(0)}</td>
                          <td><strong>{item.client_name}</strong><div className="footnote">{item.theme_name}</div></td>
                          <td>{usd(item.exposure_usd)} · {pct(item.exposure_pct)}</td>
                          <td>{item.estimated_impact_usd === null ? 'Exposure only' : `${usd(item.estimated_impact_usd)} · ${item.estimated_impact_pct?.toFixed(1)}%`}<div className="footnote">{item.scenario_name}{item.shock_pct === null ? '' : ` (${item.shock_pct > 0 ? '+' : ''}${item.shock_pct}%)`}</div></td>
                          <td><button className="btn" onClick={() => onOpenClient(item.client_id)}>Open client</button></td>
                        </tr>
                      ))}
                      {eventImpact.affected_clients.length === 0 && <tr><td colSpan={5} className="muted">No current holding maps to this event.</td></tr>}
                    </tbody>
                  </table>
                  {eventImpact.scenario_comparisons.length >= 2 && (
                    <div style={{ marginTop: 18 }}>
                      <div className="card-head" style={{ paddingLeft: 0, paddingRight: 0 }}>
                        <h2>What if conditions de-escalate or worsen?</h2>
                        <span className="sub">Side-by-side sensitivity, not a forecast</span>
                      </div>
                      <div className="grid2">
                        {eventImpact.scenario_comparisons.map((scenario) => (
                          <div className="card" key={scenario.key} style={{ background: 'var(--surface-sunk)' }}>
                            <div className="card-head">
                              <h3>{scenario.name}</h3>
                              <span className={`pill ${scenario.shock_pct < 0 ? 'low' : 'high'}`}>
                                {scenario.shock_pct > 0 ? '+' : ''}{scenario.shock_pct}% assumption
                              </span>
                            </div>
                            <div className="card-body">
                              <p style={{ marginTop: 0 }}>{scenario.description}</p>
                              <table className="postable">
                                <thead><tr><th>Client</th><th>Exposure</th><th>Estimated impact</th></tr></thead>
                                <tbody>
                                  {scenario.affected_clients.map((item) => (
                                    <tr key={`${scenario.key}-${item.client_id}`}>
                                      <td><button className="btn quiet" onClick={() => onOpenClient(item.client_id)}>{item.client_name}</button></td>
                                      <td>{usd(item.exposure_usd)}<div className="footnote">{pct(item.exposure_pct)} of household</div></td>
                                      <td>{usd(item.estimated_impact_usd)}<div className="footnote">{item.estimated_impact_pct > 0 ? '+' : ''}{item.estimated_impact_pct.toFixed(1)}% of household</div></td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="banner" style={{ marginTop: 12 }}>
                        <strong>Interpretation limit.</strong> These are linear sensitivity assumptions applied to mapped current holdings. They are not probabilities, forecasts or recommendations.
                      </div>
                    </div>
                  )}
                  <p className="footnote"><strong>Method.</strong> {eventImpact.method}. {eventImpact.limitations.join(' ')}</p>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {!eventMode && <div className="filters">
        <button className="chip" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
          All findings
        </button>
        <button className="chip" aria-pressed={filter === 'critical'} onClick={() => setFilter('critical')}>
          Critical only
        </button>
        {categories.map(([key, count]) => (
          <button key={key} className="chip" aria-pressed={filter === key} onClick={() => setFilter(key)}>
            {titleCase(key)} <span style={{ opacity: 0.6 }}>{count}</span>
          </button>
        ))}
        <span style={{ width: 16 }} />
        {['all', 'Singapore', 'Hong Kong'].map((value) => (
          <button key={value} className="chip" aria-pressed={centre === value} onClick={() => setCentre(value)}>
            {value === 'all' ? 'Both desks' : value}
          </button>
        ))}
      </div>}

      {!eventMode && <div className="card" style={{ overflow: 'hidden' }}>
        <table className="booktable">
          <thead>
            <tr>
              <th style={{ width: 210 }}>Client</th>
              <th style={{ width: 130 }}>Priority Score</th>
              <th>Flags to Address</th>
              <th style={{ width: 120, textAlign: 'right' }}>Wealth</th>
              <th style={{ width: 96 }}>Findings</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                className="row"
                key={row.client_id}
                tabIndex={0}
                onClick={() => onOpenClient(row.client_id)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    onOpenClient(row.client_id)
                  }
                }}
              >
                <td>
                  <div className="rankcell">
                    <span className="n">{row.rank}</span>
                    <div className="clientcell">
                      <div className="nm">{row.client_name}</div>
                      <div className="meta">
                        {row.client_id} · {row.booking_centre} · {row.risk_profile}
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <div className="scorebar">
                    <span className="v">
                      {row.priority_score.toFixed(0)}
                      <span style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 400, marginLeft: 1 }}>
                        /100
                      </span>
                    </span>
                    <span className="track">
                      <span
                        className={`fill ${row.top_severity}`}
                        style={{ width: `${Math.min(100, row.priority_score)}%` }}
                      />
                    </span>
                  </div>
                  <div className="meta" style={{ fontSize: 11, color: 'var(--ink-soft)', marginTop: 4, lineHeight: 1.35 }}>
                    {row.priority_explanation || titleCase(row.top_category ?? '')}
                  </div>
                </td>
                <td className="headlinecell">
                  {row.flags && row.flags.length > 0 ? (
                    <div className="flags-list" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {(expandedFlags[row.client_id] ? row.flags : row.flags.slice(0, 2)).map((flag, idx) => (
                        <div key={flag.id || idx} style={{ display: 'flex', alignItems: 'baseline', gap: 6, fontSize: 12.5 }}>
                          <span
                            className={`pill ${flag.severity}`}
                            style={{ fontSize: 9, padding: '1px 5px', textTransform: 'uppercase', flexShrink: 0 }}
                          >
                            {flag.severity}
                          </span>
                          <span style={{ fontWeight: idx === 0 ? 600 : 400, color: 'var(--ink)' }}>
                            {flag.headline}
                          </span>
                        </div>
                      ))}
                      {row.flags.length > 2 && (
                        <button
                          type="button"
                          className="btn quiet"
                          style={{
                            fontSize: 11,
                            padding: '2px 6px',
                            alignSelf: 'flex-start',
                            color: 'var(--accent)',
                            marginTop: 2,
                          }}
                          onClick={(e) => {
                            e.stopPropagation()
                            setExpandedFlags((prev) => ({
                              ...prev,
                              [row.client_id]: !prev[row.client_id],
                            }))
                          }}
                        >
                          {expandedFlags[row.client_id]
                            ? '▲ Show fewer'
                            : `… (+${row.flags.length - 2} more ${row.flags.length - 2 === 1 ? 'flag' : 'flags'})`}
                        </button>
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="h">{row.top_headline}</div>
                      <div className="why">{row.why_now.join(' · ')}</div>
                    </>
                  )}
                </td>
                <td style={{ textAlign: 'right' }}>
                  <div>{usd(row.total_usd)}</div>
                  <div className="meta" style={{ fontSize: 11, color: 'var(--muted)' }}>
                    {row.wealth_band} · {row.base_currency}
                  </div>
                </td>
                <td>
                  <div className="sevdots" title={SEVERITY_ORDER.map((s) => `${s}: ${row.severity_counts[s]}`).join(', ')}>
                    {SEVERITY_ORDER.flatMap((severity) =>
                      Array.from({ length: row.severity_counts[severity] }, (_, index) => (
                        <i className={severity} key={`${severity}-${index}`} />
                      )),
                    )}
                  </div>
                  <div className="meta" style={{ fontSize: 11, color: 'var(--muted)', marginTop: 5 }}>
                    {row.insight_count} open
                    {row.reviewed_count > 0 && ` · ${row.reviewed_count} reviewed`}
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} style={{ padding: 34, textAlign: 'center', color: 'var(--muted)' }}>
                  No clients match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>}

      <div className="footnote" style={{ maxWidth: '80ch' }}>
        <strong>How the ranking works.</strong> {book.scoring.formula}. Materiality is the{' '}
        {book.scoring.materiality}; urgency is {book.scoring.urgency}. {book.scoring.note}{' '}
        Dismissed findings drop out of the count but stay in the audit trail. Figures are
        as at {book.as_of}; percentages are of household wealth, aggregated across every
        portfolio a client holds including custody accounts. Coverage today:{' '}
        {pct((rows.length / book.clients.length) * 100, 0)} of the book shown.
      </div>
    </div>
  )
}
