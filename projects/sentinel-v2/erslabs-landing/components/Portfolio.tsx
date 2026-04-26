import { ExternalLink, Rocket } from 'lucide-react'
import portfolio from '@/data/portfolio.json'

interface App {
  slug: string
  title: string
  tagline: string
  problem: string
  url: string
  tags: string[]
  deployed_at: string
}

export function Portfolio() {
  const apps = portfolio as App[]

  return (
    <section id="portfolio" className="py-24 md:py-32 bg-surface-800/30 relative">
      <div className="absolute inset-0 noise" />

      <div className="relative max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
            Portfolio
          </p>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
            Shipped <span className="text-gradient">products</span>
          </h2>
          <p className="text-slate-400 max-w-lg mx-auto text-lg">
            Every app started as someone&apos;s real frustration. Here&apos;s what our agents built.
          </p>
        </div>

        {apps.length === 0 ? (
          <div className="text-center py-20">
            <div className="relative inline-flex mb-6">
              <div className="w-20 h-20 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center">
                <Rocket className="w-9 h-9 text-brand-400 animate-float" />
              </div>
              <div className="absolute inset-0 rounded-2xl bg-brand-500/5 blur-xl" />
            </div>
            <p className="text-slate-300 text-xl font-semibold mb-2">Building now</p>
            <p className="text-slate-500 max-w-sm mx-auto">
              Our agents are currently building the first batch of products.
              Check back soon.
            </p>
            <div className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-full border border-surface-600 text-xs font-mono text-surface-500">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-500" />
              </span>
              pipeline active
            </div>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {apps.map((app) => (
              <a
                key={app.slug}
                href={app.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group relative block p-6 rounded-xl border border-surface-600/50 bg-surface-900/60 backdrop-blur-sm card-shine hover:border-brand-500/30 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.5)]"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-bold group-hover:text-brand-400 transition-colors">
                    {app.title}
                  </h3>
                  <ExternalLink className="w-4 h-4 text-surface-500 group-hover:text-brand-400 transition-colors flex-shrink-0 mt-1" />
                </div>

                <p className="text-brand-400 text-sm font-mono font-medium mb-3">
                  {app.tagline}
                </p>

                <p className="text-slate-400 text-sm leading-relaxed mb-5 line-clamp-3">
                  {app.problem}
                </p>

                <div className="flex flex-wrap gap-2 mt-auto">
                  {app.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2.5 py-0.5 text-[10px] font-mono font-medium text-brand-300/80 bg-brand-500/5 border border-brand-500/10 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                {/* Bottom glow */}
                <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-3/4 h-px bg-gradient-to-r from-transparent via-brand-500/0 to-transparent group-hover:via-brand-500/50 transition-all duration-500" />
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
