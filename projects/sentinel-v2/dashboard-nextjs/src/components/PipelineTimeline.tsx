'use client'

import { useMemo } from 'react'
import {
  Check,
  Loader2,
  Sparkles,
  ArrowRight,
  CircleDot,
} from 'lucide-react'
import { PHASES, phaseIndex, getAgent } from '@/lib/agents'
import type { FlowBreakdown } from '@/types/sentinel'
import { cn } from '@/lib/utils'
import AgentAvatar from './AgentAvatar'

interface PipelineTimelineProps {
  breakdown: FlowBreakdown | null
}

export default function PipelineTimeline({ breakdown }: PipelineTimelineProps) {
  const currentPhase = breakdown?.phase ?? 'idle'
  const status = breakdown?.status ?? 'idle'
  const current = phaseIndex(currentPhase)
  const progress = Math.min(1, Math.max(0, breakdown?.progress ?? 0))

  const activePhaseDef = PHASES[current]
  const activeAgentId = useMemo(() => {
    const lastActivity = breakdown?.activities?.[breakdown.activities.length - 1]
    return lastActivity?.agent ?? activePhaseDef?.agents[0] ?? null
  }, [breakdown, activePhaseDef])

  return (
    <section className="surface-card relative overflow-hidden p-6">
      {/* Ambient decoration */}
      <div className="pointer-events-none absolute inset-x-0 -top-24 h-48 bg-radial-fade opacity-60" />
      <div className="pointer-events-none absolute inset-0 grid-overlay opacity-30" />

      {/* Header */}
      <div className="relative mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sparkles className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold tracking-tight">
            Development Pipeline
          </h2>
          {breakdown?.cycle ? (
            <span className="chip">
              Cycle #{breakdown.cycle}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
          {breakdown?.sub_phase && (
            <span className="font-mono uppercase tracking-wider">
              {breakdown.sub_phase.replace(/-/g, ' ')}
            </span>
          )}
          <span
            className={cn(
              'rounded-full px-2 py-0.5 font-mono uppercase tracking-wider',
              status === 'running' && 'bg-primary/15 text-primary',
              status === 'completed' && 'bg-emerald-500/15 text-emerald-300',
              status === 'blocked' && 'bg-red-500/15 text-red-300',
              status === 'idle' && 'bg-muted text-muted-foreground',
            )}
          >
            {status}
          </span>
        </div>
      </div>

      {/* Phase rail */}
      <div className="relative grid grid-cols-5 gap-3">
        {PHASES.map((phase, idx) => {
          const isCompleted = idx < current
          const isActive = idx === current
          const phaseProgress = isActive ? progress : isCompleted ? 1 : 0

          return (
            <div key={phase.id} className="relative flex flex-col">
              <PhaseCard
                phase={phase}
                isActive={isActive}
                isCompleted={isCompleted}
                progress={phaseProgress}
              />
              {idx < PHASES.length - 1 && (
                <PhaseConnector
                  isCompleted={isCompleted}
                  isActive={isActive}
                  progress={phaseProgress}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Active work strip */}
      <div className="relative mt-6 grid grid-cols-12 gap-4">
        <ActiveAgentsStrip
          phaseId={currentPhase}
          activeAgentId={activeAgentId}
        />
        <CurrentTaskCard breakdown={breakdown} />
      </div>
    </section>
  )
}

// ── Subcomponents ──────────────────────────────────────────────────────────────

interface PhaseCardProps {
  phase: (typeof PHASES)[number]
  isActive: boolean
  isCompleted: boolean
  progress: number
}

function PhaseCard({ phase, isActive, isCompleted, progress }: PhaseCardProps) {
  const Icon = phase.icon

  return (
    <div
      className={cn(
        'relative flex flex-col gap-3 rounded-xl border p-4 transition-all duration-400',
        isActive &&
          'border-primary/50 bg-primary/[0.06] shadow-[0_0_0_1px_hsl(var(--primary)/0.2),_0_20px_40px_-20px_hsl(var(--primary)/0.5)]',
        isCompleted && 'border-emerald-500/30 bg-emerald-500/[0.04]',
        !isActive && !isCompleted && 'border-border bg-surface-muted/50',
      )}
    >
      {/* Node with icon */}
      <div className="flex items-center gap-3">
        <div
          className={cn(
            'relative flex h-9 w-9 items-center justify-center rounded-lg transition-all duration-300',
            isActive && `bg-gradient-to-br ${phase.gradient} shadow-glow-indigo`,
            isCompleted && 'bg-gradient-to-br from-emerald-500 to-green-500',
            !isActive && !isCompleted && 'bg-surface-elevated',
          )}
        >
          {isCompleted ? (
            <Check className="h-4 w-4 text-white" strokeWidth={3} />
          ) : isActive ? (
            <Icon className="h-4 w-4 text-white" strokeWidth={2.4} />
          ) : (
            <Icon className="h-4 w-4 text-muted-foreground" />
          )}
          {isActive && (
            <span className="absolute inset-0 animate-pulse-glow rounded-lg" />
          )}
        </div>

        <div className="flex flex-col">
          <span
            className={cn(
              'text-[10px] font-mono uppercase tracking-[0.2em]',
              isActive && 'text-primary',
              isCompleted && 'text-emerald-400',
              !isActive && !isCompleted && 'text-muted-foreground',
            )}
          >
            {`0${PHASES.findIndex((p) => p.id === phase.id) + 1}`}
          </span>
          <span
            className={cn(
              'text-sm font-semibold tracking-tight',
              !isActive && !isCompleted && 'text-muted-foreground',
            )}
          >
            {phase.label}
          </span>
        </div>
      </div>

      {/* Description / progress */}
      <div className="flex flex-col gap-2">
        <p className={cn(
          'text-[11px] leading-relaxed line-clamp-2',
          !isActive && !isCompleted ? 'text-muted-foreground/60' : 'text-muted-foreground',
        )}>
          {phase.description}
        </p>
        <div className="relative h-1 overflow-hidden rounded-full bg-border">
          <div
            className={cn(
              'absolute left-0 top-0 h-full rounded-full transition-all duration-500',
              isCompleted && 'w-full bg-gradient-to-r from-emerald-500 to-green-400',
              isActive && 'bg-gradient-to-r from-primary via-secondary to-primary shimmer-bg animate-shimmer bg-[length:200%_100%]',
            )}
            style={{ width: isCompleted ? '100%' : isActive ? `${progress * 100}%` : '0%' }}
          />
        </div>
      </div>

      {/* Active spinner + percentage */}
      {isActive && (
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] font-medium text-primary">
            <Loader2 className="h-3 w-3 animate-spin" />
            <span className="uppercase tracking-wider">Running</span>
          </div>
          <span className="font-mono text-[10px] text-muted-foreground tabular-nums">
            {Math.round(progress * 100)}%
          </span>
        </div>
      )}
    </div>
  )
}

function PhaseConnector({
  isCompleted,
  isActive,
  progress,
}: {
  isCompleted: boolean
  isActive: boolean
  progress: number
}) {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute right-[-0.75rem] top-8 flex h-1 w-3 items-center"
    >
      <div
        className={cn(
          'h-px w-full transition-colors',
          isCompleted ? 'bg-emerald-400/70' : 'bg-border',
        )}
      />
      {isActive && progress < 1 && (
        <ArrowRight className="absolute right-0 h-3 w-3 animate-pulse text-primary" />
      )}
    </div>
  )
}

function ActiveAgentsStrip({
  phaseId,
  activeAgentId,
}: {
  phaseId: string
  activeAgentId: string | null
}) {
  const phase = PHASES.find((p) => p.id === phaseId)
  if (!phase) {
    return (
      <div className="col-span-5 flex items-center gap-3 rounded-lg border border-border bg-surface-muted/40 p-4">
        <CircleDot className="h-4 w-4 text-muted-foreground animate-pulse" />
        <span className="text-xs text-muted-foreground">Awaiting next cycle…</span>
      </div>
    )
  }
  return (
    <div className="col-span-5 flex flex-col gap-3 rounded-lg border border-border bg-surface-muted/40 p-4">
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
          Active Crew
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {phase.agents.map((id) => {
          const agent = getAgent(id)
          const isActive = activeAgentId === id
          return (
            <div
              key={id}
              className={cn(
                'flex items-center gap-2 rounded-full border px-2 py-1 transition-all',
                isActive
                  ? 'border-primary/40 bg-primary/10 animate-slide-in-up'
                  : 'border-border bg-surface-muted/60',
              )}
            >
              <AgentAvatar agentId={id} size="xs" active={isActive} />
              <span className={cn(
                'text-[11px] font-medium',
                isActive ? 'text-foreground' : 'text-muted-foreground',
              )}>
                {agent.name}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CurrentTaskCard({ breakdown }: { breakdown: FlowBreakdown | null }) {
  const currentTask = breakdown?.current_task
  const nextTask = breakdown?.next_task
  const completed = breakdown?.completed_tasks ?? []
  const pending = breakdown?.pending_tasks ?? []

  return (
    <div className="col-span-7 flex flex-col gap-2 rounded-lg border border-border bg-surface-muted/40 p-4">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
          Now Working
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">
          {completed.length} done · {pending.length} pending
        </span>
      </div>
      <div className="flex items-center gap-2">
        {currentTask ? (
          <>
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            <span className="text-sm font-medium tracking-tight">
              {currentTask}
            </span>
          </>
        ) : (
          <span className="text-sm text-muted-foreground">Waiting for next task…</span>
        )}
      </div>
      {nextTask && (
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <ArrowRight className="h-3 w-3" />
          <span>Next: {nextTask}</span>
        </div>
      )}
    </div>
  )
}
