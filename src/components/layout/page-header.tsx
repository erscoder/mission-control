import { LucideIcon } from 'lucide-react'
import { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  icon?: LucideIcon
  iconColor?: string
  actions?: ReactNode
}

export default function PageHeader({ 
  title, 
  description, 
  icon: Icon,
  iconColor = 'text-primary-500',
  actions 
}: PageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div>
        <div className="flex items-center gap-3">
          {Icon && <Icon className={iconColor} />}
          <h1 className="text-3xl font-bold text-white">{title}</h1>
        </div>
        {description && (
          <p className="text-gray-400 mt-1">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex gap-2">
          {actions}
        </div>
      )}
    </div>
  )
}
