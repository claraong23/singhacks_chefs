import { useCallback, useEffect, useState } from 'react'
import { getBook, getClient, recordDecision, resetDecision } from './api'
import type { BookView, Dossier, Insight, InsightStatus, SavedScenario } from './types'
import { BookWorkbench } from './components/BookWorkbench'
import { ClientDossier } from './components/ClientDossier'
import { shortDate } from './format'

export default function App() {
  const [book, setBook] = useState<BookView | null>(null)
  const [dossier, setDossier] = useState<Dossier | null>(null)
  const [clientId, setClientId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

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
        })
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

  return (
    <div className="shell">
      <header className="topbar">
        <div className="wordmark">
          Clarity<span>RM wealth intelligence</span>
        </div>
        <div className="topbar-meta">
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

        {book && !clientId && <BookWorkbench book={book} onOpenClient={openClient} />}

        {clientId && dossier && (
          <ClientDossier
            dossier={dossier}
            busy={busy}
            onDecide={decide}
            onReset={resetPlan}
            onAttachScenario={attachScenario}
            onBack={() => {
              setClientId(null)
              setDossier(null)
              window.history.replaceState(null, '', window.location.pathname)
              void loadBook()
            }}
          />
        )}
      </main>
    </div>
  )
}
