import { useCallback, useEffect, useState } from 'react'
import { clearWriteToken, getBook, getClient, getHealth, hasWriteToken, recordDecision, resetDecision, setWriteToken } from './api'
import type { BookView, Dossier, HealthStatus, Insight, InsightStatus, RMFeedbackInput, SavedScenario } from './types'
import type { SimulatedRole } from './types'
import { BookWorkbench } from './components/BookWorkbench'
import { ClientDossier } from './components/ClientDossier'
import { FollowThroughBoard } from './components/FollowThrough'
import { AuditConsole } from './components/AuditConsole'
import { CalibrationLab } from './components/CalibrationLab'
import { KnowledgeLibrary } from './components/KnowledgeReference'
import { HeroPage } from './components/HeroPage'
import { IntegrationSandbox } from './components/IntegrationSandbox'
import { shortDate, usd } from './format'

export default function App() {
  const [book, setBook] = useState<BookView | null>(null)
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [clientId, setClientId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [role, setRole] = useState<SimulatedRole>('rm')
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [writesUnlocked, setWritesUnlocked] = useState(hasWriteToken)
  const [view, setView] = useState<'book' | 'client' | 'follow' | 'audit' | 'calibration' | 'knowledge' | 'integrations'>('book')
  // A ?client= deep link goes straight to the dossier and skips the landing page.
  const [showHero, setShowHero] = useState(
    () => !new URLSearchParams(window.location.search).get('client'),
  )

  const loadBook = useCallback(async () => {
    try {
      setBook(await getBook())
    } catch (exception) {
      setError(String(exception))
    }
  }, [])

  useEffect(() => {
    void loadBook()
  }, [loadBook])

  useEffect(() => {
    void getHealth().then(setHealth).catch(() => undefined)
    const sync = () => setWritesUnlocked(hasWriteToken())
    window.addEventListener('clarity-write-access', sync)
    return () => window.removeEventListener('clarity-write-access', sync)
  }, [])

  const toggleWrites = () => {
    if (writesUnlocked) return clearWriteToken()
    const token = window.prompt('Enter the shared demo write token for this browser session.')
    if (token) setWriteToken(token)
  }

  const openClient = useCallback(async (id: string) => {
    setBusy(true)
    setError(null)
    try {
      const next = await getClient(id)
      setDossier(next)
      setClientId(id)
      const params = new URLSearchParams(window.location.search)
      params.set('client', id)
      window.history.replaceState(null, '', `?${params.toString()}`)
      setView('client')
      window.scrollTo({ top: 0 })
    } catch (exception) {
      setError(String(exception))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    const urlClient = new URLSearchParams(window.location.search).get('client')
    if (urlClient && !clientId) {
      void openClient(urlClient)
    }
  }, [clientId, openClient])

  const decide = useCallback(
    async (
      insight: Insight,
      input: {
        status: InsightStatus
        rmNote: string
        selectedOptionId: string | null
        editedNextStep: string | null
        selectedScenarioId?: string | null
        feedback?: RMFeedbackInput
      },
    ) => {
      setBusy(true)
      setError(null)
      try {
        await recordDecision(insight.id, {
          clientId: insight.client_id,
          status: input.status,
          rmNote: input.rmNote,
          selectedOptionId: input.selectedOptionId,
          editedNextStep: input.editedNextStep,
          selectedScenarioId: input.selectedScenarioId,
          role,
          feedback: input.feedback,
        })
        const [nextDossier] = await Promise.all([getClient(insight.client_id), loadBook()])
        setDossier(nextDossier)
      } catch (exception) {
        setError(String(exception))
      } finally {
        setBusy(false)
      }
    },
    [loadBook, role],
  )

  const resetPlan = useCallback(
    async (insight: Insight) => {
      setBusy(true)
      setError(null)
      try {
        await resetDecision(insight.id)
        const [nextDossier] = await Promise.all([getClient(insight.client_id), loadBook()])
        setDossier(nextDossier)
      } catch (exception) {
        setError(String(exception))
      } finally {
        setBusy(false)
      }
    },
    [loadBook],
  )

  const attachScenario = useCallback(
    async (insight: Insight, scenario: SavedScenario) => {
      await decide(insight, {
        status: 'rm_edited',
        rmNote: '',
        selectedOptionId: scenario.result.option_id,
        editedNextStep: null,
        selectedScenarioId: scenario.id,
      })
    },
    [decide],
  )

  if (showHero) {
    return <HeroPage onEnter={() => setShowHero(false)} clientCount={book?.totals?.clients} />
  }

  // §7 — hand-drawn monoweight icons, no icon library.
  const NAV: { id: typeof view; label: string; icon: JSX.Element }[] = [
    {
      id: 'book',
      label: 'Book',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <rect x="2.5" y="2.5" width="11" height="11" rx="1.5" />
          <path d="M5 6h6M5 8.5h6M5 11h3.5" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      id: 'follow',
      label: 'Follow-through',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <circle cx="8" cy="8" r="5.75" />
          <path d="M5.6 8.1l1.7 1.7 3.2-3.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
    },
    {
      id: 'integrations',
      label: 'Integration Sandbox',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <path d="M8 2l4.5 1.9v3.4c0 2.8-1.9 5.2-4.5 6.2-2.6-1-4.5-3.4-4.5-6.2V3.9L8 2z" strokeLinejoin="round" />
        </svg>
      ),
    },
    {
      id: 'calibration',
      label: 'Calibration Lab',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <path d="M2.5 5h11M2.5 11h11" strokeLinecap="round" />
          <circle cx="6" cy="5" r="1.6" />
          <circle cx="10.5" cy="11" r="1.6" />
        </svg>
      ),
    },
    {
      id: 'knowledge',
      label: 'Knowledge',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <path d="M3.5 2.5h6L12.5 5.5v8h-9z" strokeLinejoin="round" />
          <path d="M6 8h4M6 10.5h4" strokeLinecap="round" />
        </svg>
      ),
    },
    {
      id: 'audit',
      label: 'Audit',
      icon: (
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.3">
          <circle cx="8" cy="8" r="5.75" />
          <path d="M8 4.9V8l2.1 1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ),
    },
  ]

  // The panel groups the same ranked rows the book view shows, by the severity
  // the engine already assigned — no new taxonomy.
  const BANDS: { key: string; label: string }[] = [
    { key: 'critical', label: 'Critical' },
    { key: 'high', label: 'High' },
    { key: 'medium', label: 'Medium' },
    { key: 'low', label: 'Low' },
    { key: 'info', label: 'Info' },
  ]

  return (
    <div className="shell">
      <aside className="rail" aria-label="Sections">
        <span className="mark" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 14 14" fill="none">
            <path
              d="M3 10L6 6.5L8.5 8.5L11.5 4.5"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            <circle cx="11.5" cy="4.5" r="1.5" fill="currentColor" />
          </svg>
        </span>
        {NAV.map((item) => (
          <button
            key={item.id}
            aria-current={view === item.id}
            aria-label={item.label}
            title={item.label}
            onClick={() => setView(item.id)}
          >
            {item.icon}
          </button>
        ))}
        <span className="spacer" />
        <span className="who" title={book?.rm.rm_name ?? 'Relationship manager'}>
          {(book?.rm.rm_name ?? 'RM')
            .split(' ')
            .map((part) => part[0])
            .slice(0, 2)
            .join('')}
        </span>
      </aside>

      <aside className="bookpanel" aria-label="Client book">
        <div className="head">
          <h2>Morning Book</h2>
          <div className="meta">
            {book ? shortDate(book.as_of) : '—'} · {book?.rm.rm_name ?? '—'}
          </div>
        </div>
        <div className="list">
          {BANDS.map((band) => {
            const rows = (book?.clients ?? []).filter((row) => row.top_severity === band.key)
            if (!rows.length) return null
            return (
              <div key={band.key}>
                <div className={`band ${band.key}`}>
                  {band.label} · {rows.length}
                </div>
                {rows.map((row) => (
                  <button
                    key={row.client_id}
                    className={`row ${row.top_severity}`}
                    aria-current={clientId === row.client_id}
                    onClick={() => void openClient(row.client_id)}
                  >
                    <span className="top">
                      <span className="nm">{row.client_name}</span>
                      <span className="aum">{usd(row.total_usd)}</span>
                    </span>
                    <span className="why">{row.top_headline}</span>
                  </button>
                ))}
              </div>
            )
          })}
        </div>
        <div className="foot">
          <div className="critical">
            <div className="v">{book?.totals.critical ?? '—'}</div>
            <div className="k">Critical</div>
          </div>
          <div className="high">
            <div className="v">{book?.totals.high ?? '—'}</div>
            <div className="k">High</div>
          </div>
          <div className="rest">
            <div className="v">{book?.totals.insights ?? '—'}</div>
            <div className="k">Open</div>
          </div>
        </div>
      </aside>

      <div className="workspace">
      <header className="topbar">
        <div className="wordmark">
          Clarity<span>RM wealth intelligence</span>
        </div>
        <div className="topbar-meta">
          <label className="k">Simulated role<select className="select" value={role} onChange={(event) => setRole(event.target.value as SimulatedRole)}><option value="rm">RM</option><option value="credit">Credit specialist</option><option value="wealth_planning">Wealth planning</option><option value="investment">Investment specialist</option><option value="compliance_audit">Compliance / audit</option><option value="operations">Product operations</option></select></label>
          {health?.persistence?.write_access_required && <button className="btn quiet" onClick={toggleWrites}>{writesUnlocked ? 'Lock writes' : 'Unlock writes'}</button>}
          <div>
            <div className="k">Relationship manager</div>
            <div>{book?.rm?.rm_name ?? '—'}</div>
          </div>
          <div>
            <div className="k">Desk</div>
            <div>Asia · Singapore and Hong Kong</div>
          </div>
          <div>
            <div className="k">Position as at</div>
            <div>{book ? shortDate(book.as_of) : '—'}</div>
          </div>
        </div>
      </header>

      <main className="page">
        {error && (
          <div className="banner" role="alert">
            <strong>Could not reach the engine.</strong> {error}
            <div style={{ marginTop: 6 }}>
              Start it with <code>python -m clarity.api</code> from{' '}
              <code>clarity/backend</code>.
            </div>
          </div>
        )}

        {!book && !error && <div className="loading">Loading the book…</div>}

        {book && view === 'book' && <BookWorkbench book={book} onOpenClient={openClient} />}

        {view === 'follow' && <FollowThroughBoard role={role} onOpenClient={openClient} />}
        {book && view === 'integrations' && <IntegrationSandbox role={role} book={book} />}
        {view === 'calibration' && <CalibrationLab role={role} onActivePolicyChanged={() => void loadBook()} />}
        {view === 'knowledge' && <KnowledgeLibrary role={role} />}
        {view === 'audit' && <AuditConsole role={role} />}

        {view === 'client' && clientId && dossier && (
          <ClientDossier
            dossier={dossier}
            busy={busy}
            onDecide={decide}
            onReset={resetPlan}
            onAttachScenario={attachScenario}
            role={role}
            onBack={() => {
              setClientId(null)
              setDossier(null)
              window.history.replaceState(null, '', window.location.pathname)
              setView('book')
              void loadBook()
            }}
          />
        )}
      </main>
      </div>
    </div>
  )
}
