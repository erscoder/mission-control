import {
  Radar,
  Target,
  Code2,
  Rocket,
  ListChecks,
  ShieldAlert,
  MessageSquare,
  ChevronRight,
} from 'lucide-react'

// Mirrors src/sentinel_v2/crews/* in the Sentinel V2 codebase.
// 7 crews, 17 agents in total.
const crews = [
  {
    key: 'research',
    name: 'Research',
    count: 2,
    agents: ['Demand Hunter', 'Commercial Validator'],
    description:
      'Finds real, monetizable pain points where people are already paying for bad solutions or loudly asking for better ones, with concrete evidence not speculation.',
    icon: Radar,
    color: 'from-accent-cyan to-brand-400',
    badge: 'bg-accent-cyan/10 text-accent-cyan',
    phase: 'RESEARCH',
  },
  {
    key: 'match',
    name: 'Match',
    count: 2,
    agents: ['Customer Intelligence Analyst', 'Opportunity Qualifier'],
    description:
      'Sharpens the ICP and makes a crisp Go / Modify / Kill decision on each opportunity using evidence, not enthusiasm.',
    icon: Target,
    color: 'from-accent-amber to-brand-400',
    badge: 'bg-accent-amber/10 text-accent-amber',
    phase: 'MATCH',
  },
  {
    key: 'build',
    name: 'Build',
    count: 6,
    agents: [
      'Strategic Product Manager',
      'Senior Frontend Engineer',
      'Senior Backend Engineer',
      'Senior Code Reviewer',
      'Security Engineer',
      'QA Engineering Lead',
    ],
    description:
      'Ships a revenue-ready Next.js + Stripe MVP in 1-2 weeks. PM cuts everything off the path to paid conversion; engineers, reviewer, security and QA enforce the gates that matter.',
    icon: Code2,
    color: 'from-brand-400 to-brand-600',
    badge: 'bg-brand-500/10 text-brand-400',
    phase: 'BUILD',
  },
  {
    key: 'deploy',
    name: 'Deploy',
    count: 2,
    agents: ['Deployment Engineer', 'Production QA Verifier'],
    description:
      'Backend to fly.io, frontend to Cloudflare Pages under <slug>.erslabs.net. Then proves the product actually works for a paying customer on the live URL, not just /health.',
    icon: Rocket,
    color: 'from-brand-300 to-accent-cyan',
    badge: 'bg-brand-300/10 text-brand-300',
    phase: 'DEPLOY',
  },
  {
    key: 'portfolio',
    name: 'Portfolio',
    count: 1,
    agents: ['Portfolio Maintainer'],
    description:
      'Keeps the ErsLabs portfolio current by adding each newly validated and shipped app to the public portfolio.json data file.',
    icon: ListChecks,
    color: 'from-accent-violet to-brand-400',
    badge: 'bg-accent-violet/10 text-accent-violet',
    phase: 'PORTFOLIO',
  },
  {
    key: 'security',
    name: 'Security Remediation',
    count: 3,
    agents: [
      'Dependency Vulnerability Scanner',
      'Security Remediation Planner',
      'Dependency Refactor Developer',
    ],
    description:
      'osv-scanner produces a merged vuln report; planner turns it into a per-package action plan; refactor developer applies fixes until the build and tests pass with zero known vulns.',
    icon: ShieldAlert,
    color: 'from-accent-rose to-accent-violet',
    badge: 'bg-accent-rose/10 text-accent-rose',
    phase: 'SECURITY',
  },
  {
    key: 'social',
    name: 'Social Response',
    count: 1,
    agents: ['Social Response Specialist'],
    description:
      'Composes helpful, genuine community responses that share the new solution back to the source threads, without sounding spammy or promotional.',
    icon: MessageSquare,
    color: 'from-brand-300 to-accent-amber',
    badge: 'bg-brand-300/10 text-brand-300',
    phase: 'SOCIAL',
  },
]

const phases = [
  { name: 'RESEARCH', label: 'Discover', color: 'text-accent-cyan' },
  { name: 'MATCH', label: 'Validate', color: 'text-accent-amber' },
  { name: 'BUILD', label: 'Engineer', color: 'text-brand-400' },
  { name: 'DEPLOY', label: 'Ship', color: 'text-brand-300' },
  { name: 'PORTFOLIO', label: 'Showcase', color: 'text-accent-violet' },
  { name: 'SECURITY', label: 'Harden', color: 'text-accent-rose' },
  { name: 'SOCIAL', label: 'Respond', color: 'text-brand-300' },
]

export function Pipeline() {
  const totalAgents = crews.reduce((acc, c) => acc + c.count, 0)

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
            <span className="text-gradient">{totalAgents} agents</span>, {crews.length} crews
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-lg">
            Specialist CrewAI agents working in sequence, from discovering a real
            complaint to deploying a paying product and responding back to the
            community that voiced it.
          </p>
        </div>

        {/* Phase indicators */}
        <div className="flex items-center justify-center gap-2 mb-16 font-mono text-xs flex-wrap">
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

        {/* Crew grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {crews.map((crew) => (
            <div
              key={crew.key}
              className="group relative p-6 rounded-xl border border-surface-600/50 bg-surface-900/60 backdrop-blur-sm card-shine hover:border-brand-500/30 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.5)]"
            >
              {/* Phase badge + agent count */}
              <div className="flex items-center justify-between mb-4">
                <span className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold tracking-wider ${crew.badge}`}>
                  {crew.phase}
                </span>
                <span className="font-mono text-[11px] text-surface-500">
                  {crew.count} {crew.count === 1 ? 'agent' : 'agents'}
                </span>
              </div>

              {/* Icon + Name */}
              <div className="flex items-center gap-4 mb-4">
                <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${crew.color} p-[1px]`}>
                  <div className="w-full h-full rounded-xl bg-surface-900 flex items-center justify-center">
                    <crew.icon className="w-5 h-5 text-white" />
                  </div>
                </div>
                <div>
                  <h3 className="text-lg font-bold tracking-tight">{crew.name}</h3>
                  <p className="text-sm text-slate-400 font-mono">{crew.key}_crew</p>
                </div>
              </div>

              {/* Description */}
              <p className="text-sm text-slate-400 leading-relaxed mb-4">
                {crew.description}
              </p>

              {/* Agents in crew */}
              <ul className="space-y-1 border-t border-surface-700/40 pt-3">
                {crew.agents.map((a) => (
                  <li key={a} className="flex items-center gap-2 text-[11px] font-mono text-surface-500">
                    <span className="w-1 h-1 rounded-full bg-brand-500/60" />
                    {a}
                  </li>
                ))}
              </ul>

              {/* Bottom glow on hover */}
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-brand-500/0 to-transparent group-hover:via-brand-500/50 transition-all duration-500" />
            </div>
          ))}
        </div>

        {/* Pipeline connector */}
        <div className="mt-16 flex items-center justify-center gap-4 font-mono text-xs text-surface-500">
          <span>complaint heard</span>
          <div className="w-32 h-px pipeline-flow" />
          <span className="text-brand-400 font-semibold">live product shipped</span>
        </div>
      </div>
    </section>
  )
}
