'use client'

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

interface AgentModalProps {
  agent: Agent
  onClose: () => void
  onSave: (agent: Agent) => void
}

export default function AgentModal({ agent, onClose, onSave }: AgentModalProps) {
  const [soul, setSoul] = useState(agent.soul || '')
  const [memory, setMemory] = useState(agent.memory || '')
  const [progress, setProgress] = useState(agent.progress || '')
  const [activeTab, setActiveTab] = useState<'soul' | 'memory' | 'progress'>('soul')

  const handleSave = () => {
    const updatedAgent = {
      ...agent,
      soul,
      memory,
      progress,
    }
    onSave(updatedAgent)
  }

  const tabs = [
    { id: 'soul' as const, label: 'SOUL.md', icon: '🧠' },
    { id: 'memory' as const, label: 'MEMORY.md', icon: '💾' },
    { id: 'progress' as const, label: 'PROGRESS.md', icon: '📊' },
  ]

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="card max-w-4xl w-full max-h-[90vh] flex flex-col overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-dark-600">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              🤖 {agent.name}
            </h2>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
              <span>Model: {agent.model}</span>
              <span>Status: {agent.status}</span>
              <span>Sessions: {agent.sessions}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-primary-600 text-white'
                  : 'bg-dark-700 text-gray-400 hover:text-white'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 mt-4 overflow-auto">
          {activeTab === 'soul' && (
            <textarea
              value={soul}
              onChange={(e) => setSoul(e.target.value)}
              className="w-full h-64 bg-dark-700 text-white font-mono text-sm p-4 rounded border border-dark-600 resize-none focus:outline-none focus:border-primary-500"
              placeholder="Agent's soul and personality..."
            />
          )}
          {activeTab === 'memory' && (
            <textarea
              value={memory}
              onChange={(e) => setMemory(e.target.value)}
              className="w-full h-64 bg-dark-700 text-white font-mono text-sm p-4 rounded border border-dark-600 resize-none focus:outline-none focus:border-primary-500"
              placeholder="Agent's long-term memory..."
            />
          )}
          {activeTab === 'progress' && (
            <textarea
              value={progress}
              onChange={(e) => setProgress(e.target.value)}
              className="w-full h-64 bg-dark-700 text-white font-mono text-sm p-4 rounded border border-dark-600 resize-none focus:outline-none focus:border-primary-500"
              placeholder="Current project progress..."
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 pt-4 border-t border-dark-600">
          <button
            onClick={onClose}
            className="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="btn btn-primary flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}
