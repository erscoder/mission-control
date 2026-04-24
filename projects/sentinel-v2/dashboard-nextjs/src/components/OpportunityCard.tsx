'use client'

import {
  Lightbulb,
  Rocket,
  Zap,
  Layers,
  Target,
  AlertCircle,
} from 'lucide-react'
import type { FlowState } from '@/types/sentinel'
import { cn } from '@/lib/utils'

interface OpportunityCardProps {
  flowState: FlowState | null
}

export default function OpportunityCard({ flowState }: OpportunityCardProps) {
  const opp = flowState?.opportunity
  const score = flowState?.match_score ?? 0

  if (!opp || !opp.title) {
    return (
      <section className="surface-card flex flex-col items-center justify-center p-8 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-elevated">
          <Lightbulb className="h-5 w-5 text-muted-foreground" />
        </div>
        <p className="mt-3 text-sm font-semibold">No opportunity yet</p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Research phase will surface the top pick here.
        </p>
      </section>
    )
  }

  const techFit = opp.tech_fit ?? 0
  const complexity = opp.complexity ?? 0
  const deployed = flowState?.deployed

  return (
    <section className="surface-card border-gradient relative overflow-hidden p-5">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500 shadow-lg">
          <Lightbulb className="h-5 w-5 text-white" strokeWidth={2.4} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-amber-300">
              Top Opportunity
            </span>
            {deployed && (
              <span className="flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                <Rocket className="h-3 w-3" /> Live
              </span>
            )}
          </div>
          <h3 className="mt-0.5 text-base font-semibold leading-tight tracking-tight text-balance">
            {opp.title}
          </h3>
        </div>
        <ScoreDial score={score} />
      </div>

      {/* Problem / Solution */}
      {(opp.problem || opp.solution) && (
        <div className="mt-5 grid gap-3">
          {opp.problem && (
            <InfoRow
              icon={AlertCircle}
              label="Problem"
              tone="text-rose-300"
              value={opp.problem}
            />
          )}
          {opp.solution && (
            <InfoRow
              icon={Zap}
              label="Solution"
              tone="text-indigo-300"
              value={opp.solution}
            />
          )}
        </div>
      )}

      {/* Fit bars */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <FitBar icon={Target} label="Tech fit" value={techFit} tone="indigo" />
        <FitBar
          icon={Layers}
          label="Complexity"
          value={complexity}
          tone="amber"
          inverse
        />
      </div>
    </section>
  )
}

function InfoRow({
  icon: Icon,
  label,
  tone,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  tone: string
  value: string
}) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className={cn('mt-0.5 h-3.5 w-3.5 flex-shrink-0', tone)} />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
          {label}
        </p>
        <p className="text-[13px] leading-relaxed text-foreground/90 line-clamp-3">
          {value}
        </p>
      </div>
    </div>
  )
}

function ScoreDial({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score * 100))
  const tone =
    pct >= 70 ? 'from-emerald-500 to-green-400'
      : pct >= 40 ? 'from-amber-500 to-orange-400'
      : 'from-rose-500 to-pink-400'

  return (
    <div className="relative flex h-14 w-14 flex-shrink-0 items-center justify-center">
      <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
        <circle
          cx="18"
          cy="18"
          r="15"
          fill="none"
          stroke="hsl(var(--border))"
          strokeWidth="2.5"
        />
        <circle
          cx="18"
          cy="18"
          r="15"
          fill="none"
          stroke="url(#score-grad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 94.25} 94.25`}
          className="transition-all duration-700"
        />
        <defs>
          <linearGradient id="score-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" />
            <stop offset="100%" stopColor="hsl(var(--secondary))" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono text-[13px] font-semibold tabular-nums">
          {pct.toFixed(0)}
        </span>
        <span className="-mt-0.5 text-[8px] uppercase tracking-wider text-muted-foreground">
          match
        </span>
      </div>
      <span className={cn('sr-only', tone)} />
    </div>
  )
}

function FitBar({
  icon: Icon,
  label,
  value,
  tone,
  inverse = false,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: number
  tone: 'indigo' | 'amber'
  inverse?: boolean
}) {
  const pct = Math.min(100, Math.max(0, value * 100))
  const displayed = inverse ? 100 - pct : pct
  const gradient =
    tone === 'indigo' ? 'from-primary to-secondary' : 'from-amber-500 to-orange-400'
  const textTone = tone === 'indigo' ? 'text-indigo-300' : 'text-amber-300'

  return (
    <div className="rounded-lg border border-border bg-surface-muted/50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Icon className={cn('h-3 w-3', textTone)} />
          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            {label}
          </span>
        </div>
        <span className="font-mono text-[11px] font-semibold tabular-nums">
          {pct.toFixed(0)}
        </span>
      </div>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-border">
        <div
          className={cn(
            'h-full rounded-full bg-gradient-to-r transition-all duration-700',
            gradient,
          )}
          style={{ width: `${displayed}%` }}
        />
      </div>
    </div>
  )
}
