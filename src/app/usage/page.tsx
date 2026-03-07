'use client'

import { BarChart3, DollarSign, TrendingUp, PieChart } from 'lucide-react'
import { Metric, Card } from '@/components/ui'
import { PageHeader } from '@/components/layout'

interface UsageData {
  model: string
  tokens: number
  cost: number
  percentage: number
}

export default function UsagePage() {
  const [usageData] = useState<UsageData[]>([
    { model: 'asi1/asi1', tokens: 145000, cost: 4.35, percentage: 65 },
    { model: 'kimi-coding', tokens: 58000, cost: 2.90, percentage: 26 },
    { model: 'claude-sonnet-4', tokens: 12000, cost: 0.72, percentage: 5 },
    { model: 'claude-haiku-4', tokens: 8000, cost: 0.16, percentage: 4 },
  ])

  const totalTokens = usageData.reduce((sum, item) => sum + item.tokens, 0)
  const totalCost = usageData.reduce((sum, item) => sum + item.cost, 0)
  const avgCostPer1K = totalCost / (totalTokens / 1000)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Usage Dashboard"
        description="Track token usage and costs across all agents"
        icon={BarChart3}
      />

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Metric
          title="Total Tokens"
          value={totalTokens.toLocaleString()}
          change="This month"
          icon={DollarSign}
          trend="neutral"
        />
        <Metric
          title="Total Cost"
          value={`$${totalCost.toFixed(2)}`}
          change="This month"
          icon={TrendingUp}
          trend="neutral"
        />
        <Metric
          title="Avg Cost/1K Tokens"
          value={`$${avgCostPer1K.toFixed(3)}`}
          change="Efficiency"
          icon={PieChart}
          trend="neutral"
        />
      </div>

      {/* Usage by Model */}
      <Card title="Usage by Model">
        <div className="space-y-4">
          {usageData.map((item) => (
            <div key={item.model} className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-white font-medium">{item.model}</span>
                <div className="flex gap-4">
                  <span className="text-gray-400">{item.tokens.toLocaleString()} tokens</span>
                  <span className="text-primary-400">${item.cost.toFixed(2)}</span>
                </div>
              </div>
              <div className="w-full bg-dark-700 rounded-full h-2">
                <div
                  className="bg-primary-500 h-2 rounded-full transition-all"
                  style={{ width: `${item.percentage}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Usage Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card title="Daily Usage">
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Daily usage chart - Recharts component</p>
          </div>
        </Card>

        <Card title="Cost Distribution">
          <div className="h-64 flex items-center justify-center text-gray-500">
            <p>Cost pie chart - Recharts component</p>
          </div>
        </Card>
      </div>

      {/* Agent Breakdown */}
      <Card title="Usage by Agent">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-400 text-sm border-b border-dark-600">
                <th className="pb-3">Agent</th>
                <th className="pb-3">Model</th>
                <th className="pb-3">Tokens</th>
                <th className="pb-3">Cost</th>
                <th className="pb-3">% of Total</th>
              </tr>
            </thead>
            <tbody className="text-sm">
              <tr className="border-b border-dark-700">
                <td className="py-3 text-white">Harvis</td>
                <td className="py-3 text-gray-400">asi1/asi1</td>
                <td className="py-3 text-white">45,000</td>
                <td className="py-3 text-primary-400">$1.35</td>
                <td className="py-3 text-gray-400">20%</td>
              </tr>
              <tr className="border-b border-dark-700">
                <td className="py-3 text-white">Codex</td>
                <td className="py-3 text-gray-400">asi1/asi1</td>
                <td className="py-3 text-white">85,000</td>
                <td className="py-3 text-primary-400">$2.55</td>
                <td className="py-3 text-gray-400">38%</td>
              </tr>
              <tr className="border-b border-dark-700">
                <td className="py-3 text-white">Luna</td>
                <td className="py-3 text-gray-400">kimi-coding</td>
                <td className="py-3 text-white">58,000</td>
                <td className="py-3 text-primary-400">$2.90</td>
                <td className="py-3 text-gray-400">26%</td>
              </tr>
              <tr>
                <td className="py-3 text-white">Vector</td>
                <td className="py-3 text-gray-400">claude-sonnet-4</td>
                <td className="py-3 text-white">12,000</td>
                <td className="py-3 text-primary-400">$0.72</td>
                <td className="py-3 text-gray-400">5%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
