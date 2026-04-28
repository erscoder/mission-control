import { ArrowDown, Terminal } from 'lucide-react'

const PIPELINE_STEPS = [
  { label: 'RESEARCH', color: 'swarm-400' },
  { label: 'MATCH', color: 'swarm-300' },
  { label: 'BUILD', color: 'swarm-400' },
  { label: 'APPROVE', color: 'human-400' },
  { label: 'DEPLOY', color: 'terminal-green' },
]

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      {/* Background layers */}
      <div className="absolute inset-0 grid-bg" />
      <div className="absolute inset-0 noise" />

      {/* Radial glows */}
      <div className="absolute top-1/4 left-1/4 w-[800px] h-[800px] rounded-full bg-swarm-500/[0.06] blur-[120px]" />
      <div className="absolute bottom-1/4 right-1/4 w-[600px] h-[600px] rounded-full bg-swarm-400/[0.03] blur-[100px]" />

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center pt-20">
        {/* Status badge */}
        <div className="mb-8 inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-swarm-500/20 bg-swarm-500/5 animate-slide-up">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-swarm-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-swarm-500" />
          </span>
          <span className="text-xs font-mono text-swarm-300 tracking-wide">
            swarm active &middot; 17 agents online
          </span>
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl lg:text-8xl font-black tracking-tighter leading-[0.95] mb-6 animate-slide-up">
          The swarm
          <br />
          <span className="text-gradient-swarm">never sleeps</span>
        </h1>

        {/* Pipeline loop visualization */}
        <div className="flex items-center justify-center gap-1 mb-8 font-mono text-sm">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center">
              <div className={`
                px-3 py-1.5 rounded-md border transition-all
                ${i === 3 ? 'border-human-500/40 bg-human-500/10 text-human-400 human-pulse' : 'border-swarm-500/30 bg-swarm-500/5 text-swarm-300'}
              `}>
                {step.label}
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <span className="mx-1 text-swarm-700">→</span>
              )}
            </div>
          ))}
        </div>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-12 leading-relaxed animate-fade-in">
          Autonomous AI agents that scout, build, and deploy micro-businesses 24/7 — 
          you review and approve every decision.
        </p>

        {/* CTA */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-slide-up">
          <a
            href="#pipeline"
            className="group relative px-8 py-3.5 bg-swarm-500 hover:bg-swarm-400 text-space-950 font-bold rounded-lg transition-all hover:shadow-[0_0_30px_rgba(0,212,255,0.3)]"
          >
            See how it works
            <span className="ml-2 inline-block transition-transform group-hover:translate-x-1">&rarr;</span>
          </a>
          <a
            href="#portfolio"
            className="px-8 py-3.5 border border-space-700 hover:border-swarm-500/50 text-slate-300 hover:text-white font-medium rounded-lg transition-all"
          >
            View shipped apps
          </a>
        </div>

        {/* Terminal preview */}
        <div className="mt-16 max-w-2xl mx-auto animate-fade-in">
          <div className="rounded-xl border border-space-700/50 bg-space-900/80 backdrop-blur-sm overflow-hidden shadow-2xl shadow-black/50">
            <div className="px-4 py-2 border-b border-space-700/50 flex items-center gap-2">
              <Terminal className="w-3.5 h-3.5 text-swarm-500" />
              <span className="text-xs font-mono text-slate-500">sentinel-v2 / cycle #3</span>
            </div>
            <div className="p-4 font-mono text-[13px] leading-relaxed text-left">
              <div className="text-slate-500"># Cycle started at 08:14 UTC</div>
              <div><span className="text-swarm-500">{'>'}</span> <span className="text-swarm-300">Scout</span> found <span className="text-white">847</span> complaints across 12 subreddits</div>
              <div><span className="text-swarm-500">{'>'}</span> <span className="text-swarm-300">Analyst</span> ranked top 3 by revenue potential</div>
              <div><span className="text-swarm-500">{'>'}</span> <span className="text-swarm-300">Matcher</span> confirmed fit: <span className="text-swarm-200">92% match</span></div>
              <div><span className="text-swarm-500">{'>'}</span> <span className="text-white">Building</span> ComplianceDesk: HIPAA tracking SaaS</div>
              <div><span className="text-swarm-500">{'>'}</span> <span className="text-human-400">awaiting</span> your approval &middot; 6 agents on standby</div>
              <div className="flex items-center gap-1">
                <span className="text-swarm-500">{'>'}</span>
                <span className="text-human-300">human_required:</span>
                <span className="text-human-400">review_needed</span>
                <span className="w-2 h-4 bg-swarm-400 cursor-blink" />
              </div>
            </div>
          </div>
        </div>

        {/* Approval hint */}
        <div className="mt-6 flex items-center justify-center gap-2 text-sm font-mono text-human-400/60">
          <span className="w-2 h-2 rounded-full bg-human-500 human-pulse" />
          <span>You approve everything before money is spent</span>
        </div>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <ArrowDown className="w-5 h-5 text-slate-600" />
      </div>
    </section>
  )
}