'use client'

import {
  Building2,
  Bot,
  Activity,
  Clock,
  FileText,
} from 'lucide-react'

type Panel = 'company' | 'agents' | 'usage' | 'cron' | 'docs'

interface NavRailProps {
  activePanel: Panel
  onPanelChange: (panel: Panel) => void
}

const panels = [
  { id: 'company' as Panel, label: 'Company', icon: Building2 },
  { id: 'agents' as Panel, label: 'Agents', icon: Bot },
  { id: 'usage' as Panel, label: 'Usage', icon: Activity },
  { id: 'cron' as Panel, label: 'Cron', icon: Clock },
  { id: 'docs' as Panel, label: 'Docs', icon: FileText },
]

export default function NavRail({ activePanel, onPanelChange }: NavRailProps) {
  return (
    <nav className="w-20 bg-dark-800 border-r border-dark-600 flex flex-col items-center py-4 gap-2">
      {panels.map((panel) => {
        const Icon = panel.icon
        const isActive = activePanel === panel.id

        return (
          <button
            key={panel.id}
            onClick={() => onPanelChange(panel.id)}
            className={`
              w-12 h-12 rounded-lg flex items-center justify-center transition-all
              ${isActive ? 'bg-primary-600 text-white' : 'text-gray-400 hover:bg-dark-700'}
            `}
            title={panel.label}
          >
            <Icon size={24} />
          </button>
        )
      })}
    </nav>
  )
}
