'use client'

import { useState } from 'react'
import {
  CheckCircle,
  XCircle,
  Pencil,
  ShieldCheck,
  Clock,
  History,
} from 'lucide-react'
import type { ApprovalItem, ApprovalState } from '@/types/sentinel'
import { cn, formatRelative } from '@/lib/utils'

interface ApprovalPanelProps {
  approvalState: ApprovalState | null
  onApprove: () => void
  onReject: () => void
  onRevise: (notes: string) => void
}

function extractPending(state: ApprovalState | null): ApprovalItem | null {
  if (!state) return null
  const raw = state.pending
  if (!raw) return null
  if (Array.isArray(raw)) {
    return raw.find((i) => i.status === 'pending') ?? null
  }
  if (typeof raw === 'object') {
    const item = raw as ApprovalItem
    if (item.title && (item.status === 'pending' || item.status === undefined)) {
      return item
    }
  }
  return null
}

export default function ApprovalPanel({
  approvalState,
  onApprove,
  onReject,
  onRevise,
}: ApprovalPanelProps) {
  const pending = extractPending(approvalState)
  const [reviseOpen, setReviseOpen] = useState(false)
  const [notes, setNotes] = useState('')
  const last = approvalState?.last_action
  const lastAt = approvalState?.last_action_at
  const approvedCount = approvalState?.approved?.length ?? 0
  const rejectedCount = approvalState?.rejected?.length ?? 0

  if (!pending) {
    return (
      <section className="surface-card p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-surface-elevated">
            <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
          <div>
            <h3 className="text-xs font-semibold tracking-tight">Human Approval</h3>
            <p className="text-[10px] text-muted-foreground">No pending proposals</p>
          </div>
          {last && (
            <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
              <Clock className="h-3 w-3" />
              last {last} {formatRelative(lastAt)}
            </span>
          )}
        </div>

        {(approvedCount > 0 || rejectedCount > 0) && (
          <div className="mt-3 flex items-center gap-3 border-t border-border/60 pt-3 text-[11px]">
            <History className="h-3 w-3 text-muted-foreground" />
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="text-muted-foreground">Approved:</span>
              <span className="font-mono font-semibold tabular-nums">{approvedCount}</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
              <span className="text-muted-foreground">Rejected:</span>
              <span className="font-mono font-semibold tabular-nums">{rejectedCount}</span>
            </span>
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="surface-card animate-slide-in-up overflow-hidden p-5 shadow-glow-indigo">
      <div className="mb-4 flex items-center gap-2.5">
        <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-orange-500">
          <ShieldCheck className="h-4 w-4 text-white" />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 animate-ping rounded-full bg-amber-300" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold tracking-tight">
            Awaiting your approval
          </h3>
          <p className="text-[11px] text-muted-foreground line-clamp-1">
            Cycle #{pending.cycle} · {pending.title}
          </p>
        </div>
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
          Pending
        </span>
      </div>

      {/* Actions */}
      <div className="grid grid-cols-3 gap-2">
        <ActionButton
          onClick={onApprove}
          icon={CheckCircle}
          label="Approve"
          tone="emerald"
        />
        <ActionButton
          onClick={() => setReviseOpen((v) => !v)}
          icon={Pencil}
          label="Revise"
          tone="amber"
          active={reviseOpen}
        />
        <ActionButton onClick={onReject} icon={XCircle} label="Reject" tone="rose" />
      </div>

      {reviseOpen && (
        <div className="mt-3 flex flex-col gap-2 rounded-lg border border-border bg-surface-muted/40 p-3 animate-slide-in-up">
          <label className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
            Revision notes
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Tell the crew what to change…"
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

      {last && (
        <div className="mt-3 flex items-center gap-1.5 text-[10px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          <span>last action: {last} {formatRelative(lastAt)}</span>
        </div>
      )}
    </section>
  )
}

function ActionButton({
  onClick,
  icon: Icon,
  label,
  tone,
  active = false,
}: {
  onClick: () => void
  icon: React.ComponentType<{ className?: string }>
  label: string
  tone: 'emerald' | 'rose' | 'amber'
  active?: boolean
}) {
  const toneCls = {
    emerald:
      'border-emerald-500/30 text-emerald-300 hover:bg-emerald-500 hover:text-white hover:border-emerald-400',
    rose: 'border-rose-500/30 text-rose-300 hover:bg-rose-500 hover:text-white hover:border-rose-400',
    amber: 'border-amber-500/30 text-amber-300 hover:bg-amber-500 hover:text-white hover:border-amber-400',
  }[tone]

  const activeCls = {
    emerald: 'bg-emerald-500/10',
    rose: 'bg-rose-500/10',
    amber: 'bg-amber-500/10',
  }[tone]

  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex items-center justify-center gap-1.5 rounded-lg border px-2 py-2 text-[11px] font-semibold tracking-tight transition-all',
        toneCls,
        active && activeCls,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}
