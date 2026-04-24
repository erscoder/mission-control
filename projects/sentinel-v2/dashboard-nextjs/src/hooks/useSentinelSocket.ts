'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { io, type Socket } from 'socket.io-client'
import { BACKEND_URL, WEBSOCKET_NAMESPACE } from '@/lib/config'
import type {
  AgentMessage,
  ApprovalState,
  Draft,
  DraftsState,
  FlowBreakdown,
  FlowState,
} from '@/types/sentinel'

const SOCKET_AUTH_TOKEN = 'sentinel-v2-dashboard-secret'

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected'

export interface SentinelData {
  socket: Socket | null
  status: ConnectionStatus
  flowState: FlowState | null
  approvalState: ApprovalState | null
  breakdown: FlowBreakdown | null
  messages: AgentMessage[]
  drafts: Draft[]
  buildQueue: Draft[]
  approve: () => void
  reject: () => void
  revise: (notes: string) => void
  approveDraft: (id: string) => void
  rejectDraft: (id: string) => void
  reviseDraft: (id: string, notes: string) => void
  approveDeploy: (id: string) => void
  rejectDeploy: (id: string) => void
}

export function useSentinelSocket(): SentinelData {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [flowState, setFlowState] = useState<FlowState | null>(null)
  const [approvalState, setApprovalState] = useState<ApprovalState | null>(null)
  const [breakdown, setBreakdown] = useState<FlowBreakdown | null>(null)
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [buildQueue, setBuildQueue] = useState<Draft[]>([])
  const socketRef = useRef<Socket | null>(null)

  useEffect(() => {
    const s = io(`${BACKEND_URL}${WEBSOCKET_NAMESPACE}`, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      auth: { token: SOCKET_AUTH_TOKEN },
    })
    socketRef.current = s

    s.on('connect', () => setStatus('connected'))
    s.on('disconnect', () => setStatus('disconnected'))
    s.on('connect_error', () => setStatus('disconnected'))

    s.on('state_update', (data: FlowState) => setFlowState(data))
    s.on('approval_update', (data: ApprovalState) => setApprovalState(data))
    s.on('flow_breakdown_update', (data: FlowBreakdown) => setBreakdown(data))
    s.on('agent_messages', (data: AgentMessage[]) =>
      setMessages(Array.isArray(data) ? data : []),
    )
    s.on('drafts_update', (data: DraftsState) => {
      setDrafts(Array.isArray(data?.drafts) ? data.drafts : [])
      setBuildQueue(Array.isArray(data?.build_queue) ? data.build_queue : [])
    })

    return () => {
      s.off('connect')
      s.off('disconnect')
      s.off('connect_error')
      s.off('state_update')
      s.off('approval_update')
      s.off('flow_breakdown_update')
      s.off('agent_messages')
      s.off('drafts_update')
      s.disconnect()
    }
  }, [])

  const actions = useMemo(
    () => ({
      approve: () => socketRef.current?.emit('approve'),
      reject: () => socketRef.current?.emit('reject', { revision: false }),
      revise: (notes: string) =>
        socketRef.current?.emit('reject', { revision: true, notes }),
      approveDraft: (id: string) =>
        socketRef.current?.emit('approve_draft', { id }),
      rejectDraft: (id: string) =>
        socketRef.current?.emit('reject_draft', { id, revision: false }),
      reviseDraft: (id: string, notes: string) =>
        socketRef.current?.emit('reject_draft', { id, revision: true, notes }),
      approveDeploy: (id: string) =>
        socketRef.current?.emit('approve_deploy', { id }),
      rejectDeploy: (id: string) =>
        socketRef.current?.emit('reject_deploy', { id }),
    }),
    [],
  )

  return {
    socket: socketRef.current,
    status,
    flowState,
    approvalState,
    breakdown,
    messages,
    drafts,
    buildQueue,
    ...actions,
  }
}
