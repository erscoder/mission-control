import * as React from 'react'
import { cn } from '@/lib/utils'
import { SentinelMark } from './SentinelMark'

interface SentinelLogoProps {
  size?: number
  className?: string
  /**
   * Force monochrome (currentColor) strokes instead of the brand gradient.
   */
  mono?: boolean
}

/**
 * SentinelLogo
 *
 * Standalone mark on transparent background — no tile, no rounded square,
 * no drop-shadow "glow". The brand gradient lives on the arc strokes
 * themselves. This is what goes in nav chrome, app icons, and anywhere
 * the mark needs to read as a precision instrument rather than a SaaS
 * favicon tile.
 */
export function SentinelLogo({ size = 36, className, mono = false }: SentinelLogoProps) {
  return (
    <SentinelMark
      size={size}
      gradient={!mono}
      className={cn('shrink-0', mono && 'text-foreground', className)}
    />
  )
}

export default SentinelLogo
