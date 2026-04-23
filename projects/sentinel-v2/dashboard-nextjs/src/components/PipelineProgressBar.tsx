'use client'

import { useEffect, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import { BACKEND_URL } from '@/lib/config'
import {
  Search,
  Target as TargetIcon,
  Wrench,
  CheckCircle,
  Rocket,
  ChevronRight,
  Loader2,
} from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

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
  metrics: FlowMetrics | null
  activities: FlowActivity[]
  opportunity_title: string | null
  match_score: number
  deployed: boolean
  updated_at: string
}

type PhaseType = 'research' | 'match' | 'build' | 'approve' | 'deploy'

const PHASES: PhaseType[] = ['research', 'match', 'build', 'approve', 'deploy']

const PHASE_CONFIG: Record<
  PhaseType,
  { icon: React.ComponentType<{ className?: string }>; label: string; color: string; gradient: string }
> = {
  research: {
    icon: Search,
    label: 'Research',
    color: 'from-blue-500 to-cyan-500',
    gradient: 'shadow-blue-500/40',
  },
  match: {
    icon: TargetIcon,
    label: 'Match',
    color: 'from-purple-500 to-pink-500',
    gradient: 'shadow-purple-500/40',
  },
  build: {
    icon: Wrench,
    label: 'Build',
    color: 'from-orange-500 to-amber-500',
    gradient: 'shadow-orange-500/40',
  },
  approve: {
    icon: CheckCircle,
    label: 'Approve',
    color: 'from-green-500 to-emerald-500',
    gradient: 'shadow-green-500/40',
  },
  deploy: {
    icon: Rocket,
    label: 'Deploy',
    color: 'from-indigo-500 to-violet-500',
    gradient: 'shadow-indigo-500/40',
  },
}

// ── Components ─────────────────────────────────────────────────────────────────

interface PhaseNodeProps {
  phase: PhaseType
  isActive: boolean
  isCompleted: boolean
  progress: number
  onClick?: () => void
}

