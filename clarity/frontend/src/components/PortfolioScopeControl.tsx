import type { PortfolioView } from '../types'
import { usd } from '../format'

interface PortfolioScopeControlProps {
  portfolios: PortfolioView[]
  selectedPortfolio: string
  onChange: (portfolioId: string) => void
}

export function PortfolioScopeControl({
  portfolios,
  selectedPortfolio,
  onChange,
}: PortfolioScopeControlProps) {
  if (!portfolios || portfolios.length <= 1) {
    return null
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        marginBottom: 14,
        flexWrap: 'wrap',
      }}
    >
      <span className="eyebrow" style={{ fontSize: 11 }}>
        Portfolio Scope:
      </span>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button
          className="chip"
          style={{
            fontSize: 12,
            padding: '3px 12px',
            borderRadius: 100,
            border: '1px solid var(--rule)',
            background: selectedPortfolio === 'all' ? 'var(--accent)' : 'var(--surface)',
            color: selectedPortfolio === 'all' ? '#fff' : 'var(--ink-soft)',
            cursor: 'pointer',
            fontWeight: selectedPortfolio === 'all' ? 600 : 400,
          }}
          onClick={() => onChange('all')}
        >
          All Portfolios (Household Roll-up · {portfolios.length})
        </button>

        {portfolios.map((p) => {
          const isSelected = selectedPortfolio === p.portfolio_id
          return (
            <button
              key={p.portfolio_id}
              className="chip"
              style={{
                fontSize: 12,
                padding: '3px 12px',
                borderRadius: 100,
                border: '1px solid var(--rule)',
                background: isSelected ? 'var(--accent)' : 'var(--surface)',
                color: isSelected ? '#fff' : 'var(--ink-soft)',
                cursor: 'pointer',
                fontWeight: isSelected ? 600 : 400,
              }}
              onClick={() => onChange(p.portfolio_id)}
            >
              {p.portfolio_name} ({usd(p.value_usd)})
            </button>
          )
        })}
      </div>
    </div>
  )
}
