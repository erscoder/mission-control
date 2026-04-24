'use client'

import {
  Activity,
  Crosshair,
  Cpu,
  Wifi,
  WifiOff,
  Gauge,
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
  const metrics = breakdown?.metrics ?? {}
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

        {/* Metrics inline */}
        <div className="hidden flex-1 items-center gap-4 lg:flex">
          <MetricPill
            icon={Gauge}
            label="Coverage"
            value={metrics.coverage_percent != null ? `${metrics.coverage_percent}%` : '—'}
          />
          <MetricPill
            icon={Cpu}
            label="Tests"
            value={
              metrics.tests_total
                ? `${metrics.tests_passed ?? 0}/${metrics.tests_total}`
                : '—'
            }
          />
          <MetricPill
            icon={Activity}
            label="Issues"
            value={metrics.issues_count != null ? String(metrics.issues_count) : '—'}
            tone={metrics.issues_count ? 'warn' : 'neutral'}
          />
        </div>

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

function MetricPill({
  icon: Icon,
  label,
  value,
  tone = 'neutral',
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  tone?: 'neutral' | 'warn'
}) {
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <Icon
        className={cn(
          'h-3 w-3',
          tone === 'warn' ? 'text-amber-400' : 'text-muted-foreground',
        )}
      />
      <span className="uppercase tracking-wider text-muted-foreground/70">{label}</span>
      <span className="font-mono font-semibold tabular-nums text-foreground">{value}</span>
    </div>
  )
}
