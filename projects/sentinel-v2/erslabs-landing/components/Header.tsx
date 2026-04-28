'use client'

import { useEffect, useState } from 'react'

export function Header() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 inset-x-0 z-40 transition-all duration-300 ${
        scrolled
          ? 'bg-surface-950/80 backdrop-blur-md border-b border-surface-700/50'
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" aria-label="ErsLabs" className="flex items-center">
          <img src="/logo.svg" alt="ErsLabs" className="h-8 md:h-9" />
        </a>

        <nav className="hidden md:flex items-center gap-8 text-sm font-mono text-slate-400">
          <a href="#pipeline" className="hover:text-brand-400 transition-colors">
            Pipeline
          </a>
          <a href="#portfolio" className="hover:text-brand-400 transition-colors">
            Portfolio
          </a>
          <a href="#about" className="hover:text-brand-400 transition-colors">
            About
          </a>
        </nav>
      </div>
    </header>
  )
}
