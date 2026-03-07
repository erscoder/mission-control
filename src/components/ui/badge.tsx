import { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?: 'success' | 'error' | 'warning' | 'info'
  size?: 'sm' | 'md'
}

export function Badge({ children, variant = 'info', size = 'md' }: BadgeProps) {
  const variantStyles = {
    success: 'bg-green-900/30 text-green-400',
    error: 'bg-red-900/30 text-red-400',
    warning: 'bg-yellow-900/30 text-yellow-400',
    info: 'bg-blue-900/30 text-blue-400',
  }

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  }

  return (
    <span className={`inline-flex items-center rounded-full ${variantStyles[variant]} ${sizeStyles[size]}`}>
      {children}
    </span>
  )
}
