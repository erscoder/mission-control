'use client'

import { cn } from '@/lib/utils'
import { getAgent } from '@/lib/agents'

interface AgentAvatarProps {
  agentId: string
  size?: 'xs' | 'sm' | 'md' | 'lg'
  active?: boolean
  className?: string
}

const SIZE: Record<NonNullable<AgentAvatarProps['size']>, string> = {
  xs: 'h-6 w-6',
  sm: 'h-9 w-9',
  md: 'h-11 w-11',
  lg: 'h-14 w-14',
}

const PX: Record<NonNullable<AgentAvatarProps['size']>, number> = {
  xs: 24,
  sm: 36,
  md: 44,
  lg: 56,
}

// Map Tailwind `from-indigo-500` style to DiceBear-friendly hex palettes
// (background colors DiceBear will pick from — single values chosen to match gradient start)
const GRADIENT_TO_HEX: Record<string, string> = {
  'from-sky-500': '0ea5e9',
  'from-amber-400': 'fbbf24',
  'from-indigo-500': '6366f1',
  'from-violet-500': '8b5cf6',
  'from-fuchsia-500': 'd946ef',
  'from-emerald-500': '10b981',
  'from-teal-500': '14b8a6',
  'from-rose-600': 'e11d48',
  'from-zinc-600': '52525b',
}

function hexForAgent(gradient: string): string {
  const first = gradient.split(' ').find((c) => c.startsWith('from-'))
  return (first && GRADIENT_TO_HEX[first]) || '6366f1'
}

function avatarUrl(agentId: string, bgHex: string, size: number) {
  const seed = encodeURIComponent(agentId || 'sentinel')
  // DiceBear bottts-neutral: muted robot aesthetic, no API key, CDN cached
  const params = new URLSearchParams({
    seed,
    size: String(size * 2), // render at 2x for retina
    backgroundColor: bgHex,
    backgroundType: 'solid',
    radius: '50',
  })
  return `https://api.dicebear.com/9.x/bottts-neutral/svg?${params.toString()}`
}

export default function AgentAvatar({
  agentId,
  size = 'md',
  active = false,
  className,
}: AgentAvatarProps) {
  const agent = getAgent(agentId)
  const bg = hexForAgent(agent.gradient)
  const px = PX[size]
  const url = avatarUrl(agent.id, bg, px)

  return (
    <div
      className={cn(
        'relative flex flex-shrink-0 items-center justify-center rounded-full',
        SIZE[size],
        active && 'ring-2 ring-primary/60 ring-offset-2 ring-offset-background',
        className,
      )}
      title={agent.name}
    >
      {/* Gradient halo under avatar for brand continuity */}
      <span
        aria-hidden
        className={cn(
          'absolute inset-0 rounded-full bg-gradient-to-br opacity-90',
          agent.gradient,
        )}
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt={agent.name}
        width={px}
        height={px}
        loading="lazy"
        className={cn(
          'relative rounded-full ring-1 ring-black/20',
          SIZE[size],
        )}
      />
      {active && (
        <span className="absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5 items-center justify-center">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-80" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-background" />
        </span>
      )}
    </div>
  )
}
