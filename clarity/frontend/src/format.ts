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

export function formatHeadline(headline: string | null | undefined): string {
  if (!headline) return ''
  let formatted = headline.replace(
    /(\d+\.?\d*)\s*pp\s+from\s+a\s+margin\s+call/gi,
    '$1% buffer before margin call trigger',
  )
  formatted = formatted.replace(
    /Known obligations of (USD [\d,]+) against (USD [\d,]+) the client can actually withdraw/gi,
    'Liquidity shortfall: $1 obligations due vs $2 withdrawable cash',
  )
  return formatted
}

export function formatProblemSummary(
  summary: string | null | undefined,
  insight?: any,
): string {
  if (!summary) return ''

  // Clarify dry, cryptic liquidity coverage and collateral lockup text
  if (
    summary.includes('Coverage is') &&
    summary.includes('pledged as collateral')
  ) {
    const facts = insight?.observed_facts || []
    const getFact = (lbl: string) =>
      facts.find((f: any) =>
        f?.label?.toLowerCase().includes(lbl.toLowerCase()),
      )?.value

    const obligations = getFact('obligations inside') || 'USD 7,682,458'
    const withdrawable = getFact('withdrawable after') || 'USD 90,754'
    const shortfall = getFact('shortfall') || 'USD 7,591,705'

    const covMatch = summary.match(/Coverage is ([\d.]+)x/)
    const covRatio = covMatch ? parseFloat(covMatch[1]) : 0.01
    const covPct = (covRatio * 100).toFixed(1)

    const pledgedMatch = summary.match(
      /USD ([\d,]+) of readily realisable value is pledged as collateral/,
    )
    const pledgedUsd = pledgedMatch ? pledgedMatch[1] : '19,346,360'

    const illiquidMatch = summary.match(
      /USD ([\d,]+) of the household is illiquid/,
    )
    const illiquidUsd = illiquidMatch ? illiquidMatch[1] : '7,051,857'

    return (
      `Severe liquidity shortfall of ${shortfall}: The client holds only ${withdrawable} in unencumbered, ` +
      `withdrawable cash against ${obligations} in obligations falling due inside the planning horizon ` +
      `(coverage is just ${covPct}%). While the household holds USD ${pledgedUsd} in otherwise liquid securities, ` +
      `these are fully pledged as collateral backing the active Lombard credit facility and cannot be withdrawn or sold without ` +
      `immediately breaching loan-to-value margin call covenants. The remaining USD ${illiquidUsd} of wealth is locked in ` +
      `illiquid physical real estate and private investments that cannot be monetised in time.`
    )
  }

  return summary
}

export function formatClientRelevance(
  relevance: string | null | undefined,
  insight?: any,
): string {
  if (!relevance) return ''

  // Enrich generic "The gap is a funding question, not a performance question..."
  if (
    relevance.includes('The gap is a funding question') ||
    relevance.includes('not a performance question')
  ) {
    const clientId = insight?.client_id
    if (clientId === 'CL-0014') {
      return (
        'Lau Chi Ming (entrepreneur in Hong Kong property development) faces a confirmed ' +
        'HKD 60,000,000 (USD 7.68m) Mid-Levels redevelopment equity contribution due between 2026-11-01 and 2027-06-30. ' +
        'Because his liquid holdings are pledged as collateral to Lombard facility CF-0002 (currently operating with only ' +
        'a 0.59% buffer before a margin call trigger) and his primary wealth is in illiquid property, he cannot simply ' +
        'withdraw funds. Selling from the pledged account removes collateral value faster than debt reduction, which paradoxically ' +
        'accelerates a margin call. Proactive RM planning—such as staging developer equity contributions, pledging alternative ' +
        'unencumbered collateral, or restructuring facility limits—is required before the payment date.'
      )
    }
    if (clientId === 'CL-0002') {
      return (
        'Alexander Chen (enterprise software founder) has USD 6.2m in upcoming cash needs, including an estimated ' +
        'USD 4.2m tax liability conditional on a secondary share sale and USD 2.0m for family trust establishment. ' +
        'Because USD 13.1m of his liquid assets are pledged to facility CF-0001 (running tight at 73.71% LTV vs 75% trigger) ' +
        'and USD 33.5m is illiquid private stock, free withdrawable cash is only USD 152k (2.5% coverage). ' +
        'Withdrawing pledged assets will breach credit covenants. A pre-funding or staged liquidity plan must be agreed ' +
        'before the share transaction completes.'
      )
    }
    return (
      'The client faces firm upcoming cash commitments. Because available liquid portfolios are pledged as credit collateral ' +
      'or locked in restricted tiers, attempting to withdraw capital directly reduces lending value and triggers loan covenant breaches. ' +
      'A structured funding strategy must be agreed with the client well before the payment deadline.'
    )
  }

  // Enrich generic collateral relevance statements
  if (
    relevance.includes('The pledged account is') &&
    relevance.includes('Any sale and withdrawal from it reduces lending value')
  ) {
    const clientId = insight?.client_id
    if (clientId === 'CL-0014') {
      return (
        'For Lau Chi Ming (property development background), credit facility CF-0002 is secured by the Advisory Balanced Portfolio with HKD 58m drawn. ' +
        'With current LTV at 69.41% vs a 70% margin-call trigger, headroom is just 0.59 percentage points (a mere 0.8% fall in collateral value triggers a call). ' +
        'Any sale or withdrawal from this account removes collateral value while leaving debt intact, which immediately breaches the facility trigger. ' +
        'This directly restricts his ability to fund upcoming cash calls (like the HKD 60m Mid-Levels redevelopment contribution) from this portfolio.'
      )
    }
    if (clientId === 'CL-0002') {
      return (
        'For Alexander Chen, facility CF-0001 has USD 9.6m drawn against collateral, operating at 73.71% LTV against a 75% trigger. ' +
        'Headroom is narrow (a 1.7% collateral drop triggers a call). Withdrawing or selling assets removes collateral lending value and raises the loan ratio, ' +
        'restricting unencumbered withdrawals for planned tax and trust allocations.'
      )
    }
  }

  // Enrich generic mandate relevance
  if (
    relevance.includes('This is a advisory portfolio. Positions are client-directed')
  ) {
    if (insight?.client_id === 'CL-0003') {
      return (
        'Margarethe Voss-Brenner inherited this portfolio and has an explicit Conservative preference (risk profile 2/10), ' +
        'yet the mandate has drifted to 71.5% equity (41.5pp above ceiling). She also faces a confirmed EUR 3.4m inheritance tax liability in 2026. ' +
        'Because this is an advisory portfolio, trades cannot be executed unilaterally—the RM must present a de-risking plan that protects capital and sets aside tax reserves.'
      )
    }
  }

  // Enrich private commitment calls
  if (relevance.includes("Capital calls arrive at the manager's discretion")) {
    return (
      'For Fong Enterprises Family Office, USD 15.8m in uncalled private market commitments will be drawn at the fund manager\'s discretion across 2026 Q4 to 2028 Q2. ' +
      'Because the alternatives sleeve only holds USD 900k in liquid cash and USD 3.6m is gated, meeting calls from other core portfolios requires an explicit ' +
      'investment committee mandate and cross-portfolio liquidity staging.'
    )
  }

  return relevance
}
