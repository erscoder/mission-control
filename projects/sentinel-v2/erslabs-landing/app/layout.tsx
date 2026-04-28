import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  metadataBase: new URL('https://erslabs.net'),
  title: 'ErsLabs: We build apps by listening to real problems',
  description: 'ErsLabs is an AI-powered lab that discovers real problems people have and builds solutions that actually work.',
  openGraph: {
    title: 'ErsLabs: AI-Powered Solutions Lab',
    description: 'We build apps by listening to real problems.',
    images: ['/og-image.svg'],
    type: 'website',
    url: 'https://erslabs.net',
  },
  icons: {
    icon: '/favicon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  )
}
