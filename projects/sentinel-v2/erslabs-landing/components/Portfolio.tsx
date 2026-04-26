import { ExternalLink } from 'lucide-react'
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
    <section id="portfolio" className="py-24 md:py-32 bg-surface-800/50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-16">
          <p className="text-brand-400 font-mono text-sm tracking-wider uppercase mb-3">
            Portfolio
          </p>
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            Apps we&apos;ve shipped
          </h2>
          <p className="text-slate-400 mt-4 max-w-lg mx-auto">
            Every app started as a real problem someone shared online. Here&apos;s what we built.
          </p>
        </div>

        {apps.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mx-auto mb-4">
              <Rocket className="w-7 h-7 text-brand-400" />
            </div>
            <p className="text-slate-400 text-lg">First apps coming soon.</p>
            <p className="text-slate-500 text-sm mt-2">
              Our agents are scouting communities right now.
            </p>
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {apps.map((app) => (
              <a
                key={app.slug}
                href={app.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group block p-6 rounded-xl bg-surface-900 border border-surface-600 hover:border-brand-500/40 transition-all hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold group-hover:text-brand-400 transition-colors">
                    {app.title}
                  </h3>
                  <ExternalLink className="w-4 h-4 text-slate-500 group-hover:text-brand-400 transition-colors flex-shrink-0 mt-1" />
                </div>

                <p className="text-brand-400 text-sm font-medium mb-3">
                  {app.tagline}
                </p>

                <p className="text-slate-400 text-sm leading-relaxed mb-4 line-clamp-3">
                  {app.problem}
                </p>

                <div className="flex flex-wrap gap-2">
                  {app.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2.5 py-0.5 text-xs font-mono text-brand-300 bg-brand-500/10 rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

function Rocket(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg {...props} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>
    </svg>
  )
}
