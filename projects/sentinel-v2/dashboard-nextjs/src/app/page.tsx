'use client'

import { useEffect, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import { BACKEND_URL, WEBSOCKET_NAMESPACE } from '@/lib/config'
import FlowStatePanel from '@/components/FlowStatePanel'
import {
  Globe,
  BarChart2,
  User,
  Target,
  Layout,
  Monitor,
  Server,
  Code2,
  Shield,
  CheckCircle2,
  Crosshair,
  Loader2,
  CheckCircle,
  XCircle,
  Lightbulb,
} from 'lucide-react'

type FlowState = {
  cycle: number
  phase: string
  opportunity: Opportunity | null
  build_output: string | null
  match_score: number
  deployed: boolean
  updated_at: string
}

type Opportunity = {
  title: string
  icon: string
  problem: string
  solution: string
  tech_fit: number
  complexity: number
}

type ApprovalPendingItem = {
  cycle: number
  title: string
  problem: string
  solution: string
  tech_fit: number
  complexity: number
  status: string
  set_at?: string
  timeout_at?: string
}

type ApprovalState = {
  status: string
  pending: ApprovalPendingItem | Record<string, never> | null
  approved: Array<ApprovalPendingItem>
  rejected: Array<ApprovalPendingItem>
  last_action?: string | null
  last_action_at?: string | null
}

type AgentMessageStatus = 'pending' | 'running' | 'done' | 'error'

type AgentMetadata = {
  phase: string
  sub_phase: string
  files_reviewed?: number
  issues_found?: number
  status: AgentMessageStatus
}

type AgentMessage = {
  agent_id: string
  message: string
  metadata: AgentMetadata
  cycle: number
  timestamp: string
}

const AGENT_ICONS: Record<string, React.ElementType> = {
  'web-scout': Globe,
  'analyst': BarChart2,
  'profile-researcher': User,
  'matcher': Target,
  'manager': Layout,
  'frontend-dev': Monitor,
  'backend-dev': Server,
  'code-reviewer': Code2,
  'security-auditor': Shield,
  'qa-verifier': CheckCircle2,
}

const agentNames: Record<string, string> = {
  'web-scout': 'Web Scout',
  'analyst': 'Analyst',
  'profile-researcher': 'Profile Researcher',
  'matcher': 'Matcher',
  'manager': 'Build Manager',
  'frontend-dev': 'Frontend Developer',
  'backend-dev': 'Backend Developer',
  'code-reviewer': 'Code Reviewer',
  'security-auditor': 'Security Auditor',
  'qa-verifier': 'QA Verifier',
  'deployer': 'Deployment Engineer',
}

const phases = ['research', 'match', 'build', 'approve', 'deploy']

export default function DashboardPage() {
  const [socket, setSocket] = useState<Socket | null>(null)
  const [flowState, setFlowState] = useState<FlowState | null>(null)
  const [approvalState, setApprovalState] = useState<ApprovalState | null>(null)
  const [agentMessages, setAgentMessages] = useState<AgentMessage[]>([])
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const socketInstance = io(`${BACKEND_URL}${WEBSOCKET_NAMESPACE}`, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
    })

    socketInstance.on('connect', () => {
      setIsConnected(true)
    })

    socketInstance.on('disconnect', () => {
      setIsConnected(false)
    })

    socketInstance.on('state_update', (state: FlowState) => {
      setFlowState(state)
    })

    socketInstance.on('approval_update', (approval: ApprovalState) => {
      setApprovalState(approval)
    })

    socketInstance.on('agent_messages', (messages: AgentMessage[]) => {
      setAgentMessages(messages)
    })

    socketInstance.on('action_response', (response: { success: boolean; action: string }) => {
      if (response.success) {
        alert(`${response.action === 'approve' ? 'Approved' : response.action === 'reject' ? 'Rejected' : 'Revision requested'} successfully`)
      }
    })

    setSocket(socketInstance)

    return () => {
      socketInstance.disconnect()
    }
  }, [])

  const approve = () => {
    socket?.emit('approve')
  }

  const reject = () => {
    socket?.emit('reject', { revision: false })
  }

  const requestRevision = () => {
    const notes = prompt('Revision notes:')
    if (notes !== null) {
      socket?.emit('reject', { revision: true, notes })
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-600 to-purple-700 shadow-lg shadow-blue-500/20">
                <Crosshair className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold">Sentinel V2 Dashboard</h1>
                <p className="text-xs text-muted-foreground">AI Agent Workflow Visualization</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-[10px] font uppercase tracking-wider text-muted-foreground">Cycle</p>
                <p className="text-xl font-bold">{flowState?.cycle ?? '-'}</p>
              </div>
              <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs ${
                isConnected
                  ? 'bg-green-900/30 text-green-400'
                  : 'bg-red-900/30 text-red-400'
              }`}>
                <div className={`h-2 w-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
                <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
              </div>
              <div className="rounded-full border bg-muted px-4 py-2 text-xs font-semibold">
                {flowState?.phase?.toUpperCase() ?? 'Idle'}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        {/* Phase Tracker */}
        <section className="mb-6">
          <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            <span className="text-muted-foreground">§</span> Workflow Phase
          </h2>
          <div className="grid grid-cols-5 gap-2">
            {phases.map((phase, index) => {
              const isActive = flowState?.phase === phase
              const isCompleted = phase ? index < phases.indexOf(flowState?.phase ?? '') : false

              return (
                <div
                  key={phase}
                  className={`rounded-lg border p-3 text-center transition-all ${
                    isActive
                      ? 'node-active'
                      : isCompleted
                      ? 'node-completed'
                      : 'node-pending'
                  }`}
                >
                  <div className="text-xs font-medium capitalize">{phase}</div>
                </div>
              )
            })}
          </div>
        </section>

        {/* Flow State Panel — Full Width */}
        <section className="mb-6">
          <FlowStatePanel />
        </section>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Agent Chat */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <span className="text-muted-foreground">§</span> Agent Responses
              </h2>
            </div>
            <div className="rounded-xl border bg-card p-4 h-[500px] overflow-y-auto custom-scrollbar">
              {agentMessages.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground italic">
                  Waiting for agent responses...
                </div>
              ) : (
                <div className="space-y-3">
                  {agentMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      className="flex gap-3 rounded-lg border bg-card p-3 animate-slide-in"
                    >
                      <div className="flex-shrink-0">
                        {(() => {
                          const Icon = AGENT_ICONS[msg.agent_id]
                          return (
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted">
                              {Icon ? <Icon className="h-4 w-4 text-muted-foreground" /> : <div className="h-4 w-4 text-muted-foreground">{agentNames[msg.agent_id]?.[0] || '?'}</div>}
                            </div>
                          )
                        })()}
                      </div>
                      <div className="flex min-w-0 flex-1 flex-col">
                        <div className="mb-1 flex items-center gap-2">
                          <span className="text-sm font-semibold text-foreground">{agentNames[msg.agent_id] || msg.agent_id}</span>
                          <span className="text-[10px] text-muted-foreground">
                            {new Date(msg.timestamp).toLocaleTimeString()}
                          </span>
                          {msg.metadata?.status && (
                            <span className={`flex items-center gap-1 text-[10px] ${
                              msg.metadata.status === 'running' ? 'text-yellow-400' :
                              msg.metadata.status === 'done' ? 'text-green-400' :
                              msg.metadata.status === 'error' ? 'text-red-400' :
                              'text-muted-foreground'
                            }`}>
                              {msg.metadata.status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}
                              {msg.metadata.status === 'done' && <CheckCircle className="h-3 w-3" />}
                              {msg.metadata.status === 'error' && <XCircle className="h-3 w-3" />}
                              {msg.metadata.status === 'pending' && <Loader2 className="h-3 w-3" />}
                              <span className="capitalize">{msg.metadata.status}</span>
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground leading-relaxed">{msg.message}</p>
                        {msg.metadata && (
                          <div className="mt-2 flex flex-wrap items-center gap-2 rounded bg-muted/30 p-2 text-[10px] text-muted-foreground">
                            {msg.metadata.phase && (
                              <span className="rounded bg-muted px-1.5 py-0.5 font-medium">
                                {msg.metadata.phase}
                              </span>
                            )}
                            {msg.metadata.sub_phase && (
                              <span className="rounded bg-muted px-1.5 py-0.5">
                                {msg.metadata.sub_phase}
                              </span>
                            )}
                            {msg.metadata.files_reviewed !== undefined && (
                              <span>{msg.metadata.files_reviewed} files</span>
                            )}
                            {msg.metadata.issues_found !== undefined && (
                              <span>{msg.metadata.issues_found} issues</span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Approval Center */}
          <div>
            <div className="rounded-xl border bg-card p-6">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
                <span className="text-muted-foreground">§</span> Proposal Review
              </h2>
              {approvalState?.pending && approvalState.pending.status === 'pending' ? (
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted">
                      <Lightbulb className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold text-foreground">
                        {approvalState.pending.title}
                      </h3>
                      <p className="text-xs text-muted-foreground mt-1">
                        {approvalState.pending.problem}
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded bg-muted/50 p-2">
                      <span className="text-[10px] font uppercase text-muted-foreground">Tech Fit</span>
                      <div className="flex items-center gap-2">
                        <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-blue-500 transition-all"
                            style={{ width: `${(approvalState.pending.tech_fit * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <p className="font-semibold text-foreground text-xs">
                          {(approvalState.pending.tech_fit * 100).toFixed(0)}%
                        </p>
                      </div>
                    </div>
                    <div className="rounded bg-muted/50 p-2">
                      <span className="text-[10px] font uppercase text-muted-foreground">Complexity</span>
                      <p className="font-semibold text-foreground">
                        {approvalState.pending.complexity}/5
                      </p>
                    </div>
                  </div>
                  <div className="rounded bg-muted/50 p-3 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">Solution:</span>
                    <p className="mt-1">{approvalState.pending.solution}</p>
                  </div>
                  <div className="space-y-2 pt-2">
                    <button
                      onClick={approve}
                      className="w-full rounded-lg bg-green-600 py-2.5 text-sm font-semibold text-white hover:bg-green-700 transition-colors"
                    >
                      Approve Proposal
                    </button>
                    <button
                      onClick={reject}
                      className="w-full rounded-lg bg-red-600 py-2.5 text-sm font-semibold text-white hover:bg-red-700 transition-colors"
                    >
                      Reject Proposal
                    </button>
                    <button
                      onClick={requestRevision}
                      className="w-full rounded-lg bg-yellow-600 py-2.5 text-sm font-semibold text-white hover:bg-yellow-700 transition-colors"
                    >
                      Request Revision
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex h-40 items-center justify-center text-sm text-muted-foreground italic">
                  No proposal pending review...
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
