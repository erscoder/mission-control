'use client'

import { useState } from 'react'
import NavRail from '@/components/layout/nav-rail'
import CompanyPanel from '@/components/panels/company-panel'
import AgentsPanel from '@/components/panels/agents-panel'
import UsagePanel from '@/components/panels/usage-panel'
import CronPanel from '@/components/panels/cron-panel'
import DocsPanel from '@/components/panels/docs-panel'
import { WebSocketProvider } from '@/lib/websocket'

type Panel = 'company' | 'agents' | 'usage' | 'cron' | 'docs'

export default function Home() {
  const [activePanel, setActivePanel] = useState<Panel>('company')

  const renderPanel = () => {
    switch (activePanel) {
      case 'company':
        return <CompanyPanel />
      case 'agents':
        return <AgentsPanel />
      case 'usage':
        return <UsagePanel />
      case 'cron':
        return <CronPanel />
      case 'docs':
        return <DocsPanel />
      default:
        return <CompanyPanel />
    }
  }

  return (
    <WebSocketProvider>
      <div className="flex h-screen">
        <NavRail activePanel={activePanel} onPanelChange={setActivePanel} />
        <main className="flex-1 overflow-auto p-6">
          {renderPanel()}
        </main>
      </div>
    </WebSocketProvider>
  )
}
