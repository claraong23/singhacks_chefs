/** The Clarity brand mark: two quarter-discs, rotated against each other, with
 *  the lighter one letting the darker read through where they overlap.
 *
 *  Redrawn from the supplied SVG as two paths rather than shipping its
 *  generated clip-path scaffolding, so it stays sharp at any size, adds no
 *  network request, and carries no white background of its own. */
export function ClarityMark({ size = 22 }: { size?: number }) {
  const quarter = 'M0 838C0 617 89 402 245 246 401 90 617 0 838 0v801c0 21-16 37-37 37Z'
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 1369 1355"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path d={quarter} fill="#556cda" />
      <g transform="translate(531 517) rotate(180 419 419)">
        <path d={quarter} fill="#6e9cd0" fillOpacity="0.82" />
      </g>
    </svg>
  )
}
