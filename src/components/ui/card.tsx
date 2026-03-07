import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
}

export function Card({ children, className = '', title }: CardProps) {
  return (
    <div className={`card ${className}`}>
      {title && (
        <h2 className="text-xl font-bold text-white mb-4">{title}</h2>
      )}
      {children}
    </div>
  )
}
