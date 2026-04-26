export function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="py-12 border-t border-surface-700">
      <div className="max-w-6xl mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <img src="/favicon.svg" alt="ErsLabs" className="w-8 h-8" />
            <span className="font-semibold text-slate-300">ErsLabs</span>
          </div>

          {/* Links */}
          <nav className="flex items-center gap-8 text-sm text-slate-400">
            <a href="#how-it-works" className="hover:text-white transition-colors">
              How It Works
            </a>
            <a href="#portfolio" className="hover:text-white transition-colors">
              Portfolio
            </a>
            <a href="#about" className="hover:text-white transition-colors">
              About
            </a>
          </nav>

          {/* Copyright */}
          <p className="text-sm text-slate-500">
            &copy; {year} ErsLabs. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  )
}
