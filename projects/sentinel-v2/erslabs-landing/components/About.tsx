import { Cpu, Users, Zap } from 'lucide-react'

const highlights = [
  {
    icon: Cpu,
    title: 'AI-Powered Discovery',
    description: 'Our systems continuously scan communities, forums, and social platforms for genuine unmet needs.',
  },
  {
    icon: Zap,
    title: 'Rapid Execution',
    description: 'From problem to deployed product in days. We build MVPs that solve the exact pain point discovered.',
  },
  {
    icon: Users,
    title: 'Community-First',
    description: 'Every solution is shared with the community where we found the problem. We give back, not just sell.',
  },
]

export function About() {
  return (
    <section id="about" className="py-24 md:py-32">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: Text */}
          <div>
            <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
              About
            </p>
            <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-6">
              A different kind of{' '}
              <span className="text-gradient">software lab</span>
            </h2>
            <p className="text-slate-400 leading-relaxed mb-4">
              ErsLabs is a solutions laboratory that starts every project the
              same way: by listening. We believe the best software is born from
              real frustrations — not brainstorming sessions.
            </p>
            <p className="text-slate-400 leading-relaxed">
              We monitor where people vent, ask for help, and describe their
              daily friction. When we spot a pattern — a problem that enough
              people share and would pay to solve — we build it. Fast,
              focused, and functional.
            </p>
          </div>

          {/* Right: Highlights */}
          <div className="space-y-6">
            {highlights.map((h) => (
              <div
                key={h.title}
                className="flex gap-5 p-5 rounded-xl border border-surface-600 hover:border-brand-500/30 transition-colors"
              >
                <div className="w-12 h-12 rounded-lg bg-brand-500/10 flex items-center justify-center flex-shrink-0">
                  <h.icon className="w-5 h-5 text-brand-400" />
                </div>
                <div>
                  <h3 className="font-semibold mb-1">{h.title}</h3>
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {h.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
