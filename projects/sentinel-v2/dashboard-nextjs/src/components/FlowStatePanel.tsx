'use client'

import { useEffect, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import { BACKEND_URL, WEBSOCKET_NAMESPACE } from '@/lib/config'
import {
  Activity,
  CheckCircle2,
  Circle,
  Clock,
  AlertTriangle,
  XCircle,
  ChevronRight,
  Loader2,
  Zap,
  Target,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

type FlowBreakdown = {
  cycle: number
  phase: string
  sub_phase: string | null
  status: string
  progress: number
  current_task: string | null
  next_task: string | null
  completed_tasks: string[]
  pending_tasks: string[]
  blockers: FlowBlocker[]
  metrics: FlowMetrics
  activities: FlowActivity[]
  opportunity_title: string | null
  match_score: number
  deployed: boolean
  updated_at: string
}

type FlowBlocker = {
  id: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
  resolved: boolean
}

type FlowMetrics = {
  coverage_percent: number
  issues_count: number
  files_changed: number
  tests_passed: number
  tests_total: number
  custom?: Record<string, unknown>
}

type FlowActivity = {
  type: string
  agent: string
  message: string
  timestamp: string
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const PHASES = ['research', 'match', 'build', 'approve', 'deploy']

const PHASE_LABELS: Record<string, string> = {
  research: '🔍 Research',
  match: '🎯 Match',
  build: '🔧 Build',
  approve: '✅ Approve',
  deploy: '🚀 Deploy',
}

const STATUS_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  idle:        { icon: <Circle className="h-3 w-3" />,           color: 'text-muted-foreground', label: 'Idle' },
  running:     { icon: <Loader2 className="h-3 w-3 animate-spin" />, color: 'text-blue-400',      label: 'Running' },
  completed:   { icon: <CheckCircle2 className="h-3 w-3" />,   color: 'text-green-400',      label: 'Completed' },
  blocked:     { icon: <AlertTriangle className="h-3 w-3" />,   color: 'text-red-400',        label: 'Blocked' },
  paused:      { icon: <Clock className="h-3 w-3" />,           color: 'text-yellow-400',     label: 'Paused' },
}

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  phase_start:         <Zap className="h-3 w-3 text-blue-400" />,
  phase_complete:      <CheckCircle2 className="h-3 w-3 text-green-400" />,
  awaiting_approval:   <Clock className="h-3 w-3 text-yellow-400" />,
  blocker_added:       <AlertTriangle className="h-3 w-3 text-red-400" />,
  blocker_resolved:    <CheckCircle2 className="h-3 w-3 text-green-400" />,
  metrics_update:      <Activity className="h-3 w-3 text-purple-400" />,
}

function ProgressBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground tabular-nums">{pct}%</span>
    </div>
  )
}

