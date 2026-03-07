import { ReactNode } from 'react'
import { useWebSocketConnection } from '@/lib/websocket-provider'

interface ConnectionStatusProps {
  label?: string
  showLabel?: boolean
}

export function ConnectionStatus({ label = 'Connection', showLabel = false }: ConnectionStatusProps) {
  const isConnected = useWebSocketConnection()

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
      isConnected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
    }`}>
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
      {showLabel && (
        <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
      )}
    </div>
  )
}
