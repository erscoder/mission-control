export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer id="cta" className="py-12 border-t border-space-700/50 relative">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo */}
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-swarm-400/20 flex items-center justify-center">
              <span className="text-swarm-400 font-mono text-sm font-bold">S</span>
            </div>
            <span className="font-mono text-swarm-300 font-medium">SENTINEL</span>
          </div>

          {/* Links */}
          <nav className="flex items-center gap-8 text-sm text-slate-500 font-mono">
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

          {/* Copyright */}
          <p className="text-xs font-mono text-slate-600">
            &copy; {year} ErsLabs
          </p>
        </div>
      </div>
    </footer>
  )
}