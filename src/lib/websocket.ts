'use client'

import { useState, useEffect, createContext, useContext, ReactNode } from 'react'

interface WebSocketContextType {
  isConnected: boolean
  messages: any[]
  sendMessage: (message: any) => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

export function WebSocketProvider({ children }: { children: ReactNode }) {
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
        wsInstance = new WebSocket('ws://localhost:18789/ws?token=0a89ee11390e477248cf3db7774279d89d4df35fcae28ccd714921d80c2af1ae')

        wsInstance.onopen = () => {
          console.log('WebSocket connected')
          setIsConnected(true)
          setRetryCount(0)
        }

        wsInstance.onclose = () => {
          console.log('WebSocket disconnected')
          setIsConnected(false)

          if (retryCount < MAX_RETRIES) {
            console.log(`Retrying connection... (${retryCount + 1}/${MAX_RETRIES})`)
            retryTimeout = setTimeout(() => {
              setRetryCount(prev => prev + 1)
              connect()
            }, RETRY_DELAY)
          }
        }

        wsInstance.onerror = (error) => {
          console.error('WebSocket error:', error)
        }

        wsInstance.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            setMessages(prev => [...prev.slice(-49), data])
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
  }, [retryCount])

  const sendMessage = (message: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message))
    } else {
      console.warn('WebSocket is not connected')
    }
  }

  return (
    <WebSocketContext.Provider value={{ isConnected, messages, sendMessage }}>
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
