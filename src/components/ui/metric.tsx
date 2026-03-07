import { LucideIcon } from 'lucide-react'

interface MetricProps {
  title: string
  value: string | number
  change?: string
  icon: LucideIcon
  trend?: 'up' | 'down' | 'neutral'
}

export function Metric({ title, value, change, icon: Icon, trend }: MetricProps) {
  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <div className="text-gray-400 text-sm">{title}</div>
        <Icon className="w-5 h-5 text-gray-500" />
      </div>
      <div className="text-3xl font-bold text-white mb-2">{value}</div>
      {change && (
        <div className={`text-sm ${
          trend === 'up' ? 'text-green-500' : 
          trend === 'down' ? 'text-red-500' : 
          'text-gray-500'
        }`}>
          {change}
        </div>
      )}
    </Card>
  )
}
