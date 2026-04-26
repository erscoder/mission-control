import {
  Radar,
  BarChart3,
  UserCheck,
  Code2,
  Shield,
  Rocket,
  ChevronRight,
} from 'lucide-react'

const agents = [
  {
    name: 'Nova',
    role: 'Scout Agent',
    description: 'Scans Reddit, Twitter, HN, and 50+ forums for real pain points with evidence of willingness to pay.',
    icon: Radar,
    color: 'from-accent-cyan to-brand-400',
    ring: 'ring-accent-cyan/20',
    badge: 'bg-accent-cyan/10 text-accent-cyan',
    phase: 'RESEARCH',
  },
  {
    name: 'Atlas',
    role: 'Analyst Agent',
    description: 'Ranks opportunities by market size, competition gap, and revenue potential. Validates with real data.',
    icon: BarChart3,
    color: 'from-accent-violet to-brand-400',
    ring: 'ring-accent-violet/20',
    badge: 'bg-accent-violet/10 text-accent-violet',
    phase: 'RESEARCH',
  },
  {
    name: 'Echo',
    role: 'Match Agent',
    description: 'Matches opportunities against our tech stack and delivery capacity. Only builds what we can ship well.',
    icon: UserCheck,
    color: 'from-accent-amber to-brand-400',
    ring: 'ring-accent-amber/20',
    badge: 'bg-accent-amber/10 text-accent-amber',
    phase: 'MATCH',
  },
  {
    name: 'Forge',
    role: 'Build Crew Lead',
    description: 'Orchestrates 6 specialist sub-agents: frontend, backend, code review, security audit, and QA to ship a complete MVP.',
    icon: Code2,
    color: 'from-brand-400 to-brand-600',
    ring: 'ring-brand-400/20',
    badge: 'bg-brand-500/10 text-brand-400',
    phase: 'BUILD',
  },
  {
    name: 'Sentinel',
    role: 'Security Auditor',
    description: 'Attacker-mindset audit: OWASP Top 10, Stripe webhook verification, auth bypass, secrets leaks, dependency CVEs.',
    icon: Shield,
    color: 'from-accent-rose to-accent-violet',
    ring: 'ring-accent-rose/20',
    badge: 'bg-accent-rose/10 text-accent-rose',
    phase: 'BUILD',
  },
  {
    name: 'Hermes',
    role: 'Deploy Agent',
    description: 'Ships backend to Fly.io, frontend to Cloudflare Pages, wires Stripe webhooks, configures DNS — zero manual steps.',
    icon: Rocket,
    color: 'from-brand-300 to-accent-cyan',
    ring: 'ring-brand-300/20',
    badge: 'bg-brand-300/10 text-brand-300',
    phase: 'DEPLOY',
  },
]

const phases = [
  { name: 'RESEARCH', label: 'Discover', color: 'text-accent-cyan' },
  { name: 'MATCH', label: 'Validate', color: 'text-accent-amber' },
  { name: 'BUILD', label: 'Engineer', color: 'text-brand-400' },
  { name: 'DEPLOY', label: 'Ship', color: 'text-brand-300' },
]

export function Pipeline() {
  return (
    <section id="pipeline" className="py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-20">
          <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
            The Engine
          </p>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
            Meet the <span className="text-gradient">agents</span>
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-lg">
            Six autonomous AI agents work in sequence — from discovering a problem
            to deploying a live, paying product.
          </p>
        </div>

        {/* Phase indicators */}
        <div className="flex items-center justify-center gap-2 mb-16 font-mono text-xs">
          {phases.map((phase, i) => (
            <div key={phase.name} className="flex items-center gap-2">
              <span className={`${phase.color} font-semibold tracking-wider`}>
                {phase.label}
              </span>
              {i < phases.length - 1 && (
                <ChevronRight className="w-3 h-3 text-surface-600" />
              )}
            </div>
          ))}
        </div>

        {/* Agent grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <div
              key={agent.name}
              className={`group relative p-6 rounded-xl border border-surface-600/50 bg-surface-900/60 backdrop-blur-sm card-shine hover:border-brand-500/30 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.5)]`}
            >
              {/* Phase badge */}
              <div className="flex items-center justify-between mb-4">
                <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold tracking-wider ${agent.badge}`}>
                  {agent.phase}
                </span>
              </div>

              {/* Icon + Name */}
              <div className="flex items-center gap-4 mb-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${agent.color} p-[1px]`}>
                  <div className="w-full h-full rounded-xl bg-surface-900 flex items-center justify-center">
                    <agent.icon className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-bold tracking-tight">{agent.name}</h3>
                  <p className="text-sm text-slate-400 font-mono">{agent.role}</p>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-slate-400 leading-relaxed">
                {agent.description}
              </p>

              {/* Bottom glow on hover */}
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-brand-500/0 to-transparent group-hover:via-brand-500/50 transition-all duration-500" />
            </div>
          ))}
        </div>

        {/* Pipeline connector */}
        <div className="mt-16 flex items-center justify-center gap-4 font-mono text-xs text-surface-500">
          <span>problem discovered</span>
          <div className="w-32 h-px pipeline-flow" />
          <span className="text-brand-400 font-semibold">live product shipped</span>
        </div>
      </div>
    </section>
  )
}
