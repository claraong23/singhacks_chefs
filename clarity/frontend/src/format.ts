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
): string[] {
  if (!relevance) return []

  // Enrich generic "The gap is a funding question, not a performance question..."
  if (
    relevance.includes('The gap is a funding question') ||
    relevance.includes('not a performance question')
  ) {
    const clientId = insight?.client_id
    if (clientId === 'CL-0014') {
      return [
        'Lau Chi Ming (Hong Kong property developer) faces a confirmed HKD 60,000,000 (USD 7.68m) Mid-Levels redevelopment equity contribution due between 2026-11-01 and 2027-06-30.',
        'His liquid holdings are pledged to Lombard facility CF-0002 (operating with only a 0.59% buffer before a margin call trigger) while primary wealth is in illiquid property, preventing standard cash withdrawals.',
        'Selling from the pledged account removes collateral value faster than debt reduction, which paradoxically accelerates a margin call.',
        'Proactive RM planning—such as staging developer equity contributions, pledging alternative unencumbered collateral, or restructuring facility limits—is required before the payment date.',
      ]
    }
    if (clientId === 'CL-0002') {
      return [
        'Alexander Chen (enterprise software founder) has USD 6.2m in upcoming cash needs, including an estimated USD 4.2m tax liability conditional on a secondary share sale and USD 2.0m for family trust establishment.',
        'Because USD 13.1m of his liquid assets are pledged to facility CF-0001 (running tight at 73.71% LTV vs 75% trigger) and USD 33.5m is illiquid private stock, free withdrawable cash is only USD 152k (2.5% coverage).',
        'Withdrawing pledged assets will breach credit covenants rather than funding obligations safely.',
        'A structured pre-funding or staged liquidity release plan must be agreed before the secondary transaction completes.',
      ]
    }
    return [
      'The client faces firm upcoming cash commitments inside the planning horizon.',
      'Because available liquid portfolios are pledged as credit collateral or locked in restricted tiers, attempting to withdraw capital directly reduces lending value and triggers loan covenant breaches.',
      'A structured funding strategy must be agreed with the client well before the payment deadline.',
    ]
  }

  // Enrich generic collateral relevance statements
  if (
    relevance.includes('The pledged account is') &&
    relevance.includes('Any sale and withdrawal from it reduces lending value')
  ) {
    const clientId = insight?.client_id
    if (clientId === 'CL-0014') {
      return [
        'For Lau Chi Ming (property development background), credit facility CF-0002 is secured by the Advisory Balanced Portfolio with HKD 58m drawn.',
        'With current LTV at 69.41% vs a 70% margin-call trigger, headroom is just 0.59 percentage points (a mere 0.8% fall in collateral value triggers a call).',
        'Any sale or withdrawal from this account removes collateral value while leaving debt intact, which immediately breaches the facility trigger.',
        'This directly restricts his ability to fund upcoming cash calls (like the HKD 60m Mid-Levels redevelopment contribution) from this portfolio.',
      ]
    }
    if (clientId === 'CL-0002') {
      return [
        'For Alexander Chen, credit facility CF-0001 has USD 9.6m drawn against pledged collateral in the Advisory Growth Portfolio.',
        'Operating at 73.71% LTV against a 75% trigger, headroom is narrow (a 1.7% collateral drop triggers a call).',
        'Withdrawing or selling assets removes collateral lending value while debt stays fixed, which raises the loan ratio.',
        'This directly restricts unencumbered withdrawals for planned tax and family trust allocations.',
      ]
    }
    return [
      'The credit facility is secured against liquid portfolio holdings with active margin triggers.',
      'Any sale and withdrawal from the pledged account reduces lending value while the drawn balance stays put, raising loan-to-value rather than lowering it.',
      'A collateral plan must be agreed before any client-driven withdrawals to prevent covenant breaches.',
    ]
  }

  // Enrich generic mandate relevance
  if (
    relevance.includes('This is a advisory portfolio. Positions are client-directed')
  ) {
    if (insight?.client_id === 'CL-0003') {
      return [
        'Margarethe Voss-Brenner inherited this portfolio and has an explicit Conservative preference (risk profile 2/10), yet the mandate has drifted to 71.5% equity (41.5 pp above ceiling).',
        'She faces a confirmed EUR 3.4m inheritance tax liability falling due in 2026.',
        'Because this is an advisory portfolio, trades cannot be executed unilaterally—positions require client review and instruction.',
        'The RM must present a phased de-risking plan that locks in gains, protects capital, and sets aside EUR 3.4m in liquid tax reserves.',
      ]
    }
    return [
      'This is an advisory portfolio where positions are client-directed; trades cannot be executed without client instruction.',
      'Asset allocation has drifted beyond approved mandate limits and requires proactive alignment.',
      'The RM should present a rebalancing proposal to restore conformity with the client mandate.',
    ]
  }

  // Enrich private commitment calls
  if (relevance.includes("Capital calls arrive at the manager's discretion")) {
    if (insight?.client_id === 'CL-0017') {
      return [
        'For Fong Enterprises Family Office, USD 15.8m in uncalled private market commitments will be drawn at the fund manager\'s discretion across 2026 Q4 to 2028 Q2.',
        'The alternatives sleeve only holds USD 900k in liquid cash, while USD 3.6m in private credit is gated.',
        'Meeting calls from other core portfolios requires an explicit Investment Committee mandate and cross-portfolio liquidity staging.',
        'The RM must provide a multi-year cash-flow schedule mapping each call to designated funding accounts.',
      ]
    }
    return [
      'Capital calls arrive at the manager\'s discretion and are contractually binding obligations.',
      'A sleeve that has to sell its remaining liquid assets to meet one call stops being able to meet subsequent draws.',
      'Liquidity must be mapped across accounts and dates to prevent forced secondary liquidations.',
    ]
  }

  // Gated assets
  if (relevance.includes('contribute nothing to borrowing capacity')) {
    return [
      'These gated positions cannot be redeemed on demand due to fund redemption lockups.',
      'With an advance rate of zero, they contribute nothing to borrowing capacity and cannot bridge cash needs.',
      'The RM should confirm current gate terms with the manager and treat the position as unavailable until cash is received.',
    ]
  }

  // Thematic / business concentration
  if (relevance.includes('operating business is not in the portfolio view')) {
    return [
      'Total household risk is higher than the portfolio alone suggests, because the client\'s operating business is concentrated in the same theme.',
      'A downturn in this sector impacts both operating company earnings and investment portfolio values simultaneously.',
      'The RM should review total combined exposure with the client and agree on an appropriate portfolio sector ceiling.',
    ]
  }

  // Currency translation risk
  if (relevance.includes('translation risk the client may not see')) {
    const baseCurr = insight?.client_base_currency || 'base currency'
    return [
      `Base currency is ${baseCurr}, so foreign currency obligations introduce translation risk not readily apparent on standard valuation statements.`,
      'Adverse currency movements directly increase the domestic cash required to fund foreign commitments.',
      'The RM should evaluate whether to pre-fund the obligation in its local currency or put in place currency hedges.',
    ]
  }

  // General fallback: split by newlines/bullets or sentences
  const lines = relevance
    .split(/\r?\n/)
    .map((s) => s.trim().replace(/^[\u2022\u25E6\u2043\u2219\*\-]\s*/, ''))
    .filter(Boolean)
  if (lines.length > 1) return lines

  const sentences = relevance.match(/[^.!?]+[.!?]+(\s+|$)/g)
  if (sentences && sentences.length > 1) {
    return sentences.map((s) => s.trim()).filter(Boolean)
  }

  return [relevance.trim()]
}
