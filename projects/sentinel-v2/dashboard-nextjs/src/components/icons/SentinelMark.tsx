import * as React from 'react'

interface SentinelMarkProps extends React.SVGProps<SVGSVGElement> {
  size?: number
}

/**
 * SentinelMark
 *
 * Concept: "stacked rings + pulse" — three concentric arcs at 120° rotational
 * offsets with a filled center dot. The broken rings evoke a radar sweep and
 * the continuous Research → Match → Build → Approve → Deploy loop; the center
 * dot is the sentinel itself, observing.
 *
 * Inherits `currentColor` for strokes and fill so it adapts to any context
 * (white inside the gradient tile, gradient on dark backgrounds, etc.).
 */
export function SentinelMark({
  size = 24,
  className,
  ...rest
}: SentinelMarkProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {/* Outer arc — 220° sweep, gap at 240° (lower-left) */}
      <path d="M 18.75 3.96 A 10.5 10.5 0 1 1 1.66 13.82" />
      {/* Middle arc — 220° sweep, gap at 120° (lower-right) */}
      <path d="M 4.12 10.61 A 8 8 0 1 1 17.14 18.13" />
      {/* Inner arc — 220° sweep, gap at 0° (right) */}
      <path d="M 13.71 16.70 A 5 5 0 1 1 13.71 7.30" />
      {/* Center pulse */}
      <circle cx="12" cy="12" r="1.9" fill="currentColor" stroke="none" />
    </svg>
  )
}

export default SentinelMark
