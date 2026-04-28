export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="py-12 border-t border-surface-700/50 relative">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo */}
          <div className="flex items-center">
            <img src="/logo.svg" alt="ErsLabs" className="h-8" />
          </div>

          {/* Links */}
          <nav className="flex items-center gap-8 text-sm text-slate-500 font-mono">
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

          {/* Copyright */}
          <p className="text-xs font-mono text-surface-600">
            &copy; {year} ErsLabs
          </p>
        </div>
      </div>
    </footer>
  )
}
