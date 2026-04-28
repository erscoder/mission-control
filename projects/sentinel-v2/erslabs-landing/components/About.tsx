import { Cpu, Users, Zap, Brain, ArrowRight } from 'lucide-react'

const stats = [
  { value: '17', label: 'AI Agents', icon: Brain },
  { value: '50+', label: 'Sources Monitored', icon: Cpu },
  { value: '<4h', label: 'Discovery to Deploy', icon: Zap },
  { value: '24/7', label: 'Always Scanning', icon: Users },
]

export function About() {
  return (
    <section id="about" className="py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 noise" />
      <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-accent-violet/[0.02] rounded-full blur-[120px]" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left: Text */}
          <div>
            <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
              About
            </p>
            <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-6 leading-tight">
              Software that{' '}
              <span className="text-gradient">starts</span>
              <br />
              with listening
            </h2>
            <p className="text-slate-400 leading-relaxed text-lg mb-4">
              ErsLabs is not a typical software company. We don&apos;t start with
              ideas. We start with evidence. Our autonomous agents monitor
              communities where people describe their daily frustrations.
            </p>
            <p className="text-slate-400 leading-relaxed text-lg mb-8">
              When enough people share the same problem and show willingness to
              pay for a solution, our pipeline kicks in. Design, build, test,
              deploy. All automated, all in hours, not months.
            </p>

            <a
              href="#pipeline"
              className="group inline-flex items-center gap-2 text-brand-400 hover:text-brand-300 font-medium transition-colors"
            >
              See the full pipeline
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </a>
          </div>

          {/* Right: Stats */}
          <div className="grid grid-cols-2 gap-4">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="p-6 rounded-xl border border-surface-600/50 bg-surface-900/60 backdrop-blur-sm card-shine text-center hover:border-brand-500/20 transition-all"
              >
                <stat.icon className="w-6 h-6 text-brand-400 mx-auto mb-3" />
                <div className="text-3xl md:text-4xl font-black text-white mb-1 tracking-tight">
                  {stat.value}
                </div>
                <div className="text-xs font-mono text-surface-500 uppercase tracking-wider">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
