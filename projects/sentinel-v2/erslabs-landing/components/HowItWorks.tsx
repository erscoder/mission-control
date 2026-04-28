import { Ear, Hammer, Rocket, ArrowRight } from 'lucide-react'

const steps = [
  {
    icon: Ear,
    num: '01',
    title: 'Listen',
    iconWrap: 'bg-accent-cyan/10 border-accent-cyan/20',
    iconColor: 'text-accent-cyan',
    labelColor: 'text-accent-cyan',
    description:
      'Our agents continuously scan Reddit, Twitter, Hacker News, and 50+ forums for genuine complaints, not trends, not hype. Real people describing real friction, with evidence they would pay for a solution.',
    detail: '847 sources monitored',
  },
  {
    icon: Hammer,
    num: '02',
    title: 'Build',
    iconWrap: 'bg-brand-400/10 border-brand-400/20',
    iconColor: 'text-brand-400',
    labelColor: 'text-brand-400',
    description:
      'A crew of 6 specialized AI agents (product manager, frontend engineer, backend engineer, code reviewer, security auditor, and QA lead) collaborate to ship a complete, tested MVP with Stripe payments from day one.',
    detail: '6 agents per build',
  },
  {
    icon: Rocket,
    num: '03',
    title: 'Ship',
    iconWrap: 'bg-brand-300/10 border-brand-300/20',
    iconColor: 'text-brand-300',
    labelColor: 'text-brand-300',
    description:
      'Auto-deployed to production: backend on Fly.io, frontend on Cloudflare Pages, custom domain under erslabs.net, Stripe webhooks wired, SSL certificates provisioned. Zero manual intervention.',
    detail: '< 4 hours end-to-end',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 md:py-32 bg-surface-800/30 relative">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="text-center mb-20">
          <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
            Process
          </p>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight">
            From pain to{' '}
            <span className="text-gradient">product</span>
          </h2>
        </div>

        <div className="space-y-8 md:space-y-0 md:grid md:grid-cols-3 md:gap-8">
          {steps.map((step, i) => (
            <div key={step.title} className="relative group">
              {/* Connector */}
              {i < steps.length - 1 && (
                <div className="hidden md:flex absolute top-12 left-[calc(100%-8px)] w-8 items-center justify-center z-10">
                  <ArrowRight className="w-4 h-4 text-surface-600 group-hover:text-brand-500/50 transition-colors" />
                </div>
              )}

              <div className="p-6 rounded-xl border border-surface-600/50 bg-surface-900/60 backdrop-blur-sm hover:border-brand-500/30 transition-all duration-300 h-full">
                {/* Top row */}
                <div className="flex items-center gap-4 mb-5">
                  <div className={`w-14 h-14 rounded-2xl ${step.iconWrap} border flex items-center justify-center`}>
                    <step.icon className={`w-6 h-6 ${step.iconColor}`} />
                  </div>
                  <div>
                    <span className={`${step.labelColor} font-mono text-xs tracking-wider`}>
                      STEP {step.num}
                    </span>
                    <h3 className="text-2xl font-bold tracking-tight">{step.title}</h3>
                  </div>
                </div>

                <p className="text-slate-400 leading-relaxed text-[15px] mb-4">
                  {step.description}
                </p>

                <div className="pt-4 border-t border-surface-700/50">
                  <span className="font-mono text-xs text-surface-500">
                    {step.detail}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
