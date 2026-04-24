'use client'

import { useMemo, useState } from 'react'
import {
  CheckCircle,
  XCircle,
  Pencil,
  Lightbulb,
  ChevronDown,
  Clock,
  Target,
  Layers,
  Tag,
  AlertCircle,
  Zap,
  Inbox,
  Sparkles,
} from 'lucide-react'
import type { Draft } from '@/types/sentinel'
import { cn, formatRelative } from '@/lib/utils'

interface DraftsQueueProps {
  drafts: Draft[]
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onRevise: (id: string, notes: string) => void
}

export default function DraftsQueue({
  drafts,
  onApprove,
  onReject,
  onRevise,
}: DraftsQueueProps) {
  const pending = useMemo(
    () => drafts.filter((d) => d.status === 'pending'),
    [drafts],
  )

  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const toggle = (id: string) =>
    setExpanded((m) => ({ ...m, [id]: !m[id] }))

  return (
    <section className="surface-card flex h-full w-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/60 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-amber-500 via-orange-500 to-rose-500">
            <Lightbulb className="h-3.5 w-3.5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Draft Queue</h2>
            <p className="text-[10px] text-muted-foreground">
              {pending.length} awaiting review · {drafts.length} total
            </p>
          </div>
        </div>
        {pending.length > 0 && (
          <div className="flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400/60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-400" />
            </span>
            REVIEW PENDING
          </div>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto overscroll-contain px-4 py-4">
        {pending.length === 0 ? (
          <EmptyDrafts total={drafts.length} />
        ) : (
          <ul className="flex flex-col gap-3">
            {pending.map((draft, idx) => (
              <DraftCard
                key={draft.id}
                draft={draft}
                index={idx}
                expanded={!!expanded[draft.id]}
                onToggle={() => toggle(draft.id)}
                onApprove={() => onApprove(draft.id)}
                onReject={() => onReject(draft.id)}
                onRevise={(notes) => onRevise(draft.id, notes)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

// ── Draft Card ────────────────────────────────────────────────────────────────

function DraftCard({
  draft,
  index,
  expanded,
  onToggle,
  onApprove,
  onReject,
  onRevise,
}: {
  draft: Draft
  index: number
  expanded: boolean
  onToggle: () => void
  onApprove: () => void
  onReject: () => void
  onRevise: (notes: string) => void
}) {
  const [reviseOpen, setReviseOpen] = useState(false)
  const [notes, setNotes] = useState('')

  return (
    <li
      className="group relative animate-slide-in-up overflow-hidden rounded-xl border border-border-strong bg-surface-elevated shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset,_0_20px_40px_-20px_rgba(0,0,0,0.4)] transition-all hover:border-primary/30 hover:shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset,_0_20px_40px_-20px_hsl(var(--primary)/0.3)]"
      style={{ animationDelay: `${Math.min(index, 5) * 60}ms` }}
    >
      {/* Left accent stripe for pending (amber) — visual distinction */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-amber-400 via-orange-400 to-rose-500 opacity-80"
      />
      {/* Row: icon + title + score + chevron */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 pt-4 text-left"
      >
        <div className="relative flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500 shadow-lg">
          <Lightbulb className="h-4 w-4 text-white" strokeWidth={2.4} />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full border-2 border-background bg-primary text-[9px] font-semibold text-primary-foreground">
            {index + 1}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-sm font-semibold tracking-tight">
              {draft.title}
            </h3>
            <span className="chip flex-shrink-0 bg-amber-500/10 text-amber-300">
              <Clock className="h-2.5 w-2.5" />
              Pending
            </span>
          </div>
          {draft.tagline && (
            <p className="mt-0.5 line-clamp-1 text-[12px] text-muted-foreground">
              {draft.tagline}
            </p>
          )}
          <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
            <span className="font-mono">Cycle #{draft.cycle}</span>
            {draft.estimated_hours != null && (
              <span className="font-mono">~{draft.estimated_hours}h</span>
            )}
            {draft.created_at && (
              <span>{formatRelative(draft.created_at)}</span>
            )}
          </div>
        </div>

        <div className="flex flex-shrink-0 flex-col items-end gap-1">
          <ScoreBadge value={draft.tech_fit ?? 0} />
          <ChevronDown
            className={cn(
              'h-4 w-4 text-muted-foreground transition-transform',
              expanded && 'rotate-180',
            )}
          />
        </div>
      </button>

      {/* Stats strip always visible */}
      <div className="mt-3 grid grid-cols-2 gap-3 px-4">
        <MiniStat
          icon={Target}
          label="Tech fit"
          value={`${Math.round((draft.tech_fit ?? 0) * 100)}%`}
          tone="indigo"
        />
        <MiniStat
          icon={Layers}
          label="Complexity"
          value={`${draft.complexity ?? 0}/5`}
          tone="amber"
        />
      </div>
      {/* bottom spacer so the action row doesn't butt against stats when collapsed */}
      <div className="h-3" />

      {/* Expanded content */}
      {expanded && (
        <div className="animate-fade-in space-y-4 px-4 pt-4 pb-2">
          {draft.description && (
            <DetailBlock
              icon={Sparkles}
              label="Description"
              tone="text-indigo-300"
              value={draft.description}
            />
          )}
          {draft.problem && (
            <DetailBlock
              icon={AlertCircle}
              label="Problem"
              tone="text-rose-300"
              value={draft.problem}
            />
          )}
          {draft.solution && (
            <DetailBlock
              icon={Zap}
              label="Solution"
              tone="text-amber-300"
              value={draft.solution}
            />
          )}
          {draft.tags && draft.tags.length > 0 && (
            <div className="flex items-center gap-2">
              <Tag className="h-3 w-3 text-muted-foreground" />
              <div className="flex flex-wrap gap-1">
                {draft.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-border bg-surface-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {draft.revision_notes && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-amber-300">
                Revision requested
              </p>
              <p className="mt-0.5 text-[12px] text-amber-100/80">
                {draft.revision_notes}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Action row */}
      <div className="border-t border-border/80 bg-background/40 px-4 py-3">
        {!reviseOpen ? (
          <div className="grid grid-cols-3 gap-2">
            <CardAction
              onClick={onApprove}
              icon={CheckCircle}
              label="Approve"
              tone="emerald"
            />
            <CardAction
              onClick={() => setReviseOpen(true)}
              icon={Pencil}
              label="Revise"
              tone="amber"
            />
            <CardAction
              onClick={onReject}
              icon={XCircle}
              label="Reject"
              tone="rose"
            />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="What should the crew change in this draft?"
              autoFocus
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-[12px] outline-none ring-primary/40 placeholder:text-muted-foreground/50 focus:ring-2"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => {
                  setReviseOpen(false)
                  setNotes('')
                }}
                className="rounded-md border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
              <button
                disabled={!notes.trim()}
                onClick={() => {
                  onRevise(notes.trim())
                  setReviseOpen(false)
                  setNotes('')
                }}
                className="rounded-md bg-gradient-to-br from-amber-500 to-orange-500 px-3 py-1 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                Send revision
              </button>
            </div>
          </div>
        )}
      </div>
    </li>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function ScoreBadge({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  const tone =
    pct >= 70
      ? 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10'
      : pct >= 40
        ? 'text-amber-300 border-amber-500/30 bg-amber-500/10'
        : 'text-rose-300 border-rose-500/30 bg-rose-500/10'
  return (
    <span
      className={cn(
        'flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold tabular-nums',
        tone,
      )}
    >
      {pct}
    </span>
  )
}

function MiniStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  tone: 'indigo' | 'amber'
}) {
  const accent = tone === 'indigo' ? 'text-indigo-300' : 'text-amber-300'
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-background/60 px-2.5 py-1.5">
      <div className="flex items-center gap-1.5">
        <Icon className={cn('h-3 w-3', accent)} />
        <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
      <span className="font-mono text-[11px] font-semibold tabular-nums">
        {value}
      </span>
    </div>
  )
}

function DetailBlock({
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
        <p className="mt-0.5 whitespace-pre-wrap text-[12.5px] leading-relaxed text-foreground/90">
          {value}
        </p>
      </div>
    </div>
  )
}

function CardAction({
  onClick,
  icon: Icon,
  label,
  tone,
}: {
  onClick: () => void
  icon: React.ComponentType<{ className?: string }>
  label: string
  tone: 'emerald' | 'amber' | 'rose'
}) {
  const classes = {
    emerald:
      'border-emerald-500/30 text-emerald-300 hover:bg-emerald-500 hover:text-white hover:border-emerald-400',
    amber:
      'border-amber-500/30 text-amber-300 hover:bg-amber-500 hover:text-white hover:border-amber-400',
    rose: 'border-rose-500/30 text-rose-300 hover:bg-rose-500 hover:text-white hover:border-rose-400',
  }[tone]
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center justify-center gap-1.5 rounded-lg border bg-background/40 px-2 py-2 text-[11px] font-semibold tracking-tight transition-all active:scale-95',
        classes,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyDrafts({ total }: { total: number }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-elevated">
        <Inbox className="h-5 w-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-foreground">Inbox zero</p>
      <p className="max-w-[280px] text-[11px] text-muted-foreground">
        No drafts waiting for review.
        {total > 0 && ` All ${total} drafts have been resolved — see the build queue below.`}
      </p>
    </div>
  )
}
