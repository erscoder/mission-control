import { useState, createContext, useContext, ReactNode, useEffect } from 'react'

interface WebSocketContextType {
  isConnected: boolean
  messages: any[]
  sendMessage: (message: any) => void
  gatewayToken: string
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

interface WebSocketProviderProps {
  children: ReactNode
  token?: string
}

const DEFAULT_TOKEN = '0a89ee11390e477248cf3db7774279d89d4df35fcae28ccd714921d80c2af1ae'

export function WebSocketProvider({ children, token = DEFAULT_TOKEN }: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState<any[]>([])
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const MAX_RETRIES = 5
  const RETRY_DELAY = 3000

  useEffect(() => {
    let wsInstance: WebSocket | null = null
    let retryTimeout: NodeJS.Timeout | null = null

    const connect = () => {
      try {
        const wsUrl = `ws://localhost:18789/ws?token=${token}`
        console.log('Connecting to WebSocket:', wsUrl)

        wsInstance = new WebSocket(wsUrl)

        wsInstance.onopen = () => {
          console.log('WebSocket connected')
          setIsConnected(true)
          setRetryCount(0)
        }

        wsInstance.onclose = (event) => {
          console.log('WebSocket disconnected', event.code, event.reason)
          setIsConnected(false)

          if (retryCount < MAX_RETRIES) {
            console.log(`Retrying connection... (${retryCount + 1}/${MAX_RETRIES})`)
            retryTimeout = setTimeout(() => {
              setRetryCount((prev) => prev + 1)
              connect()
            }, RETRY_DELAY)
          } else {
            console.error('Max retries reached, giving up')
          }
        }

        wsInstance.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        wsInstance.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            setMessages((prev) => [...prev.slice(-99), data]) // Keep last 100 messages
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }

        setWs(wsInstance)
      } catch (error) {
        console.error('Failed to create WebSocket:', error)
      }
    }

    connect()

    return () => {
      if (retryTimeout) {
        clearTimeout(retryTimeout)
      }
      if (wsInstance) {
        wsInstance.close()
      }
    }
  }, [token, retryCount])

  const sendMessage = (message: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }

  return (
    <WebSocketContext.Provider 
      value={{ isConnected, messages, sendMessage, gatewayToken: token }}
    >
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)
  if (context === undefined) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }
  return context
}

export function useWebSocketConnection() {
  const { isConnected } = useWebSocket()
  return isConnected
}
