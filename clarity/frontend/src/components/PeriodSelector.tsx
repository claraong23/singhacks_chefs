export const SNAPSHOTS = [
  { date: '2025-12-31', label: '31 Dec 2025', desc: 'Year-end 2025' },
  { date: '2026-02-27', label: '27 Feb 2026', desc: 'Pre-crisis benchmark' },
  { date: '2026-03-31', label: '31 Mar 2026', desc: 'Q1 Shock' },
  { date: '2026-06-30', label: '30 Jun 2026', desc: 'Mid-year 2026' },
  { date: '2026-08-26', label: '26 Aug 2026', desc: 'Latest position' },
]

interface PeriodSelectorProps {
  from: string
  to: string
  onChange: (from: string, to: string) => void
}

const PRESETS = [
  { label: 'Full Year', from: '2025-12-31', to: '2026-08-26' },
  { label: 'Q1 Shock', from: '2025-12-31', to: '2026-03-31' },
  { label: 'Q2 Recovery/Repricing', from: '2026-03-31', to: '2026-06-30' },
  { label: 'Recent (Q3)', from: '2026-06-30', to: '2026-08-26' },
]

export function PeriodSelector({ from, to, onChange }: PeriodSelectorProps) {
  const handleFromChange = (newFrom: string) => {
    if (newFrom >= to) {
      // automatically push 'to' forward if possible
      const availableTo = SNAPSHOTS.filter((s) => s.date > newFrom)
      if (availableTo.length > 0) {
        onChange(newFrom, availableTo[0].date)
      }
    } else {
      onChange(newFrom, to)
    }
  }

  const handleToChange = (newTo: string) => {
    if (newTo <= from) {
      // automatically pull 'from' backwards if possible
      const availableFrom = SNAPSHOTS.filter((s) => s.date < newTo)
      if (availableFrom.length > 0) {
        onChange(availableFrom[availableFrom.length - 1].date, newTo)
      }
    } else {
      onChange(from, newTo)
    }
  }

  return (
    <div
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        padding: '10px 14px',
        background: 'var(--surface-sunk)',
        border: '1px solid var(--rule)',
        borderRadius: 'var(--radius)',
        marginBottom: 16,
      }}
    >
      {/* Presets */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
        <span className="eyebrow" style={{ marginRight: 4 }}>
          Period Presets:
        </span>
        {PRESETS.map((p) => {
          const isSelected = from === p.from && to === p.to
          return (
            <button
              key={p.label}
              className={`chip ${isSelected ? 'active' : ''}`}
              style={{
                fontSize: 11.5,
                padding: '3px 10px',
                borderRadius: 100,
                border: '1px solid var(--rule)',
                background: isSelected ? 'var(--accent)' : 'var(--surface)',
                color: isSelected ? '#fff' : 'var(--ink-soft)',
                cursor: 'pointer',
                fontWeight: isSelected ? 600 : 400,
              }}
              onClick={() => onChange(p.from, p.to)}
            >
              {p.label}
            </button>
          )
        })}
      </div>

      {/* Granular Snapshot Selectors */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className="k" style={{ fontSize: 11.5, color: 'var(--muted)' }}>
          From:
        </span>
        <select
          className="select"
          style={{ padding: '4px 8px', fontSize: 12, width: 'auto' }}
          value={from}
          onChange={(e) => handleFromChange(e.target.value)}
        >
          {SNAPSHOTS.slice(0, -1).map((s) => (
            <option key={s.date} value={s.date}>
              {s.label} ({s.desc})
            </option>
          ))}
        </select>

        <span style={{ color: 'var(--muted)', fontSize: 12 }}>→</span>

        <span className="k" style={{ fontSize: 11.5, color: 'var(--muted)' }}>
          To:
        </span>
        <select
          className="select"
          style={{ padding: '4px 8px', fontSize: 12, width: 'auto' }}
          value={to}
          onChange={(e) => handleToChange(e.target.value)}
        >
          {SNAPSHOTS.filter((s) => s.date > from).map((s) => (
            <option key={s.date} value={s.date}>
              {s.label} ({s.desc})
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
