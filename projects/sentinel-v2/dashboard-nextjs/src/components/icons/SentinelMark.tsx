import * as React from 'react'

interface SentinelMarkProps extends React.SVGProps<SVGSVGElement> {
  size?: number
  /**
   * When true, strokes render with the indigo→violet→fuchsia brand gradient.
   * When false, strokes fall back to `currentColor` (monochrome contexts,
   * favicon OS chrome, print, email signatures).
   */
  gradient?: boolean
}

// Unique gradient id per component instance so multiple marks on the same
// page don't collide (Next.js hydration + React 18 useId keeps SSR-safe).
function useGradientId() {
  const id = React.useId()
  return `sentinel-mark-grad-${id.replace(/:/g, '')}`
}

/**
 * SentinelMark
 *
 * Concept: "stacked rings + pulse" — three concentric arcs at rotational
 * offsets with a filled center dot. The broken rings evoke a radar sweep
 * and the continuous Research → Match → Build → Approve → Deploy loop;
 * the center dot is the sentinel itself, observing.
 *
 * Direction: gradient-stroke-only. The brand gradient lives on the line,
 * not on a container tile. Transparent background. Reads as a precision
 * instrument rather than a SaaS favicon square.
 */
export function SentinelMark({
  size = 24,
  className,
  gradient = true,
  ...rest
}: SentinelMarkProps) {
  const gradId = useGradientId()
  const stroke = gradient ? `url(#${gradId})` : 'currentColor'
  const fill = gradient ? `url(#${gradId})` : 'currentColor'

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke={stroke}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {gradient && (
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#6366f1" />
            <stop offset="50%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#d946ef" />
          </linearGradient>
        </defs>
      )}
      {/* Outer arc — 220° sweep, gap at lower-left */}
      <path d="M 18.75 3.96 A 10.5 10.5 0 1 1 1.66 13.82" />
      {/* Middle arc — 220° sweep, gap at lower-right */}
      <path d="M 4.12 10.61 A 8 8 0 1 1 17.14 18.13" />
      {/* Inner arc — 220° sweep, gap at right */}
      <path d="M 13.71 16.70 A 5 5 0 1 1 13.71 7.30" />
      {/* Center pulse */}
      <circle cx="12" cy="12" r="2" fill={fill} stroke="none" />
    </svg>
  )
}

export default SentinelMark