function PhaseBadge({ phase }: { phase: string }) {
  const idx = PHASES.indexOf(phase)
  return (
    <div className="flex items-center gap-1">
      {PHASES.slice(0, idx).map(p => (
        <span key={p} className="h-1.5 w-1.5 rounded-full bg-green-500" />
      ))}
      {phase ? (
        <span className="rounded-full bg-blue-900/50 px-2 py-0.5 text-[10px] font-semibold text-blue-300">
          {PHASE_LABELS[phase] || phase}
        </span>
      ) : null}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${cfg.color}`}>
      {cfg.icon}
      {cfg.label}
    </span>
  )
}

function BlockersList({ blockers }: { blockers: FlowBlocker[] }) {
  if (!blockers.length) return null
  return (
    <div className="space-y-1">
      {blockers.filter(b => !b.resolved).map(b => (
        <div key={b.id} className="flex items-start gap-1.5 rounded bg-red-900/20 border border-red-800/30 p-1.5 text-xs">
          <AlertTriangle className={`h-3 w-3 mt-0.5 flex-shrink-0 ${
            b.severity === 'critical' ? 'text-red-400' :
            b.severity === 'high' ? 'text-orange-400' :
            b.severity === 'medium' ? 'text-yellow-400' : 'text-zinc-400'
          }`} />
          <span className="text-muted-foreground">{b.description}</span>
        </div>
      ))}
    </div>
  )
}

function ActivityFeed({ activities }: { activities: FlowActivity[] }) {
  if (!activities.length) {
    return (
      <div className="flex h-20 items-center justify-center text-xs text-muted-foreground italic">
        No activity yet
      </div>
    )
  }
  return (
    <div className="space-y-1 max-h-40 overflow-y-auto custom-scrollbar">
      {[...activities].reverse().slice(0, 20).map((act, idx) => (
        <div key={idx} className="flex items-start gap-2 text-xs">
          <span className="mt-0.5 flex-shrink-0">
            {ACTIVITY_ICONS[act.type] || <Circle className="h-3 w-3 text-muted-foreground" />}
          </span>
          <div className="flex-1 min-w-0">
            <span className="text-muted-foreground truncate block">{act.message}</span>
            <span className="text-[10px] text-muted-foreground/60">
              {new Date(act.timestamp).toLocaleTimeString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function FlowStatePanel() {
  const [breakdown, setBreakdown] = useState<FlowBreakdown | null>(null)
  const [socket, setSocket] = useState<Socket | null>(null)

  useEffect(() => {
    const socketInstance = io(BACKEND_URL, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
    })

    socketInstance.on('flow_breakdown_update', (data: FlowBreakdown) => {
      setBreakdown(data)
    })

    socketInstance.on('connect', () => {
      // Request current breakdown
      socketInstance.emit('state_update', {}, WEBSOCKET_NAMESPACE)
    })

    setSocket(socketInstance)

    return () => {
      socketInstance.disconnect()
    }
  }, [])

  const bd = breakdown

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-blue-400" />
          <h2 className="text-sm font-semibold">Flow State</h2>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Cycle</p>
            <p className="text-lg font-bold tabular-nums">#{bd?.cycle ?? 0}</p>
          </div>
          {bd?.status && <StatusBadge status={bd.status} />}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Phase + Sub-phase + Progress */}
        {bd ? (
          <>
            {/* Phase row with progress */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold capitalize">{bd.phase}</span>
                  {bd.sub_phase && (
                    <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      {bd.sub_phase}
                    </span>
                  )}
                </div>
                <PhaseBadge phase={bd.phase} />
              </div>
              <ProgressBar value={bd.progress} />
            </div>

            {/* Opportunity + Match Score */}
            {(bd.opportunity_title || bd.match_score > 0) && (
              <div className="flex items-center gap-3 rounded bg-muted/30 p-2 text-xs">
                {bd.opportunity_title && (
                  <div className="flex items-center gap-1.5">
                    <Target className="h-3 w-3 text-purple-400" />
                    <span className="font-medium text-foreground truncate">{bd.opportunity_title}</span>
                  </div>
                )}
                {bd.match_score > 0 && (
                  <div className="ml-auto rounded bg-muted px-2 py-0.5 font-mono text-[10px]">
                    score: {bd.match_score.toFixed(2)}
                  </div>
                )}
              </div>
            )}

            {/* Tasks */}
            <div className="grid grid-cols-3 gap-2 text-xs">
              {/* Completed */}
              <div className="space-y-1">
                <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Done</p>
                <div className="space-y-0.5">
                  {bd.completed_tasks.length === 0 ? (
                    <p className="italic text-muted-foreground/60">—</p>
                  ) : (
                    bd.completed_tasks.map((t, i) => (
                      <div key={i} className="flex items-center gap-1 text-green-400">
                        <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
                        <span className="truncate">{t}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Current */}
              <div className="space-y-1">
                <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Current</p>
                {bd.current_task ? (
                  <div className="flex items-center gap-1 text-blue-400">
                    <Loader2 className="h-3 w-3 animate-spin flex-shrink-0" />
                    <span className="truncate">{bd.current_task}</span>
                  </div>
                ) : (
                  <p className="italic text-muted-foreground/60">—</p>
                )}
              </div>

              {/* Pending */}
              <div className="space-y-1">
                <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Next</p>
                <div className="space-y-0.5">
                  {bd.pending_tasks.length === 0 ? (
                    <p className="italic text-muted-foreground/60">—</p>
                  ) : (
                    bd.pending_tasks.slice(0, 3).map((t, i) => (
                      <div key={i} className="flex items-center gap-1 text-muted-foreground">
                        <ChevronRight className="h-3 w-3 flex-shrink-0" />
                        <span className="truncate">{t}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Metrics */}
            {bd.metrics && Object.keys(bd.metrics).length > 0 && (
              <div className="grid grid-cols-4 gap-2 text-center">
                {bd.metrics.coverage_percent > 0 && (
                  <div className="rounded bg-muted/50 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Coverage</p>
                    <p className="font-mono text-sm font-semibold text-green-400">
                      {bd.metrics.coverage_percent.toFixed(0)}%
                    </p>
                  </div>
                )}
                {bd.metrics.issues_count > 0 && (
                  <div className="rounded bg-muted/50 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Issues</p>
                    <p className="font-mono text-sm font-semibold text-red-400">
                      {bd.metrics.issues_count}
                    </p>
                  </div>
                )}
                {bd.metrics.files_changed > 0 && (
                  <div className="rounded bg-muted/50 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Files</p>
                    <p className="font-mono text-sm font-semibold text-blue-400">
                      {bd.metrics.files_changed}
                    </p>
                  </div>
                )}
                {bd.metrics.tests_total > 0 && (
                  <div className="rounded bg-muted/50 p-1.5">
                    <p className="text-[10px] text-muted-foreground">Tests</p>
                    <p className="font-mono text-sm font-semibold">
                      {bd.metrics.tests_passed}/{bd.metrics.tests_total}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Blockers */}
            {bd.blockers && bd.blockers.filter(b => !b.resolved).length > 0 && (
              <div className="space-y-1">
                <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Blockers</p>
                <BlockersList blockers={bd.blockers} />
              </div>
            )}

            {/* Activity Feed */}
            <div className="space-y-1">
              <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Activity Feed</p>
              <ActivityFeed activities={bd.activities} />
            </div>
          </>
        ) : (
          <div className="flex h-40 items-center justify-center text-sm text-muted-foreground italic">
            Waiting for flow state...
          </div>
        )}
      </div>
    </div>
  )
}
