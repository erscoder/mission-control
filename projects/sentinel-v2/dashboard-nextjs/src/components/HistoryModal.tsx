'use client'

import { useMemo } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import {
  History,
  ArrowRight,
  Calendar,
  X,
  Search,
} from 'lucide-react'
import type { Draft } from '@/types/sentinel'
import { cn, formatRelative } from '@/lib/utils'

interface HistoryModalProps {
  drafts: Draft[]
  children: React.ReactNode
}

export default function HistoryModal({ drafts, children }: HistoryModalProps) {
  const items = useMemo(() => {
    const list = drafts.filter(
      (x) => x.status === 'validated' || x.status === 'rejected' || x.status === 'failed',
    )
    list.sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
    return list
  }, [drafts])

  const validatedCount = items.filter((x) => x.status === 'validated').length
  const rejectedCount = items.length - validatedCount
  const total = items.length

  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{children}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm data-[state=open]:animate-fade-in" />
        <Dialog.Content className="dialog-content fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[min(960px,92vw)] flex-col overflow-hidden rounded-xl border border-border-strong bg-surface-elevated shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600">
                <History className="h-4 w-4 text-white" />
              </div>
              <div>
                <Dialog.Title className="text-sm font-semibold tracking-tight">
                  History
                </Dialog.Title>
                <Dialog.Description className="text-[11px] text-muted-foreground">
                  {total} total · {validatedCount} validated · {rejectedCount} rejected
                </Dialog.Description>
              </div>
            </div>
            <Dialog.Close asChild>
              <button
                className="flex h-8 w-8 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </Dialog.Close>
          </div>

          {/* Body — chronological, newest first */}
          <div className="flex-1 overflow-y-auto p-6">
            {total === 0 ? (
              <EmptyHistory />
            ) : (
              <ul className="flex flex-col gap-2">
                {items.map((d) => (
                  <HistoryItem
                    key={d.id}
                    draft={d}
                    variant={d.status === 'validated' ? 'validated' : 'rejected'}
                  />
                ))}
              </ul>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function HistoryItem({
  draft,
  variant,
}: {
  draft: Draft
  variant: 'validated' | 'rejected'
}) {
  const isDeployed = variant === 'validated'
  return (
    <li
      className={cn(
        'group relative flex items-start gap-3 overflow-hidden rounded-lg border bg-surface-muted/40 px-4 py-3 transition-colors hover:bg-surface-muted/60',
        isDeployed ? 'border-emerald-500/20' : 'border-rose-500/20',
      )}
    >
      {/* stripe */}
      <span
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-y-0 left-0 w-[2px]',
          isDeployed
            ? 'bg-gradient-to-b from-emerald-400 to-green-500'
            : 'bg-gradient-to-b from-rose-400 to-red-500',
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="truncate text-[13px] font-semibold tracking-tight">
            {draft.title}
          </h4>
          <span
            className={cn(
              'chip font-mono uppercase tracking-wider',
              isDeployed
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-300',
            )}
          >
            {isDeployed ? 'Validated' : 'Rejected at draft'}
          </span>
          {draft.cycle ? (
            <span className="chip bg-background/60">Cycle #{draft.cycle}</span>
          ) : null}
          <span className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground">
            <Calendar className="h-3 w-3" />
            {formatRelative(draft.updated_at || draft.created_at)}
          </span>
        </div>
        {draft.tagline && (
          <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
            {draft.tagline}
          </p>
        )}
        {draft.description && (
          <p className="mt-1.5 line-clamp-2 text-[12px] leading-relaxed text-foreground/80">
            {draft.description}
          </p>
        )}
        {!isDeployed && draft.revision_notes && (
          <div className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
            <p className="text-[10px] font-mono uppercase tracking-wider text-amber-300">
              Reason
            </p>
            <p className="mt-0.5 text-[12px] text-amber-100/80">{draft.revision_notes}</p>
          </div>
        )}
      </div>
      {isDeployed && draft.deployment_url && (
        <a
          href={draft.deployment_url}
          target="_blank"
          rel="noreferrer"
          className="flex flex-shrink-0 items-center gap-1 self-center rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-[11px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500 hover:text-white"
        >
          Open
          <ArrowRight className="h-3 w-3" />
        </a>
      )}
    </li>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyHistory() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-muted/60">
        <Search className="h-5 w-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">No history yet</p>
      <p className="max-w-[320px] text-[11px] text-muted-foreground">
        Apps you deploy and drafts you reject will show up here.
      </p>
    </div>
  )
}
