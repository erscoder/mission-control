'use client'

import { useState } from 'react'
import {
  Clock,
  Hammer,
  Rocket,
  XCircle,
  Layers3,
  ArrowRight,
  CheckCircle,
  ShieldCheck,
  FlaskConical,
  AlertTriangle,
  Gauge,
  Cpu,
  Check,
  Loader2,
  X,
  Lightbulb,
  ChevronDown,
  Pencil,
  Tag,
  Zap,
  Sparkles,
} from 'lucide-react'
import type { Draft, DraftStatus } from '@/types/sentinel'
import { cn } from '@/lib/utils'
import HistoryModal from './HistoryModal'
import { History } from 'lucide-react'

interface BuildQueueProps {
  queue: Draft[]
  allDrafts?: Draft[]
  onApproveDraft?: (id: string) => void
  onRejectDraft?: (id: string) => void
  onReviseDraft?: (id: string, notes: string) => void
  onRetryDraft?: (id: string) => void
  onApproveDeploy?: (id: string) => void
  onRejectDeploy?: (id: string) => void
  onRequestChanges?: (id: string, notes: string) => void
  onValidateDraft?: (id: string) => void
}

type StageKey = 'draft' | 'queued' | 'building' | 'review' | 'built' | 'deploying' | 'deployed'

const STAGE_ORDER: StageKey[] = [
  'draft',
  'queued',
  'building',
  'review',
  'built',
  'deploying',
  'deployed',
]

const STAGE: Record<StageKey, {
  label: string
  icon: React.ComponentType<{ className?: string }>
  tone: string
  bg: string
  ring: string
  stripe: string
}> = {
  draft: {
    label: 'Draft',
    icon: Lightbulb,
    tone: 'text-amber-300',
    bg: 'bg-gradient-to-br from-amber-400 via-orange-500 to-rose-500',
    ring: 'border-amber-500/25',
    stripe: 'bg-gradient-to-b from-amber-300 via-orange-500 to-rose-500',
  },
  queued: {
    label: 'Queued',
    icon: Clock,
    tone: 'text-zinc-300',
    bg: 'bg-zinc-600',
    ring: 'border-zinc-500/20',
    stripe: 'bg-gradient-to-b from-zinc-400 to-zinc-600',
  },
  building: {
    label: 'Building',
    icon: Hammer,
    tone: 'text-indigo-300',
    bg: 'bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500',
    ring: 'border-indigo-500/25',
    stripe: 'bg-gradient-to-b from-indigo-400 via-violet-500 to-fuchsia-500',
  },
  review: {
    label: 'Review',
    icon: ShieldCheck,
    tone: 'text-amber-300',
    bg: 'bg-gradient-to-br from-amber-500 via-orange-500 to-rose-500',
    ring: 'border-amber-500/25',
    stripe: 'bg-gradient-to-b from-amber-400 via-orange-500 to-rose-500',
  },
  built: {
    label: 'Built',
    icon: FlaskConical,
    tone: 'text-cyan-300',
    bg: 'bg-gradient-to-br from-cyan-500 to-sky-500',
    ring: 'border-cyan-500/25',
    stripe: 'bg-gradient-to-b from-cyan-400 to-sky-500',
  },
  deploying: {
    label: 'Deploying',
    icon: Rocket,
    tone: 'text-violet-300',
    bg: 'bg-gradient-to-br from-violet-500 to-fuchsia-500',
    ring: 'border-violet-500/25',
    stripe: 'bg-gradient-to-b from-violet-400 to-fuchsia-500',
  },
  deployed: {
    label: 'Deployed',
    icon: Rocket,
    tone: 'text-emerald-300',
    bg: 'bg-gradient-to-br from-emerald-500 to-green-500',
    ring: 'border-emerald-500/25',
    stripe: 'bg-gradient-to-b from-emerald-400 to-green-500',
  },
}

function currentStageIndex(s: DraftStatus): number {
  if (s === 'pending') return 0
  if (s === 'approved' || s === 'queued') return 1
  if (s === 'building') return 2
  if (s === 'review') return 3
  if (s === 'testing' || s === 'built') return 4
  if (s === 'pending_deploy' || s === 'deploying') return 5
  if (s === 'deployed') return 7 // past everything → all done
  return -1
}

