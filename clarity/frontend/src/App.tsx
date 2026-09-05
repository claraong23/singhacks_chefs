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
import { shortDate } from './format'

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
    return <HeroPage onEnter={() => setShowHero(false)} clientCount={book?.totals.clients} />
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wordmark">
          Clarity<span>RM wealth intelligence</span>
        </div>
        <div className="topbar-meta">
          <label className="k">Simulated role<select className="select" value={role} onChange={(event) => setRole(event.target.value as SimulatedRole)}><option value="rm">RM</option><option value="credit">Credit specialist</option><option value="wealth_planning">Wealth planning</option><option value="investment">Investment specialist</option><option value="compliance_audit">Compliance / audit</option><option value="operations">Product operations</option></select></label>
          {health?.persistence.write_access_required && <button className="btn quiet" onClick={toggleWrites}>{writesUnlocked ? 'Lock writes' : 'Unlock writes'}</button>}
          <div>
            <div className="k">Relationship manager</div>
            <div>{book?.rm.rm_name ?? '—'}</div>
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

      <nav className="tabs" aria-label="Application navigation">
        <button aria-current={view === 'book'} onClick={() => setView('book')}>Book</button>
        <button aria-current={view === 'follow'} onClick={() => setView('follow')}>Follow-through</button>
        <button aria-current={view === 'integrations'} onClick={() => setView('integrations')}>Integration Sandbox</button>
        <button aria-current={view === 'calibration'} onClick={() => setView('calibration')}>Calibration Lab</button>
        <button aria-current={view === 'knowledge'} onClick={() => setView('knowledge')}>Knowledge</button>
        <button aria-current={view === 'audit'} onClick={() => setView('audit')}>Audit</button>
      </nav>

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
  )
}
