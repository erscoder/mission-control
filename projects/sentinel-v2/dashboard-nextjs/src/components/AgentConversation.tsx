'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  MessageSquare,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Play,
  Pause,
  Filter,
} from 'lucide-react'
import type { AgentMessage } from '@/types/sentinel'
import { cn, formatTime } from '@/lib/utils'
import { getAgent, humanize } from '@/lib/agents'
import AgentAvatar from './AgentAvatar'

interface AgentConversationProps {
  messages: AgentMessage[]
  activeAgentId?: string | null
}

const HOOK_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  task_started: Play,
  task_completed: CheckCircle2,
  phase_started: Sparkles,
  phase_completed: CheckCircle2,
  agent_initialized: Sparkles,
  agent_output: MessageSquare,
  error: AlertTriangle,
}

const HOOK_LABEL: Record<string, string> = {
  task_started: 'Task started',
  task_completed: 'Task completed',
  phase_started: 'Phase started',
  phase_completed: 'Phase completed',
  agent_initialized: 'Agent online',
  agent_output: 'Said',
  error: 'Error',
}

const HOOK_TONE: Record<string, string> = {
  task_started: 'text-sky-300',
  task_completed: 'text-emerald-300',
  phase_started: 'text-indigo-300',
  phase_completed: 'text-emerald-300',
  agent_initialized: 'text-muted-foreground',
  agent_output: 'text-foreground',
  error: 'text-red-300',
}

export default function AgentConversation({
  messages,
  activeAgentId,
}: AgentConversationProps) {
  const [autoScroll, setAutoScroll] = useState(true)
  const [filter, setFilter] = useState<'all' | 'output'>('all')
  const scrollRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(
    () =>
      filter === 'all'
        ? messages
        : messages.filter((m) => m.hook_type === 'agent_output' || !m.hook_type),
    [messages, filter],
  )

  useEffect(() => {
    if (!autoScroll) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [filtered, autoScroll])

  const lastMessage = filtered[filtered.length - 1]
  const isTyping =
    lastMessage &&
    ['task_started', 'phase_started', 'agent_initialized'].includes(
      lastMessage.hook_type ?? '',
    )

  return (
    <section className="surface-card flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/60 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-indigo-500 to-violet-600">
            <MessageSquare className="h-3.5 w-3.5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold tracking-tight">Agent Feed</h2>
            <p className="text-[10px] text-muted-foreground">
              {filtered.length} messages · live
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setFilter(filter === 'all' ? 'output' : 'all')}
            className="flex items-center gap-1 rounded-md border border-border bg-surface-muted/60 px-2 py-1 text-[10px] font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <Filter className="h-3 w-3" />
            {filter === 'all' ? 'All' : 'Outputs'}
          </button>
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className={cn(
              'flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors',
              autoScroll
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-border bg-surface-muted/60 text-muted-foreground hover:text-foreground',
            )}
            title={autoScroll ? 'Pause auto-scroll' : 'Resume auto-scroll'}
          >
            {autoScroll ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
            {autoScroll ? 'Live' : 'Paused'}
          </button>
        </div>
      </div>

      {/* Message stream */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain px-5 py-4"
      >
        {filtered.length === 0 ? (
          <EmptyState />
        ) : (
          <ul className="flex flex-col gap-3">
            {filtered.map((msg, i) => (
              <MessageBubble key={`${msg.timestamp}-${i}`} message={msg} index={i} />
            ))}
            {isTyping && activeAgentId && <TypingBubble agentId={activeAgentId} />}
          </ul>
        )}
      </div>
    </section>
  )
}

// ── Message Bubble ────────────────────────────────────────────────────────────

function MessageBubble({ message, index }: { message: AgentMessage; index: number }) {
  const agent = getAgent(message.agent_id)
  const hook = message.hook_type ?? 'agent_output'
  const HookIcon = HOOK_ICON[hook] ?? MessageSquare
  const hookLabel = HOOK_LABEL[hook] ?? humanize(hook)
  const hookTone = HOOK_TONE[hook] ?? 'text-muted-foreground'
  const filesReviewed = (message.metadata?.files_reviewed as number | undefined) ?? undefined
  const issuesFound = (message.metadata?.issues_found as number | undefined) ?? undefined

  return (
    <li
      className="flex items-start gap-3 animate-slide-in-up"
      style={{ animationDelay: `${Math.min(index, 6) * 40}ms` }}
    >
      <AgentAvatar agentId={message.agent_id} size="sm" />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {/* Meta line */}
        <div className="flex items-center gap-2 text-[11px]">
          <span className={cn('font-semibold text-foreground', agent.accent)}>
            {agent.name}
          </span>
          <span className="flex items-center gap-1 text-muted-foreground/70">
            <HookIcon className={cn('h-3 w-3', hookTone)} />
            <span>{hookLabel}</span>
          </span>
          {message.phase && (
            <span className="rounded border border-border bg-surface-muted/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
              {message.phase}
            </span>
          )}
          <span className="ml-auto font-mono text-[10px] text-muted-foreground/50 tabular-nums">
            {formatTime(message.timestamp)}
          </span>
        </div>

        {/* Bubble */}
        <div
          className={cn(
            'rounded-2xl rounded-tl-sm border px-3.5 py-2.5 text-[13px] leading-relaxed',
            hook === 'error'
              ? 'border-red-500/30 bg-red-500/5 text-red-200'
              : hook === 'task_completed' || hook === 'phase_completed'
                ? 'border-emerald-500/20 bg-emerald-500/[0.04] text-emerald-50/90'
                : 'border-border bg-surface-muted/60 text-foreground/90',
          )}
        >
          <p className="whitespace-pre-wrap break-words">{message.message}</p>

          {(filesReviewed != null || issuesFound != null) && (
            <div className="mt-2 flex items-center gap-3 border-t border-border/60 pt-2 text-[10px] text-muted-foreground">
              {filesReviewed != null && (
                <span className="font-mono tabular-nums">
                  {filesReviewed} file{filesReviewed === 1 ? '' : 's'} reviewed
                </span>
              )}
              {issuesFound != null && (
                <span
                  className={cn(
                    'font-mono tabular-nums',
                    issuesFound > 0 ? 'text-amber-300' : 'text-emerald-300',
                  )}
                >
                  {issuesFound} issue{issuesFound === 1 ? '' : 's'}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  )
}

// ── Typing indicator ──────────────────────────────────────────────────────────

function TypingBubble({ agentId }: { agentId: string }) {
  const agent = getAgent(agentId)
  return (
    <li className="flex items-start gap-3 animate-fade-in">
      <AgentAvatar agentId={agentId} size="sm" active />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2 text-[11px]">
          <span className={cn('font-semibold', agent.accent)}>{agent.name}</span>
          <span className="text-muted-foreground/70">is thinking…</span>
        </div>
        <div className="inline-flex items-center gap-1 rounded-2xl rounded-tl-sm border border-border bg-surface-muted/60 px-4 py-3">
          <Dot delay="0ms" />
          <Dot delay="150ms" />
          <Dot delay="300ms" />
        </div>
      </div>
    </li>
  )
}

function Dot({ delay }: { delay: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-typing-dot"
      style={{ animationDelay: delay }}
    />
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-elevated">
        <MessageSquare className="h-5 w-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium text-foreground">Feed is quiet</p>
      <p className="max-w-[240px] text-[11px] text-muted-foreground">
        Waiting for the next agent to speak. The first message will arrive when
        Sentinel kicks off the research phase.
      </p>
    </div>
  )
}
