'use client'

import { useState, useEffect } from 'react'
import { Sparkles, TrendingUp, Users, Activity, DollarSign } from 'lucide-react'
import { Metric } from '@/components/ui'
import { Card } from '@/components/ui'
import { ConnectionStatus } from '@/components/common/connection-status'
import { PageHeader } from '@/components/layout'

export default function CompanyPage() {
  const [metrics, setMetrics] = useState({
    totalRevenue: 1250,
    monthlyGrowth: 23.5,
    activeAgents: 5,
    totalProjects: 8,
  })

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(prev => ({
        ...prev,
        totalRevenue: prev.totalRevenue + Math.random() * 100,
      }))
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agent Software"
        description="Autonomous AI Agents Company Dashboard"
        icon={Sparkles}
        actions={<ConnectionStatus showLabel />}
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Metric
          title="Total Revenue"
          value={`$${metrics.totalRevenue.toFixed(2)}`}
          change="+12.5% this month"
          icon={DollarSign}
          trend="up"
        />
        <Metric
          title="Monthly Growth"
          value={`${metrics.monthlyGrowth}%`}
          change="+3.2% vs last month"
          icon={TrendingUp}
          trend="up"
        />
        <Metric
          title="Active Agents"
          value={metrics.activeAgents}
          change="All operational"
          icon={Users}
          trend="neutral"
        />
        <Metric
          title="Total Projects"
          value={metrics.totalProjects}
          change="2 in progress"
          icon={Activity}
          trend="neutral"
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Revenue Trend">
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Revenue chart placeholder - Recharts component</p>
          </div>
        </Card>

        <Card title="Agent Performance">
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Agent performance chart - Recharts component</p>
          </div>
        </Card>
      </div>

      {/* Quick Stats */}
      <Card title="Quick Stats">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-dark-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Sessions Today</div>
            <div className="text-2xl font-bold text-white">247</div>
          </div>
          <div className="bg-dark-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Tasks Completed</div>
            <div className="text-2xl font-bold text-white">1,842</div>
          </div>
          <div className="bg-dark-700 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Avg Response Time</div>
            <div className="text-2xl font-bold text-white">1.2s</div>
          </div>
        </div>
      </Card>
    </div>
  )
}
