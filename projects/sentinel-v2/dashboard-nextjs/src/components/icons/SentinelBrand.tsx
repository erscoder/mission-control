import * as React from 'react'
import { cn } from '@/lib/utils'
import { SentinelMark } from './SentinelMark'
import { SentinelWordmark } from './SentinelWordmark'

type BrandSize = 'sm' | 'md' | 'lg'
type BrandVariant = 'default' | 'mono'

interface SentinelBrandProps {
  size?: BrandSize
  variant?: BrandVariant
  className?: string
  /**
   * Show the "Agent Command Center" eyebrow tagline beneath the wordmark.
   * Defaults to true at md/lg, false at sm.
   */
  showTagline?: boolean
}

/**
 * Size map: mark dimension ~1.15× cap-height of the wordmark for optical
 * balance, tight horizontal gap (mark reads as a sibling of the glyph,
 * not a separate block).
 */
const SIZES: Record<BrandSize, {
  markSize: number
  wordmarkHeight: number
  gap: number
  tagline: string
}> = {
  sm: { markSize: 20, wordmarkHeight: 16, gap: 8,  tagline: 'text-[9px]' },
  md: { markSize: 26, wordmarkHeight: 20, gap: 10, tagline: 'text-[10px]' },
  lg: { markSize: 36, wordmarkHeight: 28, gap: 12, tagline: 'text-[11px]' },
}

/**
 * SentinelBrand — the full lockup.
 *
 * Direction: no tile. The mark (gradient-stroked arcs) sits flush-left of
 * the wordmark at optically-matched cap-height. The brand gradient lives
 * on the mark's strokes; the wordmark stays in text-foreground for
 * typographic clarity. In `mono` the gradient collapses to currentColor.
 *
 * This is a Linear/Vercel/Warp-style lockup: quiet, precise, monospace-
 * adjacent. No chunky gradient square, no drop-shadow glow.
 */
export function SentinelBrand({
  size = 'md',
  variant = 'default',
  className,
  showTagline,
}: SentinelBrandProps) {
  const dims = SIZES[size]
  const renderTagline = showTagline ?? size !== 'sm'
  const isMono = variant === 'mono'

  return (
    <div
      className={cn('inline-flex items-center', className)}
      style={{ gap: dims.gap }}
      aria-label="Sentinel — Agent Command Center"
    >
      <SentinelMark
        size={dims.markSize}
        gradient={!isMono}
        className={cn('shrink-0', isMono && 'text-foreground')}
      />

      <div className="flex flex-col justify-center leading-none">
        <SentinelWordmark
          height={dims.wordmarkHeight}
          className="text-foreground"
        />
        {renderTagline && (
          <span
            className={cn(
              'mt-1 font-medium uppercase tracking-[0.28em] text-muted-foreground/80',
              dims.tagline,
            )}
          >
            Agent Command Center
          </span>
        )}
      </div>
    </div>
  )
}

export default SentinelBrand
