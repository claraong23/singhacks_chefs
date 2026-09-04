/* Inline SVG charts. No charting library: the shapes we need are few, and
   drawing them directly keeps the bundle small and the axes honest. */

import type { BandBreach, LtvPoint } from '../types'
import { pct, usd } from '../format'

interface ValuePoint {
  label: string
  total_usd: number
}

export function ValueLine({ points }: { points: ValuePoint[] }) {
  const width = 620
  const height = 150
  const padX = 14
  const padTop = 18
  const padBottom = 26
  if (points.length < 2) return null

  const values = points.map((p) => p.total_usd)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  // Give the line room to breathe rather than pinning it to the frame.
  const lo = min - span * 0.25
  const hi = max + span * 0.25

  const x = (index: number) =>
    padX + (index * (width - padX * 2)) / (points.length - 1)
  const y = (value: number) =>
    padTop + (1 - (value - lo) / (hi - lo)) * (height - padTop - padBottom)

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.total_usd)}`).join(' ')
  const area = `${line} L${x(points.length - 1)},${height - padBottom} L${x(0)},${height - padBottom} Z`
  const rising = points[points.length - 1].total_usd >= points[0].total_usd
  const stroke = rising ? 'var(--positive)' : 'var(--negative)'

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
      aria-label="Household value at each snapshot">
      <defs>
        <linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.14" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#valueFill)" />
      <path d={line} fill="none" stroke={stroke} strokeWidth="1.75" strokeLinejoin="round" />
      {points.map((p, i) => (
        <g key={p.label}>
          <circle cx={x(i)} cy={y(p.total_usd)} r="3" fill="var(--surface)" stroke={stroke} strokeWidth="1.5" />
          <text x={x(i)} y={height - 12} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}
            fontSize="10" fill="var(--faint)">
            {p.label}
          </text>
          <text x={x(i)} y={y(p.total_usd) - 9} textAnchor={i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}
            fontSize="10.5" fill="var(--muted)">
            {usd(p.total_usd)}
          </text>
        </g>
      ))}
    </svg>
  )
}

export function LtvChart({ series, trigger }: { series: LtvPoint[]; trigger: number }) {
  const width = 620
  const height = 168
  const padX = 16
  const padTop = 16
  const padBottom = 26
  const values = series.map((p) => p.ltv_pct ?? 0)
  const hi = Math.max(trigger + 8, ...values.map((v) => v + 6))
  const lo = Math.max(0, Math.min(...values.map((v) => v - 8), trigger - 20))

  const x = (i: number) => padX + (i * (width - padX * 2)) / (series.length - 1)
  const y = (v: number) => padTop + (1 - (v - lo) / (hi - lo)) * (height - padTop - padBottom)

  const line = series
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i)},${y(p.ltv_pct ?? 0)}`)
    .join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img"
      aria-label="Loan to value across the five snapshots against the margin-call trigger">
      <rect x={padX} y={padTop} width={width - padX * 2} height={y(trigger) - padTop}
        fill="var(--critical)" opacity="0.06" />
      <line x1={padX} y1={y(trigger)} x2={width - padX} y2={y(trigger)}
        stroke="var(--critical)" strokeWidth="1" strokeDasharray="4 3" />
      {/* Anchored left so it never collides with the final point's label,
          which is the one most likely to sit near the trigger. */}
      <text x={padX} y={y(trigger) - 5} textAnchor="start" fontSize="10" fill="var(--critical)">
        Margin call {trigger.toFixed(0)}%
      </text>
      <path d={line} fill="none" stroke="var(--accent)" strokeWidth="1.75" strokeLinejoin="round" />
      {series.map((p, i) => (
        <g key={p.snapshot}>
          <circle cx={x(i)} cy={y(p.ltv_pct ?? 0)} r={p.breached ? 4.5 : 3}
            fill={p.breached ? 'var(--critical)' : 'var(--surface)'}
            stroke={p.breached ? 'var(--critical)' : 'var(--accent)'} strokeWidth="1.5" />
          <text x={x(i)} y={y(p.ltv_pct ?? 0) - 9}
            textAnchor={i === 0 ? 'start' : i === series.length - 1 ? 'end' : 'middle'}
            fontSize="10.5" fill={p.breached ? 'var(--critical)' : 'var(--muted)'}
            fontWeight={p.breached ? 700 : 400}>
            {pct(p.ltv_pct)}
          </text>
          <text x={x(i)} y={height - 11}
            textAnchor={i === 0 ? 'start' : i === series.length - 1 ? 'end' : 'middle'}
            fontSize="10" fill="var(--faint)">
            {p.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

interface BandRow {
  assetClass: string
  actual: number
  min: number
  target: number
  max: number
  breach?: BandBreach
}

export function BandChart({ rows }: { rows: BandRow[] }) {
  const scaleMax = Math.max(100, ...rows.map((r) => r.actual + 5))
  return (
    <div>
      {rows.map((row) => {
        const toPct = (v: number) => (v / scaleMax) * 100
        const outside = Boolean(row.breach)
        return (
          <div key={row.assetClass} style={{ marginBottom: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 5 }}>
              <span>{row.assetClass}</span>
              <span className={outside ? 'neg' : 'muted'} style={{ fontWeight: outside ? 600 : 400 }}>
                {pct(row.actual)}
                <span className="muted" style={{ fontWeight: 400 }}>
                  {' '}· band {row.min.toFixed(0)}–{row.max.toFixed(0)}%
                </span>
              </span>
            </div>
            <div style={{ position: 'relative', height: 12, background: 'var(--surface-sunk)', borderRadius: 2 }}>
              <div style={{
                position: 'absolute', left: `${toPct(row.min)}%`,
                width: `${toPct(row.max - row.min)}%`, top: 0, bottom: 0,
                background: 'var(--accent)', opacity: 0.14,
              }} />
              <div style={{
                position: 'absolute', left: `${toPct(row.target)}%`, top: -2, bottom: -2,
                width: 1, background: 'var(--accent)', opacity: 0.55,
              }} />
              <div style={{
                position: 'absolute', left: 0, width: `${toPct(Math.min(row.actual, scaleMax))}%`,
                top: 3, bottom: 3, background: outside ? 'var(--critical)' : 'var(--accent)',
                borderRadius: 2,
              }} />
            </div>
          </div>
        )
      })}
      <div className="footnote">
        Shaded range is the permitted band, the vertical hairline is the strategic target,
        the solid bar is today.
      </div>
    </div>
  )
}

export function TierBar({ tiers }: { tiers: Record<string, number> }) {
  const order = ['Daily', 'Weekly', 'Monthly', 'Quarterly Gate', 'Illiquid']
  const colours: Record<string, string> = {
    Daily: 'var(--accent)',
    Weekly: '#3b7ba8',
    Monthly: '#7d9db4',
    'Quarterly Gate': 'var(--high)',
    Illiquid: 'var(--critical)',
  }
  const total = order.reduce((sum, key) => sum + (tiers[key] ?? 0), 0)
  if (!total) return null
  return (
    <div>
      <div style={{ display: 'flex', height: 22, borderRadius: 2, overflow: 'hidden' }}>
        {order.map((key) => {
          const value = tiers[key] ?? 0
          if (!value) return null
          return (
            <div key={key} title={`${key}: ${usd(value)}`}
              style={{ width: `${(value / total) * 100}%`, background: colours[key] }} />
          )
        })}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
        {order.map((key) => {
          const value = tiers[key] ?? 0
          if (!value) return null
          return (
            <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5 }}>
              <i style={{ width: 8, height: 8, background: colours[key], display: 'block', borderRadius: 2 }} />
              <span>{key}</span>
              <span className="muted">{usd(value)} · {pct((value / total) * 100, 0)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

interface BarRow {
  label: string
  value: number
  detail?: string
}

export function DivergingBars({ rows }: { rows: BarRow[] }) {
  if (!rows.length) return null
  const max = Math.max(...rows.map((r) => Math.abs(r.value))) || 1
  return (
    <div>
      {rows.map((row) => {
        const negative = row.value < 0
        const width = (Math.abs(row.value) / max) * 50
        return (
          <div key={row.label} style={{ marginBottom: 11 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 4, gap: 12 }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {row.label}
              </span>
              <span className={negative ? 'neg' : 'pos'} style={{ whiteSpace: 'nowrap' }}>
                {negative ? '−' : '+'}{usd(Math.abs(row.value))}
              </span>
            </div>
            <div style={{ position: 'relative', height: 8, background: 'var(--surface-sunk)', borderRadius: 2 }}>
              <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 1, background: 'var(--rule-strong)' }} />
              <div style={{
                position: 'absolute',
                left: negative ? `${50 - width}%` : '50%',
                width: `${width}%`, top: 0, bottom: 0,
                background: negative ? 'var(--negative)' : 'var(--positive)',
                borderRadius: 2,
              }} />
            </div>
            {row.detail && <div className="footnote" style={{ marginTop: 3 }}>{row.detail}</div>}
          </div>
        )
      })}
    </div>
  )
}

export function DonutList({
  entries,
  total,
}: {
  entries: [string, number][]
  total: number
}) {
  const palette = ['var(--accent)', '#3b7ba8', '#6f9cbb', '#9bb8cc', '#c3d3de', '#dfe7ed']
  return (
    <div>
      <div style={{ display: 'flex', height: 10, borderRadius: 2, overflow: 'hidden', marginBottom: 12 }}>
        {entries.map(([key, value], i) => (
          <div key={key} title={`${key}: ${usd(value)}`}
            style={{ width: `${(value / total) * 100}%`, background: palette[i % palette.length] }} />
        ))}
      </div>
      <table className="kv">
        <tbody>
          {entries.map(([key, value], i) => (
            <tr key={key}>
              <td>
                <i style={{
                  display: 'inline-block', width: 8, height: 8, borderRadius: 2,
                  background: palette[i % palette.length], marginRight: 8,
                }} />
                {key}
              </td>
              <td style={{ textAlign: 'right' }}>
                {usd(value)} <span className="muted">· {pct((value / total) * 100)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
