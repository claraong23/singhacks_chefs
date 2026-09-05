import '../hero.css'

/** The landing page. Dark, per DESIGN.md; the workbench behind it keeps its
 *  own light system, so everything here is scoped to `.hero-page`. */
export function HeroPage({ onEnter, clientCount }: { onEnter: () => void; clientCount?: number }) {
  const stats = [
    // The client count is the live figure from the book; the rest are the
    // product claims from the reference hero, not computed values.
    { value: String(clientCount ?? 20), label: 'Client relationships' },
    { value: '3', label: 'Urgent actions today' },
    { value: '100%', label: 'Evidence-traced insights' },
    { value: '<90s', label: 'Brief to decision' },
  ]

  const pillars = [
    {
      icon: (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <circle cx="9" cy="9" r="7.5" stroke="currentColor" strokeWidth="1.2" />
          <path d="M6 9l2 2 4-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      ),
      title: 'Signal before noise',
      body:
        'Every insight is ranked by urgency and client outcome — not data volume. ' +
        'Priscilla sees who needs attention first, and why.',
    },
    {
      icon: (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <rect x="2" y="2" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.2" />
          <path d="M5 9h8M5 6h5M5 12h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
        </svg>
      ),
      title: 'Every claim, sourced',
      body:
        'Facts trace back to CSV row, date, and calculation. AI drafts narrative — ' +
        'it never calculates, ranks, or acts without RM review.',
    },
    {
      icon: (
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
          <path d="M9 2v5M9 11v5M2 9h5M11 9h5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          <circle cx="9" cy="9" r="2.5" stroke="currentColor" strokeWidth="1.2" />
        </svg>
      ),
      title: 'Human in the loop',
      body:
        'No action reaches a client without the RM editing, approving, or dismissing it. ' +
        'Suitability gates enforce this — not convention.',
    },
  ]

  return (
    <div className="hero-page">
      <nav className="hero-nav">
        <div className="hero-brand">
          <span className="hero-mark">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path
                d="M3 10L6 6.5L8.5 8.5L11.5 4.5"
                stroke="white"
                strokeWidth="1.6"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              <circle cx="11.5" cy="4.5" r="1.5" fill="white" />
            </svg>
          </span>
          <span className="hero-wordmark">Clarity</span>
        </div>
        <button className="hero-nav-cta" onClick={onEnter}>
          Open workbench
        </button>
      </nav>

      <div className="hero-body">
        <h1 className="hero-headline">
          From client book
          <br />
          <em>to best conversation.</em>
        </h1>

        <p className="hero-sub">
          Clarity turns a fragmented twenty-client book into a defensible next action, with
          every insight sourced, every gate checked, and every step controlled by the RM.
        </p>

        <div className="hero-ctas">
          <button className="hero-cta-primary" onClick={onEnter}>
            Open Morning Book
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <path
                d="M3 7h8M8 4l3 3-3 3"
                stroke="white"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          <button
            className="hero-cta-secondary"
            onClick={() =>
              document.getElementById('hero-how-it-works')?.scrollIntoView({ behavior: 'smooth' })
            }
          >
            Watch demo
          </button>
        </div>

        <div className="hero-stats">
          {stats.map((stat) => (
            <div className="hero-stat" key={stat.label}>
              <div className="hero-stat-value">{stat.value}</div>
              <div className="hero-stat-label">{stat.label}</div>
            </div>
          ))}
        </div>

        <div className="hero-pillars">
          <div className="hero-eyebrow" id="hero-how-it-works">
            HOW IT WORKS
          </div>
          <div className="hero-pillar-grid">
            {pillars.map((pillar) => (
              <div className="hero-pillar" key={pillar.title}>
                <div className="hero-pillar-icon">{pillar.icon}</div>
                <div className="hero-pillar-title">{pillar.title}</div>
                <div className="hero-pillar-body">{pillar.body}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