export default function BuildQueue({
  queue,
  allDrafts,
  onApproveDraft,
  onRejectDraft,
  onReviseDraft,
  onRetryDraft,
  onApproveDeploy,
  onRejectDeploy,
  onRequestChanges,
  onValidateDraft,
}: BuildQueueProps) {
  // Active pipeline = everything NOT in history (validated / rejected move out)
  const active = queue.filter(
    (d) => d.status !== 'rejected' && d.status !== 'validated',
  )
  const isEmpty = active.length === 0
  const summary = countByStage(active)

  // History dataset: prefer the full drafts list (includes rejected/deployed);
  // fall back to queue if not provided.
  const historyDrafts = allDrafts ?? queue
  const historyCount =
    historyDrafts.filter(
      (d) => d.status === 'validated' || d.status === 'rejected' || d.status === 'failed' || d.status === 'rejected_deploy',
    ).length

  return (
    <section className="surface-card relative overflow-hidden p-5">
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
            <Layers3 className="h-3.5 w-3.5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Build Pipeline</h2>
            <p className="text-[10px] text-muted-foreground">
              {active.length} app{active.length === 1 ? '' : 's'} in flight
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {STAGE_ORDER.filter((k) => k !== 'deployed').map((k) => (
            <LegendChip key={k} stage={k} count={summary[k] ?? 0} />
          ))}
          {summary.failed > 0 && (
            <LegendChip stage="failed" count={summary.failed} />
          )}
          <div className="mx-1 h-4 w-px bg-border" />
          <HistoryModal drafts={historyDrafts}>
            <button
              type="button"
              className="flex items-center gap-1.5 rounded-md border border-border bg-surface-muted/60 px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              <History className="h-3 w-3" />
              History
              <span className="font-mono text-[10px] tabular-nums text-foreground">
                {historyCount}
              </span>
            </button>
          </HistoryModal>
        </div>
      </div>

      {isEmpty ? (
        <EmptyQueue />
      ) : (
        <ul className="flex flex-col gap-3">
          {active.map((d) => (
            <PipelineRow
              key={d.id}
              draft={d}
              onApproveDraft={onApproveDraft}
              onRejectDraft={onRejectDraft}
              onReviseDraft={onReviseDraft}
              onRetryDraft={onRetryDraft}
              onApproveDeploy={onApproveDeploy}
              onRejectDeploy={onRejectDeploy}
              onRequestChanges={onRequestChanges}
              onValidateDraft={onValidateDraft}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

// ── Pipeline Row ──────────────────────────────────────────────────────────────

function PipelineRow({
  draft,
  onApproveDraft,
  onRejectDraft,
  onReviseDraft,
  onRetryDraft,
  onApproveDeploy,
  onRejectDeploy,
  onRequestChanges,
  onValidateDraft,
}: {
  draft: Draft
  onApproveDraft?: (id: string) => void
  onRejectDraft?: (id: string) => void
  onReviseDraft?: (id: string, notes: string) => void
  onRetryDraft?: (id: string) => void
  onApproveDeploy?: (id: string) => void
  onRejectDeploy?: (id: string) => void
  onRequestChanges?: (id: string, notes: string) => void
  onValidateDraft?: (id: string) => void
}) {
  const failed = draft.status === 'failed' || draft.status === 'rejected_deploy'
  const currentIdx = currentStageIndex(draft.status)
  const isDoneState = draft.status === 'deployed'
  const activeStage: StageKey | null = isDoneState
    ? 'deployed'
    : currentIdx >= 0 && currentIdx < STAGE_ORDER.length
      ? STAGE_ORDER[currentIdx]
      : null
  const activeMeta = activeStage ? STAGE[activeStage] : null
  const progress = Math.min(1, Math.max(0, draft.build_progress ?? 0))
  const isBuildingStage = activeStage === 'building'
  const isReviewStage = activeStage === 'review'
  const isDraftStage = activeStage === 'draft'

  const [expanded, setExpanded] = useState(isDraftStage)
  const [reviseOpen, setReviseOpen] = useState(false)
  const [reviseNotes, setReviseNotes] = useState('')

  const m = (draft as unknown as { metrics?: { coverage_percent?: number; issues_count?: number; tests_passed?: number; tests_total?: number } }).metrics
  const issuesCount =
    (draft as unknown as { issues_count?: number }).issues_count ?? m?.issues_count
  const coverage =
    (draft as unknown as { coverage_percent?: number }).coverage_percent ?? m?.coverage_percent
  const testsPassed =
    (draft as unknown as { tests_passed?: number }).tests_passed ?? m?.tests_passed
  const testsTotal =
    (draft as unknown as { tests_total?: number }).tests_total ?? m?.tests_total

  const rowBorder = failed
    ? 'border-rose-500/25'
    : activeMeta
      ? activeMeta.ring
      : 'border-border'

  const stripeGradient = failed
    ? 'bg-gradient-to-b from-rose-400 to-red-600'
    : activeMeta?.stripe || 'bg-border'

  const canExpand = isDraftStage || Boolean(draft.description || draft.problem || draft.solution)

  return (
    <li
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-lg border bg-surface-elevated pl-5 pr-4 py-3 shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset,_0_10px_20px_-12px_rgba(0,0,0,0.5)] transition-colors animate-slide-in-up hover:bg-surface-elevated/90',
        rowBorder,
      )}
    >
      {/* Left accent stripe */}
      <span
        aria-hidden
        className={cn(
          'pointer-events-none absolute inset-y-0 left-0 w-[3px]',
          stripeGradient,
        )}
      />

      {/* Top row: stage icon + title + pill + metrics + actions */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-white shadow',
            failed ? 'bg-gradient-to-br from-rose-600 to-red-600' : activeMeta?.bg,
          )}
        >
          {failed ? (
            <X className="h-4 w-4" strokeWidth={3} />
          ) : isDoneState ? (
            <Check className="h-4 w-4" strokeWidth={3} />
          ) : isBuildingStage || isReviewStage ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : activeMeta ? (
            (() => {
              const Icon = activeMeta.icon
              return <Icon className="h-4 w-4" />
            })()
          ) : null}
        </div>

        <button
          type="button"
          onClick={() => canExpand && setExpanded((v) => !v)}
          disabled={!canExpand}
          className={cn(
            'min-w-0 flex-1 text-left',
            canExpand && 'cursor-pointer',
            !canExpand && 'cursor-default',
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-[13px] font-semibold tracking-tight">
              {draft.title}
            </h3>
            <span
              className={cn(
                'chip flex-shrink-0 font-mono uppercase tracking-wider',
                failed
                  ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                  : activeMeta &&
                      cn(activeMeta.ring, activeMeta.tone, 'bg-background/30'),
              )}
            >
              {failed ? 'Failed' : activeMeta?.label}
            </span>
            {draft.cycle ? (
              <span className="chip bg-surface-muted/60">Cycle #{draft.cycle}</span>
            ) : null}
            {canExpand && (
              <ChevronDown
                className={cn(
                  'ml-auto h-3.5 w-3.5 text-muted-foreground/60 transition-transform',
                  expanded && 'rotate-180',
                )}
              />
            )}
          </div>
          {draft.tagline && (
            <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
              {draft.tagline}
            </p>
          )}
          {/* Always-visible error reason on failed cards */}
          {failed && draft.revision_notes && (
            <p className="mt-1 line-clamp-2 rounded bg-rose-500/10 px-2 py-1 text-[11px] font-mono text-rose-300/90">
              {draft.revision_notes}
            </p>
          )}
        </button>

        {/* Right-side metrics / actions */}
        <div className="flex flex-shrink-0 items-center gap-2">
          {isDraftStage && (
            <>
              <ScoreBadge value={draft.tech_fit ?? 0} />
              <button
                type="button"
                onClick={() => onApproveDraft?.(draft.id)}
                className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500 hover:text-white"
                title="Approve draft — sends to build queue"
              >
                <CheckCircle className="h-3 w-3" />
                Approve
              </button>
              <button
                type="button"
                onClick={() => setReviseOpen((v) => !v)}
                className={cn(
                  'flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-300 transition-colors hover:bg-amber-500 hover:text-white',
                  reviseOpen && 'bg-amber-500/20',
                )}
                title="Request revision"
              >
                <Pencil className="h-3 w-3" />
                Revise
              </button>
              <button
                type="button"
                onClick={() => onRejectDraft?.(draft.id)}
                className="flex items-center rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-rose-300 transition-colors hover:bg-rose-500 hover:text-white"
                title="Reject draft"
              >
                <XCircle className="h-3 w-3" />
              </button>
            </>
          )}
          {isReviewStage && issuesCount != null && (
            <InlineMetric
              icon={AlertTriangle}
              label="Issues"
              value={String(issuesCount)}
              tone={issuesCount > 0 ? 'warn' : 'success'}
            />
          )}
          {activeStage === 'built' && (
            <>
              {coverage != null && (
                <InlineMetric
                  icon={Gauge}
                  label="Cov"
                  value={`${Math.round(coverage)}%`}
                  tone="info"
                />
              )}
              {testsTotal != null && (
                <InlineMetric
                  icon={Cpu}
                  label="Tests"
                  value={`${testsPassed ?? 0}/${testsTotal}`}
                  tone="info"
                />
              )}
              {(onApproveDeploy || onRejectDeploy) && (
                <>
                  <button
                    type="button"
                    onClick={() => onApproveDeploy?.(draft.id)}
                    className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500 hover:text-white"
                  >
                    <CheckCircle className="h-3 w-3" />
                    Deploy
                  </button>
                  <button
                    type="button"
                    onClick={() => setReviseOpen((v) => !v)}
                    className={cn(
                      'flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-300 transition-colors hover:bg-amber-500 hover:text-white',
                      reviseOpen && 'bg-amber-500/20',
                    )}
                    title="Request changes"
                  >
                    <Pencil className="h-3 w-3" />
                    Changes
                  </button>
                  <button
                    type="button"
                    onClick={() => onRejectDeploy?.(draft.id)}
                    className="flex items-center rounded-md border border-rose-500/30 bg-rose-500/10 px-2 py-1 text-rose-300 transition-colors hover:bg-rose-500 hover:text-white"
                    title="Reject deployment"
                  >
                    <XCircle className="h-3 w-3" />
                  </button>
                </>
              )}
            </>
          )}
          {draft.status === 'deployed' && (
            <>
              {draft.deployment_url && (
                <a
                  href={draft.deployment_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500 hover:text-white"
                >
                  Open
                  <ArrowRight className="h-3 w-3" />
                </a>
              )}
              <button
                type="button"
                onClick={() => onValidateDraft?.(draft.id)}
                className="flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold text-emerald-300 transition-colors hover:bg-emerald-500 hover:text-white"
                title="Mark as validated - move to history"
              >
                <CheckCircle className="h-3 w-3" />
                Validate
              </button>
              <button
                type="button"
                onClick={() => setReviseOpen((v) => !v)}
                className={cn(
                  'flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-300 transition-colors hover:bg-amber-500 hover:text-white',
                  reviseOpen && 'bg-amber-500/20',
                )}
                title="Request changes"
              >
                <Pencil className="h-3 w-3" />
                Changes
              </button>
            </>
          )}
          {failed && (
            <>
              {onRetryDraft && (
                <button
                  type="button"
                  onClick={() => onRetryDraft(draft.id)}
                  className="flex items-center gap-1 rounded-md border border-indigo-500/40 bg-indigo-500/10 px-2 py-1 text-[10px] font-semibold text-indigo-300 transition-colors hover:bg-indigo-500 hover:text-white"
                  title="Retry: resume from the last checkpoint if available, otherwise restart from pending"
                >
                  <Loader2 className="h-3 w-3" />
                  Retry
                </button>
              )}
              <button
                type="button"
                onClick={() => setReviseOpen((v) => !v)}
                className={cn(
                  'flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] font-semibold text-amber-300 transition-colors hover:bg-amber-500 hover:text-white',
                  reviseOpen && 'bg-amber-500/20',
                )}
                title="Request changes"
              >
                <Pencil className="h-3 w-3" />
                Changes
              </button>
            </>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && canExpand && (
        <div className="mt-3 grid grid-cols-1 gap-3 rounded-md border border-border/60 bg-background/40 p-3 md:grid-cols-2 animate-fade-in">
          {draft.description && (
            <DetailBlock
              icon={Sparkles}
              label="Description"
              tone="text-indigo-300"
              value={draft.description}
              wide
            />
          )}
          {draft.problem && (
            <DetailBlock
              icon={AlertTriangle}
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
            <div className="col-span-full flex items-center gap-2">
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
              {draft.estimated_hours != null && (
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                  est. ~{draft.estimated_hours}h
                </span>
              )}
            </div>
          )}
          {draft.revision_notes && (
            <div className="col-span-full rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2">
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

      {/* Revision note composer (draft, built, deployed, failed) */}
      {reviseOpen && (
        <div className="mt-3 flex flex-col gap-2 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 animate-slide-in-up">
          <label className="text-[10px] font-mono uppercase tracking-wider text-amber-300">
            {isDraftStage ? 'Revision notes' : 'Change request'}
          </label>
          <textarea
            value={reviseNotes}
            onChange={(e) => setReviseNotes(e.target.value)}
            rows={3}
            autoFocus
            placeholder={
              isDraftStage
                ? 'What should the crew change before re-submitting?'
                : 'What needs to change? The build crew will receive these notes.'
            }
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-[12px] outline-none ring-primary/40 placeholder:text-muted-foreground/50 focus:ring-2"
          />
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => {
                setReviseOpen(false)
                setReviseNotes('')
              }}
              className="rounded-md border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              Cancel
            </button>
            <button
              disabled={!reviseNotes.trim()}
              onClick={() => {
                if (isDraftStage) {
                  onReviseDraft?.(draft.id, reviseNotes.trim())
                } else {
                  onRequestChanges?.(draft.id, reviseNotes.trim())
                }
                setReviseOpen(false)
                setReviseNotes('')
              }}
              className="rounded-md bg-gradient-to-br from-amber-500 to-orange-500 px-3 py-1 text-[11px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isDraftStage ? 'Send revision' : 'Request changes'}
            </button>
          </div>
        </div>
      )}

      {/* Stepper */}
      <div className="mt-3">
        <Stepper
          currentIdx={currentIdx}
          failed={failed}
          progress={isBuildingStage || isReviewStage ? progress : 1}
        />
      </div>
    </li>
  )
}

// ── Stepper ───────────────────────────────────────────────────────────────────

function Stepper({
  currentIdx,
  failed,
  progress,
}: {
  currentIdx: number
  failed: boolean
  progress: number
}) {
  return (
    <ol className="flex items-center gap-1">
      {STAGE_ORDER.map((key, idx) => {
        const meta = STAGE[key]
        let state: 'done' | 'current' | 'pending' | 'failed' = 'pending'
        if (failed && idx === Math.max(currentIdx, 0)) state = 'failed'
        else if (idx < currentIdx) state = 'done'
        else if (idx === currentIdx) state = 'current'
        else state = 'pending'

        return (
          <li key={key} className="flex min-w-0 flex-1 items-center gap-1">
            <StepNode meta={meta} state={state} stageKey={key} />
            {idx < STAGE_ORDER.length - 1 && (
              <Connector
                filled={state === 'done'}
                active={state === 'current'}
                progress={state === 'current' ? progress : 1}
                nextStageTone={STAGE[STAGE_ORDER[idx + 1]].bg}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}

function StepNode({
  meta,
  state,
  stageKey,
}: {
  meta: (typeof STAGE)[StageKey]
  state: 'done' | 'current' | 'pending' | 'failed'
  stageKey: StageKey
}) {
  const Icon = meta.icon
  // Pipeline "pauses" at Draft and Built — waiting for human decision, not actively running.
  const isHumanGate = stageKey === 'draft' || stageKey === 'built'
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <div
        className={cn(
          'relative flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-white transition-all',
          state === 'done' && 'bg-gradient-to-br from-emerald-500 to-green-500 shadow-[0_0_0_1px_rgba(16,185,129,0.25)]',
          state === 'current' && `${meta.bg} shadow-[0_0_0_2px_rgba(255,255,255,0.06)] ${meta.tone}`,
          state === 'pending' && 'border border-border bg-surface-muted/60 text-muted-foreground/50',
          state === 'failed' && 'bg-gradient-to-br from-rose-500 to-red-600',
        )}
      >
        {state === 'done' && <Check className="h-3 w-3" strokeWidth={3} />}
        {state === 'current' && isHumanGate && <Icon className="h-3 w-3" />}
        {state === 'current' && !isHumanGate && <Loader2 className="h-3 w-3 animate-spin" />}
        {state === 'pending' && <Icon className="h-2.5 w-2.5" />}
        {state === 'failed' && <X className="h-3 w-3" strokeWidth={3} />}
      </div>
      <span
        className={cn(
          'truncate text-[10px] font-medium tracking-tight',
          state === 'done' && 'text-emerald-300',
          state === 'current' && meta.tone,
          state === 'pending' && 'text-muted-foreground/60',
          state === 'failed' && 'text-rose-300',
        )}
      >
        {meta.label}
      </span>
    </div>
  )
}

function Connector({
  filled,
  active,
  progress,
}: {
  filled: boolean
  active: boolean
  progress: number
  nextStageTone: string
}) {
  return (
    <div className="relative h-[2px] flex-1 min-w-[8px] overflow-hidden rounded-full bg-border">
      <div
        className={cn(
          'h-full transition-all duration-500',
          filled && 'bg-gradient-to-r from-emerald-500 to-green-400',
          active && 'bg-gradient-to-r from-emerald-500 to-primary/80',
        )}
        style={{ width: filled ? '100%' : active ? `${progress * 100}%` : '0%' }}
      />
    </div>
  )
}

// ── Bits ──────────────────────────────────────────────────────────────────────

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
      title="Tech fit score"
      className={cn(
        'rounded-md border px-1.5 py-0.5 font-mono text-[10px] font-semibold tabular-nums',
        tone,
      )}
    >
      {pct}
    </span>
  )
}

function InlineMetric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  tone: 'info' | 'warn' | 'success' | 'danger'
}) {
  const toneCls = {
    info: 'border-cyan-500/30 bg-cyan-500/5 text-cyan-200',
    warn: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
    success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
    danger: 'border-rose-500/30 bg-rose-500/10 text-rose-200',
  }[tone]
  return (
    <div
      className={cn(
        'flex items-center gap-1 rounded-md border px-1.5 py-1 font-mono text-[10px]',
        toneCls,
      )}
    >
      <Icon className="h-3 w-3" />
      <span className="uppercase tracking-wider opacity-80">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </div>
  )
}

function DetailBlock({
  icon: Icon,
  label,
  tone,
  value,
  wide = false,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  tone: string
  value: string
  wide?: boolean
}) {
  return (
    <div className={cn('flex items-start gap-2', wide && 'md:col-span-2')}>
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

function LegendChip({
  stage,
  count,
}: {
  stage: StageKey | 'failed'
  count: number
}) {
  if (stage === 'failed') {
    return (
      <div className="flex items-center gap-1 text-[10px]">
        <span className="h-1.5 w-1.5 rounded-full bg-gradient-to-br from-rose-600 to-red-600" />
        <span className="text-muted-foreground/70">Failed</span>
        <span className="font-mono font-semibold tabular-nums text-rose-300">
          {count}
        </span>
      </div>
    )
  }
  const meta = STAGE[stage]
  return (
    <div className="flex items-center gap-1 text-[10px]">
      <span className={cn('h-1.5 w-1.5 rounded-full', meta.bg)} />
      <span className="text-muted-foreground/70">{meta.label}</span>
      <span className={cn('font-mono font-semibold tabular-nums', meta.tone)}>
        {count}
      </span>
    </div>
  )
}

function countByStage(queue: Draft[]) {
  const out: Record<string, number> = {
    draft: 0,
    queued: 0,
    building: 0,
    review: 0,
    built: 0,
    deploying: 0,
    deployed: 0,
    failed: 0,
  }
  for (const d of queue) {
    const s = d.status
    if (s === 'pending') out.draft++
    else if (s === 'queued' || s === 'approved') out.queued++
    else if (s === 'building') out.building++
    else if (s === 'review') out.review++
    else if (s === 'built' || s === 'testing') out.built++
    else if (s === 'pending_deploy' || s === 'deploying') out.deploying++
    else if (s === 'deployed') out.deployed++
    else if (s === 'failed' || s === 'rejected_deploy') out.failed++
  }
  return out
}

function EmptyQueue() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border/60 py-10 text-center">
      <Layers3 className="h-5 w-5 text-muted-foreground" />
      <p className="text-sm font-medium">Pipeline is idle</p>
      <p className="max-w-[300px] text-[11px] text-muted-foreground">
        New drafts will appear here at the Draft stage for your approval, then flow through the build pipeline end-to-end.
      </p>
    </div>
  )
}
