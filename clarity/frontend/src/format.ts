/* Display helpers. Every figure the UI shows is USD unless a currency is given
   explicitly, and rounding happens here rather than in the engine. */

export function usd(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const abs = Math.abs(value)
  if (abs >= 1_000_000_000) return `${sign(value)}USD ${(abs / 1e9).toFixed(2)}bn`
  if (abs >= 1_000_000) return `${sign(value)}USD ${(abs / 1e6).toFixed(abs >= 10e6 ? 1 : 2)}m`
  return `${sign(value)}USD ${abs.toLocaleString('en-GB', {
    maximumFractionDigits: digits,
  })}`
}

export function usdExact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${sign(value)}USD ${Math.abs(value).toLocaleString('en-GB', {
    maximumFractionDigits: 0,
  })}`
}

export function money(value: number | null | undefined, currency: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${sign(value)}${currency} ${Math.abs(value).toLocaleString('en-GB', {
    maximumFractionDigits: 0,
  })}`
}

function sign(value: number): string {
  return value < 0 ? '−' : ''
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value.toFixed(digits)}%`
}

export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value >= 0 ? '+' : '−'}${Math.abs(value).toFixed(digits)}%`
}

export function signedUsd(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${value >= 0 ? '+' : '−'}${usd(Math.abs(value))}`
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export function titleCase(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

export const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  info: 'Info',
}

export const CONFIDENCE_LABEL: Record<string, string> = {
  measured: 'Measured',
  derived: 'Derived',
  reported: 'Reported',
}

export const CONFIDENCE_HINT: Record<string, string> = {
  measured: 'Arithmetic on source rows. Nothing assumed.',
  derived: 'Arithmetic plus a stated modelling assumption.',
  reported: 'Rests on an RM note or a client statement the data does not confirm.',
}
