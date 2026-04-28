import { Search, Target, Code2, UserCheck, Rocket } from 'lucide-react'

const steps = [
  {
    icon: Search,
    num: '01',
    label: 'RESEARCH',
    color: 'swarm',
    description:
      'Scout agents continuously scan Reddit, Twitter, HN, and 50+ communities. Hunter agents filter signal from noise — real pain points, not trends.',
    detail: '847 sources monitored 24/7',
  },
  {
    icon: Target,
    num: '02',
    label: 'MATCH',
    color: 'swarm',
    description:
      'Profile agent researches the target user. Matcher confirms fit: market size, competition, your skill adjacency. No gut feelings — data.',
    detail: '92% match threshold',
  },
  {
    icon: Code2,
    num: '03',
    label: 'BUILD',
    color: 'swarm',
    description:
      'Build crew ships the MVP: PM, frontend, backend, reviewer, security, QA. Full-stack, tested, Stripe wired. You stay hands-off.',
    detail: '6 specialized agents',
  },
  {
    icon: UserCheck,
    num: '04',
    label: 'APPROVE',
    color: 'human',
    description:
      'The swarm stops here. Nothing moves forward without your explicit approval. You review the business plan, the spec, the economics.',
    detail: 'you are in control',
  },
  {
    icon: Rocket,
    num: '05',
    label: 'DEPLOY',
    color: 'terminal-green',
    description:
      'Once you approve, Deploy crew launches: Fly.io backend, Cloudflare Pages frontend, custom domain, Stripe webhooks, SSL.',
    detail: 'production in < 4h',
  },
]

export function HowItWorks() {
  return (
    <section id="pipeline" className="py-24 md:py-32 bg-space-900/30 relative">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="text-center mb-20">
          <p className="text-swarm-400 font-mono text-sm tracking-wider uppercase mb-3">
            Pipeline
          </p>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight text-white">
            The loop that runs{' '}
            <span className="text-gradient-swarm">24/7</span>
          </h2>
        </div>

        <div className="space-y-6 md:space-y-0 md:grid md:grid-cols-5 md:gap-4">
          {steps.map((step, i) => (
            <div
              key={step.label}
              className={`
                relative p-5 rounded-xl border backdrop-blur-sm transition-all duration-300
                ${step.color === 'human'
                  ? 'border-human-500/30 bg-human-500/5 hover:border-human-500/50'
                  : step.color === 'terminal-green'
                  ? 'border-terminal-green/20 bg-terminal-green/5 hover:border-terminal-green/40'
                  : 'border-swarm-900/50 bg-swarm-900/20 hover:border-swarm-500/30'
                }
              `}
            >
              {/* Step number + label */}
              <div className="flex items-center gap-2 mb-4">
                <span className={`
                  font-mono text-xs px-2 py-0.5 rounded
                  ${step.color === 'human' ? 'bg-human-500/20 text-human-400' : step.color === 'terminal-green' ? 'bg-terminal-green/20 text-terminal-green' : 'bg-swarm-500/20 text-swarm-400'}
                `}>
                  {step.num}
                </span>
                <span className={`
                  font-mono text-xs tracking-wider font-semibold
                  ${step.color === 'human' ? 'text-human-400' : step.color === 'terminal-green' ? 'text-terminal-green' : 'text-swarm-300'}
                `}>
                  {step.label}
                </span>
              </div>

              {/* Icon */}
              <div className={`
                w-10 h-10 rounded-lg mb-4 flex items-center justify-center
                ${step.color === 'human' ? 'bg-human-500/10 text-human-400' : step.color === 'terminal-green' ? 'bg-terminal-green/10 text-terminal-green' : 'bg-swarm-500/10 text-swarm-400'}
              `}>
                <step.icon className="w-5 h-5" />
              </div>

              {/* Description */}
              <p className="text-slate-400 text-sm leading-relaxed mb-4">
                {step.description}
              </p>

              {/* Detail */}
              <div className="pt-3 border-t border-space-700/50">
                <span className="font-mono text-xs text-slate-500">
                  {step.detail}
                </span>
              </div>

              {/* Arrow connector */}
              {i < steps.length - 1 && (
                <div className="hidden md:flex absolute top-1/2 -right-3 transform -translate-y-1/2 z-10">
                  <div className="w-6 h-0.5 bg-space-700 relative overflow-hidden">
                    <div className="absolute inset-y-0 left-0 w-1/2 bg-swarm-500/40 pipeline-flow" />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Human control callout */}
        <div className="mt-12 text-center">
          <div className="inline-flex items-center gap-3 px-5 py-3 rounded-full border border-human-500/20 bg-human-500/5">
            <span className="w-3 h-3 rounded-full bg-human-500 human-pulse" />
            <span className="font-mono text-sm text-human-400">
              You approve at step 04 — the swarm never spends money without your say
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}