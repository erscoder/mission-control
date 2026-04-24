import * as React from 'react'
import { cn } from '@/lib/utils'
import { SentinelMark } from './SentinelMark'

interface SentinelLogoProps {
  size?: number
  className?: string
}

/**
 * SentinelLogo
 *
 * Wraps SentinelMark in the Linear-style gradient tile used across the
 * dashboard chrome (indigo → violet → fuchsia, rounded-lg, indigo glow).
 * The mark renders in white and is sized at ~44% of the tile so it sits
 * comfortably inside the tile without crowding the corners.
 */
export function SentinelLogo({ size = 36, className }: SentinelLogoProps) {
  const markSize = Math.round(size * 0.5)
  return (
    <div
      className={cn(
        'relative flex items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 shadow-glow-indigo',
        className,
      )}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <SentinelMark size={markSize} className="text-white" />
    </div>
  )
}

export default SentinelLogo
