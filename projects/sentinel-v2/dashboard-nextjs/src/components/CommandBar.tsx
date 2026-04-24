'use client'

import {
  Activity,
  Crosshair,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { FlowBreakdown, FlowState } from '@/types/sentinel'
import { formatRelative } from '@/lib/utils'
import SentinelBrand from '@/components/icons/SentinelBrand'

interface CommandBarProps {
  status: 'connecting' | 'connected' | 'disconnected'
  flowState: FlowState | null
  breakdown: FlowBreakdown | null
}

export default function CommandBar({ status, flowState, breakdown }: CommandBarProps) {
  const cycle = breakdown?.cycle ?? flowState?.cycle ?? 0
  const phase = breakdown?.phase ?? flowState?.phase ?? 'idle'
  const progress = Math.round((breakdown?.progress ?? 0) * 100)
  const updated = breakdown?.updated_at || flowState?.updated_at

  return (
    <header className="sticky top-0 z-40 border-b border-border/80 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex w-full max-w-[1800px] items-center gap-6 px-6 py-3">
        {/* Logo */}
        <SentinelBrand size="md" />


        <div className="hidden h-6 w-px bg-border md:block" />

        {/* Cycle pill */}
        <div className="flex items-center gap-1.5 rounded-md border border-border bg-surface-muted/60 px-2.5 py-1 font-mono text-[11px] text-muted-foreground">
          <Crosshair className="h-3 w-3 text-primary" />
          <span className="text-foreground">Cycle</span>
          <span className="font-semibold text-foreground tabular-nums">#{cycle}</span>
        </div>

        {/* Active phase */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 text-[11px] font-medium text-primary">
            <Activity className="h-3 w-3" />
            <span className="uppercase tracking-wider">{phase}</span>
          </div>
          {progress > 0 && phase !== 'idle' && (
            <span className="font-mono text-[11px] text-muted-foreground tabular-nums">
              {progress}%
            </span>
          )}
        </div>

        {/* Spacer — metrics now live inline on each pipeline row card */}
        <div className="hidden flex-1 lg:block" />

        {/* Updated-at */}
        {updated && (
          <span className="hidden text-[11px] text-muted-foreground md:inline">
            {formatRelative(updated)}
          </span>
        )}

        {/* Connection */}
        <div
          className={cn(
            'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[11px] font-medium',
            status === 'connected' && 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
            status === 'disconnected' && 'border-red-500/30 bg-red-500/10 text-red-300',
            status === 'connecting' && 'border-amber-500/30 bg-amber-500/10 text-amber-300',
          )}
        >
          {status === 'connected' ? (
            <Wifi className="h-3 w-3" />
          ) : (
            <WifiOff className={cn('h-3 w-3', status === 'connecting' && 'animate-pulse')} />
          )}
          <span className="uppercase tracking-wider">
            {status === 'connected' ? 'Live' : status === 'connecting' ? 'Syncing' : 'Offline'}
          </span>
        </div>
      </div>
    </header>
  )
}

