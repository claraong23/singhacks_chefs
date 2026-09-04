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

  return (
    <div>
      <div className="book-head">
        <div>
          <div className="eyebrow">Morning brief · {shortDate(book.as_of)}</div>
          <h1>Who to call first</h1>
          <p>
            {book.totals.clients} clients, {usd(book.totals.aum_usd)} under advice.{' '}
            {book.totals.insights} open findings, of which {book.totals.critical} are
            critical. Ranked by a published formula, not by an opaque score — open any
            client to see the reasons behind their position.
          </p>
          {book.scoring.policy && <p className="footnote" style={{ marginBottom: 0 }}>Active priority policy: <strong>{book.scoring.policy.name}</strong> · severity {Math.round(book.scoring.policy.weights.severity * 100)}%, materiality {Math.round(book.scoring.policy.weights.materiality * 100)}%, urgency {Math.round(book.scoring.policy.weights.urgency * 100)}%.</p>}
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
                  <div className="meta" style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
                    {titleCase(row.top_category ?? '')}
                  </div>
                </td>
                <td className="headlinecell">
                  <div className="h">{row.top_headline}</div>
                  <div className="why">{row.why_now.join(' · ')}</div>
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
