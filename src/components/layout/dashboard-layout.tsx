import { ReactNode } from 'react'
import { NavRail } from './nav-rail'

interface DashboardLayoutProps {
  children: ReactNode
  activePanel?: string
  onPanelChange?: (panel: string) => void
}

export default function DashboardLayout({ 
  children, 
  activePanel = 'company',
  onPanelChange 
}: DashboardLayoutProps) {
  return (
    <div className="flex h-screen">
      <NavRail 
        activePanel={activePanel} 
        onPanelChange={onPanelChange || (() => {})} 
      />
      <main className="flex-1 overflow-auto p-6">
        {children}
      </main>
    </div>
  )
}
