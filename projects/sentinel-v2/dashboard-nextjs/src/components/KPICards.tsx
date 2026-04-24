'use client'

import { useMemo } from 'react'
import type { Draft, DraftStatus, FlowBreakdown } from '@/types/sentinel'
import { cn } from '@/lib/utils'

interface KPICardsProps {
  drafts: Draft[]
  breakdown: FlowBreakdown | null
}

type KPI = {
  key: string
  label: string
  value: number
  sub?: string
  accent: string
  gradient: string
  tone: 'neutral' | 'warn' | 'info' | 'success' | 'danger'
}

export default function KPICards({ drafts, breakdown }: KPICardsProps) {
  const kpis: KPI[] = useMemo(() => {
    const by = (s: DraftStatus) => drafts.filter((d) => d.status === s).length
    const total = drafts.length
    const pending = by('pending')
    const approved = by('approved') + by('queued')
    const building = by('building')
    const done = by('built') + by('deployed')
    const rejected = by('rejected')

    return [
      {
        key: 'drafts',
        label: 'Drafts',
        value: total,
        sub: `${total - rejected} active`,
        accent: 'text-indigo-300',
        gradient: 'from-indigo-500 to-violet-500',
        tone: 'info',
      },
      {
        key: 'pending',
        label: 'Pending',
        value: pending,
        sub: pending ? 'Waiting for you' : 'Inbox zero',
        accent: 'text-amber-300',
        gradient: 'from-amber-500 to-orange-500',
        tone: pending > 0 ? 'warn' : 'neutral',
      },
      {
        key: 'approved',
        label: 'Approved',
        value: approved,
        sub: approved ? 'In build queue' : 'Nothing queued',
        accent: 'text-violet-300',
        gradient: 'from-violet-500 to-fuchsia-500',
        tone: 'info',
      },
      {
        key: 'building',
        label: 'Building',
        value: building,
        sub: breakdown?.current_task
          ? truncate(breakdown.current_task, 28)
          : building
            ? 'Crew working'
            : 'Idle',
        accent: 'text-primary',
        gradient: 'from-indigo-500 via-violet-500 to-fuchsia-500',
        tone: building > 0 ? 'info' : 'neutral',
      },
      {
        key: 'done',
        label: 'Shipped',
        value: done,
        sub: done ? 'Live in production' : '—',
        accent: 'text-emerald-300',
        gradient: 'from-emerald-500 to-green-500',
        tone: 'success',
      },
      {
        key: 'rejected',
        label: 'Rejected',
        value: rejected,
        sub: rejected ? 'Filtered out' : '—',
        accent: 'text-rose-300',
        gradient: 'from-rose-500 to-red-500',
        tone: rejected > 0 ? 'danger' : 'neutral',
      },
    ]
  }, [drafts, breakdown])

  return (
    <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {kpis.map((k, i) => (
        <KPICard key={k.key} kpi={k} index={i} />
      ))}
    </section>
  )
}

function KPICard({ kpi, index }: { kpi: KPI; index: number }) {
  const isActive = kpi.value > 0 && kpi.tone !== 'neutral'

  return (
    <div
      className={cn(
        'surface-card group relative overflow-hidden p-4 transition-all animate-slide-in-up',
        isActive && 'hover:border-border-strong',
      )}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      {/* Ambient accent */}
      <div
        aria-hidden
        className={cn(
          'pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full bg-gradient-to-br opacity-10 blur-2xl transition-opacity group-hover:opacity-20',
          kpi.gradient,
        )}
      />

      {/* Header — label + colored dot aligned, no icon */}
      <div className="relative flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          {kpi.label}
        </span>
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full bg-gradient-to-br',
            kpi.gradient,
            !isActive && 'opacity-40',
          )}
        />
      </div>

      <div className="relative mt-3 flex items-baseline gap-2">
        <span
          className={cn(
            'font-mono text-[30px] font-semibold leading-none tabular-nums',
            isActive ? 'text-foreground' : 'text-muted-foreground/70',
          )}
        >
          {kpi.value}
        </span>
      </div>

      {kpi.sub && (
        <p className="relative mt-1.5 truncate text-[11px] text-muted-foreground">
          {kpi.sub}
        </p>
      )}
    </div>
  )
}

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}
