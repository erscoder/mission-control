'use client'

import { useState, useEffect } from 'react'
import {
  Building2,
  TrendingUp,
  Users,
  Activity,
  Sparkles,
} from 'lucide-react'
import { useWebSocket } from '@/lib/websocket'

interface MetricCardProps {
  title: string
  value: string | number
  change?: string
  icon: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
}

function MetricCard({ title, value, change, icon, trend }: MetricCardProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="text-gray-400 text-sm font-medium">{title}</div>
        <div className="text-gray-500">{icon}</div>
      </div>
      <div className="text-3xl font-bold text-white mb-2">{value}</div>
      {change && (
        <div className={`text-sm ${trend === 'up' ? 'text-green-500' : trend === 'down' ? 'text-red-500' : 'text-gray-500'}`}>
          {change}
        </div>
      )}
    </div>
  )
}

export default function CompanyPage() {
  const { isConnected } = useWebSocket()
  const [metrics, setMetrics] = useState({
    totalRevenue: 1250,
    monthlyGrowth: 23.5,
    activeAgents: 5,
    totalProjects: 8,
  })

  // Simulate real-time updates
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
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Sparkles className="text-primary-500" />
            Agent Software
          </h1>
          <p className="text-gray-400 mt-1">
            Autonomous AI Agents Company Dashboard
          </p>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
          isConnected ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
        }`}>
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400'}`} />
          {isConnected ? 'Connected' : 'Disconnected'}
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Revenue"
          value={`$${metrics.totalRevenue.toFixed(2)}`}
          change="+12.5% this month"
          trend="up"
          icon={<DollarSign className="w-5 h-5" />}
        />
        <MetricCard
          title="Monthly Growth"
          value={`${metrics.monthlyGrowth}%`}
          change="+3.2% vs last month"
          trend="up"
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <MetricCard
          title="Active Agents"
          value={metrics.activeAgents}
          change="All operational"
          trend="neutral"
          icon={<Users className="w-5 h-5" />}
        />
        <MetricCard
          title="Total Projects"
          value={metrics.totalProjects}
          change="2 in progress"
          trend="neutral"
          icon={<Activity className="w-5 h-5" />}
        />
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Chart */}
        <div className="card">
          <h2 className="text-xl font-bold text-white mb-4">Revenue Trend</h2>
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Revenue chart placeholder - Recharts component</p>
          </div>
        </div>

        {/* Agent Performance */}
        <div className="card">
          <h2 className="text-xl font-bold text-white mb-4">Agent Performance</h2>
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Agent performance chart - Recharts component</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="card">
        <h2 className="text-xl font-bold text-white mb-4">Quick Stats</h2>
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
      </div>
    </div>
  )
}
