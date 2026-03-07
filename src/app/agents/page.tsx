'use client'

import { useState } from 'react'
import {
  Bot,
  Play,
  Pause,
  FileText,
  Brain,
  Trash2,
} from 'lucide-react'
import { useWebSocket } from '@/lib/websocket'
import AgentModal from '@/components/modals/agent-modal'

interface Agent {
  id: string
  name: string
  status: 'active' | 'idle' | 'error'
  model: string
  sessions: number
  lastActive: string
  soul?: string
  memory?: string
  progress?: string
}

export default function AgentsPage() {
  const { isConnected } = useWebSocket()
  const [agents, setAgents] = useState<Agent[]>([
    { id: 'harvis', name: 'Harvis', status: 'active', model: 'asi1/asi1', sessions: 42, lastActive: '2 min ago' },
    { id: 'codex', name: 'Codex', status: 'active', model: 'asi1/asi1', sessions: 156, lastActive: '5 min ago' },
    { id: 'luna', name: 'Luna', status: 'idle', model: 'kimi-coding', sessions: 23, lastActive: '1 hour ago' },
    { id: 'vector', name: 'Vector', status: 'active', model: 'asi1/asi1', sessions: 89, lastActive: '10 min ago' },
    { id: 'vega', name: 'Vega', status: 'error', model: 'asi1/asi1', sessions: 12, lastActive: '3 hours ago' },
  ])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [showModal, setShowModal] = useState(false)

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'active':
        return 'bg-green-900/30 text-green-400'
      case 'idle':
        return 'bg-yellow-900/30 text-yellow-400'
      case 'error':
        return 'bg-red-900/30 text-red-400'
      default:
        return 'bg-gray-900/30 text-gray-400'
    }
  }

  const handleAgentClick = (agent: Agent) => {
    setSelectedAgent(agent)
    setShowModal(true)
  }

  const handleSaveAgent = (updatedAgent: Agent) => {
    setAgents(prev => prev.map(agent =>
      agent.id === updatedAgent.id ? updatedAgent : agent
    ))
    setShowModal(false)
    setSelectedAgent(null)
  }

  const handleDeleteAgent = (agentId: string) => {
    if (confirm('Are you sure you want to delete this agent?')) {
      setAgents(prev => prev.filter(agent => agent.id !== agentId))
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Bot className="text-primary-500" />
            Agents
          </h1>
          <p className="text-gray-400 mt-1">
            Manage your AI agents and their configuration
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
          isConnected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
        }`}>
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      {/* Agents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="card cursor-pointer hover:border-primary-500 transition-colors group"
            onClick={() => handleAgentClick(agent)}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg ${getStatusColor(agent.status)} flex items-center justify-center`}>
                  <Bot size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">{agent.name}</h3>
                  <div className={`text-xs px-2 py-0.5 rounded-full ${getStatusColor(agent.status)}`}>
                    {agent.status.toUpperCase()}
                  </div>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteAgent(agent.id)
                }}
                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-400 transition-opacity"
              >
                <Trash2 size={18} />
              </button>
            </div>

            {/* Stats */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Model:</span>
                <span className="text-white">{agent.model}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Sessions:</span>
                <span className="text-white">{agent.sessions}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Last Active:</span>
                <span className="text-white">{agent.lastActive}</span>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2 mt-4">
              <button className="flex-1 btn btn-primary text-sm flex items-center justify-center gap-2">
                <Play size={16} />
                Start
              </button>
              <button className="flex-1 btn btn-secondary text-sm flex items-center justify-center gap-2">
                <Pause size={16} />
                Pause
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Agent Modal */}
      {showModal && selectedAgent && (
        <AgentModal
          agent={selectedAgent}
          onClose={() => setShowModal(false)}
          onSave={handleSaveAgent}
        />
      )}
    </div>
  )
}
