'use client'

import { useState } from 'react'
import { Bot, Play, Pause, Trash2 } from 'lucide-react'
import { Button, Card, getStatusColor } from '@/components/ui'
import { StatusBadge } from '@/components/ui'
import { ConnectionStatus } from '@/components/common/connection-status'
import { PageHeader } from '@/components/layout'
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
  const [agents, setAgents] = useState<Agent[]>([
    { id: 'harvis', name: 'Harvis', status: 'active', model: 'asi1/asi1', sessions: 42, lastActive: '2 min ago' },
    { id: 'codex', name: 'Codex', status: 'active', model: 'asi1/asi1', sessions: 156, lastActive: '5 min ago' },
    { id: 'luna', name: 'Luna', status: 'idle', model: 'kimi-coding', sessions: 23, lastActive: '1 hour ago' },
    { id: 'vector', name: 'Vector', status: 'active', model: 'asi1/asi1', sessions: 89, lastActive: '10 min ago' },
    { id: 'vega', name: 'Vega', status: 'error', model: 'asi1/asi1', sessions: 12, lastActive: '3 hours ago' },
  ])
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [showModal, setShowModal] = useState(false)

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
      <PageHeader
        title="Agents"
        description="Manage your AI agents and their configuration"
        icon={Bot}
        actions={<ConnectionStatus showLabel />}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <Card
            key={agent.id}
            className="cursor-pointer hover:border-primary-500 transition-colors group"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg ${getStatusColor(agent.status)} flex items-center justify-center`}>
                  <Bot size={20} />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-white">{agent.name}</h3>
                  <StatusBadge status={agent.status} icon={false} />
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={Trash2}
                onClick={(e) => {
                  e.stopPropagation()
                  handleDeleteAgent(agent.id)
                }}
                className="opacity-0 group-hover:opacity-100 hover:text-red-400"
              />
            </div>

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

            <div className="flex gap-2 mt-4">
              <Button variant="primary" size="sm" icon={Play} className="flex-1">
                Start
              </Button>
              <Button variant="secondary" size="sm" icon={Pause} className="flex-1">
                Pause
              </Button>
            </div>

            {/* Invisible click area for opening modal */}
            <div
              className="absolute inset-0 cursor-pointer"
              onClick={() => handleAgentClick(agent)}
            />
          </Card>
        ))}
      </div>

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