function PhaseNode({ phase, isActive, isCompleted, progress, onClick }: PhaseNodeProps) {
  const config = PHASE_CONFIG[phase]
  const Icon = config.icon

  return (
    <div
      onClick={onClick}
      className="relative flex flex-col items-center flex-1 cursor-pointer group"
    >
      {/* Connection Line */}
      <div className="absolute top-5 left-1/2 w-full h-0.5 -z-10">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${
            isCompleted ? 'bg-gradient-to-r ' + config.color : 'bg-muted'
          }`}
          style={{
            width: progress ? `${progress}%` : isCompleted ? '100%' : '0%',
          }}
        />
      </div>

      {/* Icon Container */}
      <div
        className={`
          relative z-10 flex h-10 w-10 items-center justify-center
          rounded-xl border-2 transition-all duration-500
          ${isActive 
            ? `scale-110 border-transparent bg-gradient-to-br ${config.color} shadow-lg ${config.gradient} shadow-blue-500/30 animate-glow` 
            : isCompleted 
            ? `border-transparent bg-gradient-to-br ${config.color}` 
            : 'border-border bg-card'
          }
        `}
      >
        {isActive ? (
          <Loader2 className={`h-5 w-5 text-white animate-spin`} />
        ) : isCompleted ? (
          <CheckCircle className="h-5 w-5 text-white" />
        ) : (
          <Icon className="h-5 w-5 text-muted-foreground group-hover:text-foreground transition-colors" />
        )}
      </div>

      {/* Label */}
      <p
        className={`
          mt-2 text-xs font-medium transition-all duration-300 capitalize
          ${isActive ? `text-transparent bg-gradient-to-r ${config.color} bg-clip-text font-bold` : 
            isCompleted ? 'text-foreground' : 'text-muted-foreground'}
        `}
      >
        {config.label}
      </p>

      {/* Progress Indicator */}
      {isActive && progress > 0 && (
        <div className="mt-1 px-2 py-0.5 rounded-full bg-muted">
          <p className="text-[10px] font-mono text-muted-foreground">
            {Math.round(progress * 100)}%
          </p>
        </div>
      )}
    </div>
  )
}

interface CurrentTaskDisplayProps {
  phase: PhaseType | null
  currentTask: string | null
  status: string
}

function CurrentTaskDisplay({ phase, currentTask, status }: CurrentTaskDisplayProps) {
  if (!currentTask && !phase) {
    return (
      <div className="flex items-center justify-center h-16 text-sm text-muted-foreground italic">
        Waiting for workflow to start...
      </div>
    )
  }

  const config = phase ? PHASE_CONFIG[phase] : null
  const PhaseIcon = config?.icon ?? Loader2

  return (
    <div
      className={`
        rounded-xl border p-4 transition-all duration-500
        ${status === 'running' ? 'bg-blue-950/20 border-blue-800/50' : 
          status === 'completed' ? 'bg-green-950/20 border-green-800/50' : 
          'bg-card border-border'}
      `}
    >
      <div className="flex items-center gap-3">
        {/* Animated Icon */}
        <div
          className={`
            flex h-12 w-12 items-center justify-center
            rounded-xl border-2 transition-all duration-500
            ${status === 'running' 
              ? `scale-110 border-transparent bg-gradient-to-br ${config?.color} shadow-lg ${config?.gradient} animate-pulse` 
              : status === 'completed'
              ? `border-transparent bg-gradient-to-br ${config?.color}`
              : 'border-border bg-muted'
            }
          `}
        >
          {status === 'running' ? (
            <PhaseIcon className="h-6 w-6 text-white animate-spin" />
          ) : (
            <PhaseIcon className={`h-6 w-6 ${status === 'completed' ? 'text-white' : 'text-muted-foreground'}`} />
          )}
        </div>

        {/* Task Text */}
        <div className="flex-1 min-w-0">
          {phase && (
            <p
              className={`
                text-xs font-semibold uppercase tracking-wider mb-1 transition-all duration-300
                ${status === 'running' ? 'text-transparent bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text' : 'text-muted-foreground'}
              `}
            >
              {config?.label} Phase
            </p>
          )}
          <p className="text-sm font-medium text-foreground leading-tight">
            {currentTask || 'Initializing...'}
          </p>
          {status === 'running' && (
            <div className="flex items-center gap-2 mt-1">
              <div className="flex gap-0.5">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1 h-1 rounded-full bg-blue-400 animate-bounce"
                    style={{ animationDelay: `${i * 150}ms` }}
                  />
                ))}
              </div>
              <p className="text-[10px] text-muted-foreground">Processing...</p>
            </div>
          )}
        </div>

        {/* Progress Badge */}
        {status === 'completed' && (
          <div className="flex-shrink-0">
            <CheckCircle className="h-8 w-8 text-green-400" />
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

interface PipelineProgressBarProps {
  className?: string
}

export default function PipelineProgressBar({ className = '' }: PipelineProgressBarProps) {
  const [breakdown, setBreakdown] = useState<FlowBreakdown | null>(null)
  const [socket, setSocket] = useState<Socket | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')

  useEffect(() => {
    const socketInstance = io(BACKEND_URL, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
    })

    socketInstance.on('connect', () => {
      console.log('[PipelineProgressBar] Connected')
      setConnectionStatus('connected')
      // Request current flow breakdown
      socketInstance.emit('get_flow_breakdown')
    })

    socketInstance.on('disconnect', () => {
      console.log('[PipelineProgressBar] Disconnected')
      setConnectionStatus('disconnected')
    })

    socketInstance.on('flow_breakdown_update', (data: FlowBreakdown) => {
      console.log('[PipelineProgressBar] Flow breakdown update:', data)
      setBreakdown(data)
    })

    setSocket(socketInstance)

    return () => {
      socketInstance.disconnect()
    }
  }, [])

  const currentPhase = breakdown?.phase as PhaseType | null
  const currentPhaseIndex = currentPhase ? PHASES.indexOf(currentPhase) : -1

  return (
    <div className={`rounded-xl border bg-card overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className={`h-2 w-2 rounded-full ${
            connectionStatus === 'connected' ? 'bg-green-400' :
            connectionStatus === 'disconnected' ? 'bg-red-400' :
            'bg-yellow-400 animate-pulse'
          }`} />
          <h2 className="text-sm font-semibold">Workflow Pipeline</h2>
        </div>
        <div className="text-right">
          <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Cycle</p>
          <p className="text-lg font-bold tabular-nums">#{breakdown?.cycle ?? 0}</p>
        </div>
      </div>

      <div className="p-4 space-y-6">
        {/* Pipeline Phases */}
        <div className="relative">
          <div className="flex items-center justify-between">
            {PHASES.map((phase, index) => {
              const isActive = currentPhase === phase
              const isCompleted = currentPhaseIndex > -1 && index < currentPhaseIndex
              const progress = breakdown?.phase === phase ? breakdown.progress : isCompleted ? 1 : 0

              return (
                <PhaseNode
                  key={phase}
                  phase={phase}
                  isActive={isActive}
                  isCompleted={isCompleted}
                  progress={progress}
                />
              )
            })}
          </div>
        </div>

        {/* Current Task Display */}
        <CurrentTaskDisplay
          phase={currentPhase}
          currentTask={breakdown?.current_task ?? null}
          status={breakdown?.status ?? 'idle'}
        />

        {/* Sub-phase Badge */}
        {breakdown?.sub_phase && currentPhase && (
          <div className="flex justify-center">
            <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
              breakdown.status === 'running'
                ? `bg-gradient-to-r ${PHASE_CONFIG[currentPhase].color} bg-opacity-20 border-transparent`
                : 'bg-muted border-border'
            }`}>
              <Loader2 className={`
                h-3 w-3 
                ${breakdown.status === 'running' ? 'animate-spin' : ''}
              `} />
              <span className="text-[10px] font-medium capitalize">
                {breakdown.sub_phase}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
