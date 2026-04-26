import { ArrowDown, Terminal } from 'lucide-react'

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background layers */}
      <div className="absolute inset-0 grid-bg" />
      <div className="absolute inset-0 noise" />

      {/* Radial glows */}
      <div className="absolute top-1/4 left-1/4 w-[800px] h-[800px] rounded-full bg-brand-500/[0.07] blur-[120px]" />
      <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] rounded-full bg-accent-cyan/[0.04] blur-[100px]" />

      {/* Terminal-style top bar */}
      <div className="absolute top-0 left-0 right-0 h-10 flex items-center px-6 border-b border-surface-600/50 bg-surface-900/80 backdrop-blur-sm">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-accent-rose/60" />
          <div className="w-3 h-3 rounded-full bg-accent-amber/60" />
          <div className="w-3 h-3 rounded-full bg-brand-400/60" />
        </div>
        <div className="ml-4 flex items-center gap-2 text-xs font-mono text-surface-500">
          <Terminal className="w-3 h-3" />
          <span>erslabs.net</span>
          <span className="text-brand-500">~</span>
          <span className="text-surface-500/50">production</span>
        </div>
      </div>

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-10">
        {/* Logo */}
        <div className="mb-8 flex justify-center animate-fade-in">
          <div className="relative">
            <img src="/logo.svg" alt="ErsLabs" className="h-14 md:h-20 relative z-10" />
            <div className="absolute inset-0 blur-2xl bg-brand-500/20 scale-150" />
          </div>
        </div>

        {/* Status badge */}
        <div className="mb-8 inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-brand-500/20 bg-brand-500/5 animate-slide-up">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500" />
          </span>
          <span className="text-xs font-mono text-brand-300 tracking-wide">
            6 agents online &middot; scanning communities now
          </span>
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.95] mb-6 animate-slide-up">
          We build apps by
          <br />
          <span className="text-gradient">listening</span>
        </h1>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed animate-fade-in">
          An autonomous AI lab that discovers real problems people have,
          engineers targeted solutions, and ships them to production —
          all without human intervention.
        </p>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-slide-up">
          <a
            href="#pipeline"
            className="group relative px-8 py-3.5 bg-brand-500 hover:bg-brand-400 text-surface-950 font-bold rounded-lg transition-all hover:shadow-[0_0_30px_rgba(16,185,129,0.3)]"
          >
            See the pipeline
            <span className="ml-2 inline-block transition-transform group-hover:translate-x-1">&rarr;</span>
          </a>
          <a
            href="#portfolio"
            className="px-8 py-3.5 border border-surface-600 hover:border-brand-500/50 text-slate-300 hover:text-white font-medium rounded-lg transition-all"
          >
            View shipped apps
          </a>
        </div>

        {/* Terminal preview */}
        <div className="mt-16 max-w-2xl mx-auto animate-fade-in">
          <div className="rounded-xl border border-surface-600/50 bg-surface-900/80 backdrop-blur-sm overflow-hidden shadow-2xl shadow-black/50">
            <div className="px-4 py-2 border-b border-surface-700/50 flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-brand-500" />
              <span className="text-xs font-mono text-surface-500">sentinel-v2 / cycle #3</span>
            </div>
            <div className="p-4 font-mono text-[13px] leading-relaxed text-left">
              <div className="text-surface-500"># Cycle started at 08:14 UTC</div>
              <div><span className="text-brand-400">{'>'}</span> <span className="text-accent-cyan">Scout</span> found <span className="text-white">847</span> complaints across 12 subreddits</div>
              <div><span className="text-brand-400">{'>'}</span> <span className="text-accent-violet">Analyst</span> ranked top 3 by revenue potential</div>
              <div><span className="text-brand-400">{'>'}</span> <span className="text-accent-amber">Matcher</span> confirmed fit: <span className="text-brand-300">92% match</span></div>
              <div><span className="text-brand-400">{'>'}</span> <span className="text-white">Building</span> ComplianceDesk — HIPAA tracking SaaS</div>
              <div><span className="text-brand-400">{'>'}</span> <span className="text-brand-500">6 agents</span> collaborating: frontend, backend, review, security, QA</div>
              <div className="flex items-center gap-1">
                <span className="text-brand-400">{'>'}</span>
                <span className="text-brand-300">Deploying to</span>
                <span className="text-brand-400">compliancedesk.erslabs.net</span>
                <span className="w-2 h-4 bg-brand-400 cursor-blink" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <ArrowDown className="w-5 h-5 text-surface-500" />
      </div>
    </section>
  )
}
