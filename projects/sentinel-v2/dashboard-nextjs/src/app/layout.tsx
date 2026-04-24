import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sentinel — Agent Command Center',
  description: 'Real-time autonomous agent swarm. Research → Match → Build → Approve → Deploy.',
  icons: { icon: '/icon.svg' },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  )
}
