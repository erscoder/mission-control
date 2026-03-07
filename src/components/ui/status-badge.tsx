import { CheckCircle, Clock, XCircle, LucideIcon } from 'lucide-react'

export type StatusType = 'active' | 'idle' | 'error' | 'paused'

interface StatusBadgeProps {
  status: StatusType
  icon?: boolean
}

export function StatusBadge({ status, icon = true }: StatusBadgeProps) {
  const config = {
    active: {
      Icon: CheckCircle,
      badge: 'bg-green-900/30 text-green-400',
      label: 'ACTIVE',
    },
    idle: {
      Icon: Clock,
      badge: 'bg-yellow-900/30 text-yellow-400',
      label: 'IDLE',
    },
    error: {
      Icon: XCircle,
      badge: 'bg-red-900/30 text-red-400',
      label: 'ERROR',
    },
    paused: {
      Icon: Clock,
      badge: 'bg-yellow-900/30 text-yellow-400',
      label: 'PAUSED',
    },
  }

  const { Icon, badge, label } = config[status]

  return (
    <div className="flex items-center gap-2">
      {icon && <Icon size={20} className={badge.replace('bg-', 'text-')} />}
      <span className={`text-xs px-2 py-0.5 rounded-full ${badge}`}>
        {label}
      </span>
    </div>
  )
}

export function getStatusColor(status: StatusType): string {
  const colors = {
    active: 'bg-green-900/30 text-green-400',
    idle: 'bg-yellow-900/30 text-yellow-400',
    error: 'bg-red-900/30 text-red-400',
    paused: 'bg-yellow-900/30 text-yellow-400',
  }
  return colors[status]
}
