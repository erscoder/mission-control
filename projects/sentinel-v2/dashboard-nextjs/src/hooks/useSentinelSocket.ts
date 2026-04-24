'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { io, type Socket } from 'socket.io-client'
import { BACKEND_URL, WEBSOCKET_NAMESPACE } from '@/lib/config'
import type {
  AgentMessage,
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
  breakdown: FlowBreakdown | null
  messages: AgentMessage[]
  drafts: Draft[]
  buildQueue: Draft[]
  approveDraft: (id: string) => void
  rejectDraft: (id: string) => void
  reviseDraft: (id: string, notes: string) => void
  retryDraft: (id: string) => void
  approveDeploy: (id: string) => void
  rejectDeploy: (id: string) => void
}

export function useSentinelSocket(): SentinelData {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const [flowState, setFlowState] = useState<FlowState | null>(null)
  const [breakdown, setBreakdown] = useState<FlowBreakdown | null>(null)
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [buildQueue, setBuildQueue] = useState<Draft[]>([])
  const socketRef = useRef<Socket | null>(null)

  // REST fallback refs so the interval can read current state without stale closures
  const draftsRef = useRef<Draft[]>([])
  const statusRef = useRef<ConnectionStatus>('connecting')

  useEffect(() => {
    const s = io(`${BACKEND_URL}${WEBSOCKET_NAMESPACE}`, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      auth: { token: SOCKET_AUTH_TOKEN },
    })
    socketRef.current = s

    s.on('connect', () => {
      setStatus('connected')
      statusRef.current = 'connected'
    })
    s.on('disconnect', () => {
      setStatus('disconnected')
      statusRef.current = 'disconnected'
    })
    s.on('connect_error', () => {
      setStatus('disconnected')
      statusRef.current = 'disconnected'
    })

    s.on('state_update', (data: FlowState) => setFlowState(data))
    s.on('flow_breakdown_update', (data: FlowBreakdown) => setBreakdown(data))
    s.on('agent_messages', (data: AgentMessage[]) =>
      setMessages(Array.isArray(data) ? data : []),
    )
    s.on('drafts_update', (data: DraftsState) => {
      const d = Array.isArray(data?.drafts) ? data.drafts : []
      const q = Array.isArray(data?.build_queue) ? data.build_queue : []
      setDrafts(d)
      setBuildQueue(q)
      draftsRef.current = d
    })

    // Poll /api/drafts every 3s as a fallback for when the socket misses the
    // initial push or Flask hasn't emitted drafts_update yet.
    const poll = setInterval(async () => {
      if (statusRef.current === 'connected' && draftsRef.current.length > 0) return
      try {
        const res = await fetch(`${BACKEND_URL}/api/drafts`)
        if (!res.ok) return
        const json: DraftsState & { build_queue?: Draft[] } = await res.json()
        const d = Array.isArray(json?.drafts) ? json.drafts : []
        const q = Array.isArray(json?.build_queue) ? json.build_queue : []
        setDrafts(d)
        setBuildQueue(q)
        draftsRef.current = d
      } catch {
        // Flask not running — silent; socket will deliver when it reconnects
      }
    }, 3000)

    return () => {
      clearInterval(poll)
      s.off('connect')
      s.off('disconnect')
      s.off('connect_error')
      s.off('state_update')
      s.off('flow_breakdown_update')
      s.off('agent_messages')
      s.off('drafts_update')
      s.disconnect()
    }
  }, [])

  const actions = useMemo(
    () => ({
      approveDraft: (id: string) =>
        socketRef.current?.emit('approve_draft', { id }),
      rejectDraft: (id: string) =>
        socketRef.current?.emit('reject_draft', { id, revision: false }),
      reviseDraft: (id: string, notes: string) =>
        socketRef.current?.emit('reject_draft', { id, revision: true, notes }),
      retryDraft: (id: string) =>
        socketRef.current?.emit('retry_draft', { id }),
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
    breakdown,
    messages,
    drafts,
    buildQueue,
    ...actions,
  }
}
