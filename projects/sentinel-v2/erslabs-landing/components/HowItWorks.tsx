import { Ear, Hammer, Rocket } from 'lucide-react'

const steps = [
  {
    icon: Ear,
    title: 'Listen',
    description:
      'We scan communities — Reddit, Twitter, Hacker News, forums — for real complaints, pain points, and unmet needs with evidence of willingness to pay.',
  },
  {
    icon: Hammer,
    title: 'Build',
    description:
      'Our AI-powered agent swarm designs, builds, and tests an MVP in days, not months. Focused on solving the exact problem people described.',
  },
  {
    icon: Rocket,
    title: 'Ship',
    description:
      'We deploy the solution and share it back with the communities where we found the problem. Real solutions for real people.',
  },
]

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
            Process
          </p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            From pain point to product
          </h2>
        </div>

        <div className="grid md:grid-cols-3 gap-8 md:gap-12">
          {steps.map((step, i) => (
            <div key={step.title} className="relative group">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-10 left-[calc(50%+40px)] w-[calc(100%-80px)] h-px bg-gradient-to-r from-brand-500/40 to-brand-500/10" />
              )}

              <div className="flex flex-col items-center text-center">
                {/* Icon */}
                <div className="w-20 h-20 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-6 group-hover:bg-brand-500/15 transition-colors">
                  <step.icon className="w-8 h-8 text-brand-400" />
                </div>

                {/* Step number */}
                <span className="text-brand-500 font-mono text-sm mb-2">
                  0{i + 1}
                </span>

                <h3 className="text-xl font-semibold mb-3">{step.title}</h3>
                <p className="text-slate-400 leading-relaxed max-w-sm">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
