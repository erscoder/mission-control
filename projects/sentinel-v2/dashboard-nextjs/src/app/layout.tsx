import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sentinel V2 Dashboard',
  description: 'Real-time AI agent workflow visualization',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}
