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

// Vibrant palette — each agent_id deterministically maps to a distinct hue.
// Colors chosen so bottts-neutral (grayscale robots) sits on a saturated backdrop.
const COLOR_PALETTE = [
  'f97316', // orange-500
  'f59e0b', // amber-500
  'eab308', // yellow-500
  '84cc16', // lime-500
  '22c55e', // green-500
  '10b981', // emerald-500
  '14b8a6', // teal-500
  '06b6d4', // cyan-500
  '0ea5e9', // sky-500
  '3b82f6', // blue-500
  '6366f1', // indigo-500
  '8b5cf6', // violet-500
  'a855f7', // purple-500
  'd946ef', // fuchsia-500
  'ec4899', // pink-500
  'f43f5e', // rose-500
  'ef4444', // red-500
]

// Explicit color overrides for known crew roles so phase-color-coding remains
// consistent with the pipeline stages. Unknown agents fall through to the hash.
const KNOWN_ROLE_HEX: Record<string, string> = {
  'web-scout': '0ea5e9',           // sky
  'market-analyst': '06b6d4',      // cyan
  'profile-researcher': 'f59e0b',  // amber
  matcher: 'ec4899',               // pink
  'strategic-manager': '6366f1',   // indigo
  'frontend-lead': '8b5cf6',       // violet
  'backend-lead': 'd946ef',        // fuchsia
  'code-reviewer': 'a855f7',       // purple
  'security-auditor': '10b981',    // emerald
  'qa-lead': '3b82f6',             // blue
  'deployment-engineer': '22c55e', // green
  'qa-verifier': '14b8a6',         // teal
  orchestrator: 'f97316',          // orange
  sentinel: 'f97316',
}

function hashString(s: string): number {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = (h * 33) ^ s.charCodeAt(i)
  }
  return Math.abs(h)
}

function hexForAgent(agentId: string): string {
  const key = (agentId || 'sentinel').toLowerCase().replace(/\s+/g, '-')
  if (KNOWN_ROLE_HEX[key]) return KNOWN_ROLE_HEX[key]
  return COLOR_PALETTE[hashString(key) % COLOR_PALETTE.length]
}

function avatarUrl(agentId: string, bgHex: string, size: number) {
  const seed = encodeURIComponent(agentId || 'sentinel')
  const params = new URLSearchParams({
    seed,
    size: String(size * 2), // 2x for retina
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
  const bg = hexForAgent(agent.id)
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
        style={{ backgroundColor: `#${bg}` }}
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
