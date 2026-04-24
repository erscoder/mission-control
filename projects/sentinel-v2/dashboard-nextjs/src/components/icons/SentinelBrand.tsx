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
 * Size map: wordmark height in px, mark tile dimension, gap between them.
 * Calibrated so the mark's visual weight roughly matches the cap-height
 * of the wordmark (optical alignment — mark is ~1.15x cap-height).
 */
const SIZES: Record<BrandSize, {
  markSize: number
  markInner: number
  wordmarkHeight: number
  gap: number
  tagline: string
}> = {
  sm: { markSize: 22, markInner: 12, wordmarkHeight: 16, gap: 8,  tagline: 'text-[9px]' },
  md: { markSize: 32, markInner: 16, wordmarkHeight: 20, gap: 10, tagline: 'text-[10px]' },
  lg: { markSize: 44, markInner: 22, wordmarkHeight: 28, gap: 12, tagline: 'text-[11px]' },
}

/**
 * SentinelBrand — the full lockup (the actual logo).
 *
 * Lockup approach: horizontal pairing with the gradient mark tile on the
 * left, baseline-aligned to the wordmark cap-height on the right. The mark
 * retains its indigo→violet→fuchsia gradient tile in the default variant
 * (anchoring the brand color), while the wordmark sits in text-foreground
 * for typographic clarity. A vertical stack on the right holds the wordmark
 * with an optional "Agent Command Center" eyebrow beneath it.
 *
 * In `mono` variant, the mark renders in current-color (no gradient tile),
 * useful for single-color contexts like email signatures or print.
 *
 * A subtle drop-shadow on the wordmark gives it ambient glow on dark
 * backgrounds without looking heavy-handed.
 */
export function SentinelBrand({
  size = 'md',
  variant = 'default',
  className,
  showTagline,
}: SentinelBrandProps) {
  const dims = SIZES[size]
  const renderTagline = showTagline ?? size !== 'sm'

  return (
    <div
      className={cn('inline-flex items-center', className)}
      style={{ gap: dims.gap }}
      aria-label="Sentinel — Agent Command Center"
    >
      {variant === 'default' ? (
        <div
          className="relative flex shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 shadow-glow-indigo"
          style={{ width: dims.markSize, height: dims.markSize }}
          aria-hidden="true"
        >
          <SentinelMark size={dims.markInner} className="text-white" />
        </div>
      ) : (
        <SentinelMark
          size={dims.markSize}
          className="shrink-0 text-foreground"
          aria-hidden="true"
        />
      )}

      <div className="flex flex-col justify-center leading-none">
        <SentinelWordmark
          height={dims.wordmarkHeight}
          className="text-foreground [filter:drop-shadow(0_0_8px_rgba(139,92,246,0.25))]"
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
