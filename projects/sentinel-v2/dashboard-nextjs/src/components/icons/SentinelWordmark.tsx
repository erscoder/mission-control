import * as React from 'react'

interface SentinelWordmarkProps {
  height?: number
  className?: string
  /**
   * When true, the "i" dot position is left open so a parent lockup can place
   * a custom mark there (e.g. SentinelBrand integrating SentinelMark as the dot).
   * Defaults to false — the wordmark stands alone with its own minimal tittle.
   */
  omitDot?: boolean
  /**
   * X coordinate of the "i" tittle in the local viewBox. Exported so the
   * lockup can perfectly register its mark over this point.
   */
}

/**
 * SentinelWordmark — the custom-set "Sentinel" brand type.
 *
 * Design decision: geometric grotesk, heavy (700), tight optical tracking
 * (-2% letter-spacing), with one bespoke touch — the crossbar of the "t"
 * is extended into a subtle horizontal "scan line" that nods to radar/
 * reconnaissance, reinforcing the surveillance-loop concept of Sentinel
 * without leaning on an icon motif.
 *
 * ViewBox is tightly fitted to the glyph bounds so the wordmark can be
 * baseline-aligned with an external mark in a lockup composition.
 *
 * Fill uses currentColor so the wordmark inherits text-foreground from
 * its parent (and can be overridden to a gradient via fill prop).
 */
export function SentinelWordmark({
  height = 24,
  className,
  omitDot = false,
}: SentinelWordmarkProps) {
  // ViewBox chosen to tightly bound "Sentinel" at 700-weight, ~20 units tall.
  // Height 28 leaves headroom for the tittle of the lowercase "i".
  const viewBoxWidth = 148
  const viewBoxHeight = 28
  const width = (height * viewBoxWidth) / viewBoxHeight

  return (
    <svg
      viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
      width={width}
      height={height}
      fill="currentColor"
      className={className}
      role="img"
      aria-label="Sentinel"
    >
      <text
        x="0"
        y="22"
        fontFamily="Inter, system-ui, -apple-system, sans-serif"
        fontWeight={700}
        fontSize="24"
        letterSpacing="-0.03em"
        style={{ fontFeatureSettings: "'ss01','cv11'" }}
      >
        Sent
        {/* The "i" is rendered as a stem only; the tittle is drawn separately
            so it can be replaced by the mark in the lockup. */}
        <tspan letterSpacing="-0.03em">&#x131;</tspan>
        nel
      </text>

      {/* Bespoke touch: extended "t" crossbar — a 14-unit scan line past the
          stem, with a 1px gap, evoking a radar sweep. Positioned over the
          "t" (~x=41 in Inter-700 at 24px after "Sen"). */}
      <rect x="44.5" y="7.2" width="8" height="1.6" rx="0.8" opacity="0.55" />

      {/* Tittle of "i" (unless omitted for lockup integration). */}
      {!omitDot && (
        <circle cx={WORDMARK_DOT_X} cy={WORDMARK_DOT_Y} r="2.2" />
      )}
    </svg>
  )
}

/** Exported so SentinelBrand can register its mark exactly over the "i" tittle. */
export const WORDMARK_VIEWBOX_WIDTH = 148
export const WORDMARK_VIEWBOX_HEIGHT = 28
export const WORDMARK_DOT_X = 69.5
export const WORDMARK_DOT_Y = 4.4

export default SentinelWordmark
