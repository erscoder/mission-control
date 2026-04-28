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
          ? 'bg-space-950/80 backdrop-blur-md border-b border-swarm-900/50'
          : 'bg-transparent border-b border-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" aria-label="Sentinel" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-swarm-400/20 flex items-center justify-center swarm-pulse">
            <span className="text-swarm-400 font-mono text-sm font-bold">S</span>
          </div>
          <span className="font-mono text-swarm-300 font-medium">SENTINEL</span>
        </a>

        <nav className="hidden md:flex items-center gap-8 text-sm font-mono text-slate-400">
          <a href="#pipeline" className="hover:text-swarm-400 transition-colors">
            Pipeline
          </a>
          <a href="#portfolio" className="hover:text-swarm-400 transition-colors">
            Portfolio
          </a>
          <a href="#about" className="hover:text-swarm-400 transition-colors">
            About
          </a>
        </nav>

        <a
          href="#cta"
          className="hidden md:flex items-center gap-2 px-4 py-2 bg-swarm-400/10 border border-swarm-400/30 rounded-lg text-swarm-400 text-sm font-mono hover:bg-swarm-400/20 transition-colors"
        >
          Launch
        </a>
      </div>
    </header>
  )
}