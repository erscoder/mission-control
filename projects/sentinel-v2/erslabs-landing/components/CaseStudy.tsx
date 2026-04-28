import { CheckCircle, Clock, Globe, CreditCard, Shield, Zap } from 'lucide-react'

export function CaseStudy() {
  return (
    <section className="py-24 md:py-32 relative overflow-hidden">
      <div className="absolute inset-0 noise" />
      {/* Background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-swarm-500/[0.03] rounded-full blur-[100px]" />

      <div className="relative max-w-6xl mx-auto px-6">
        {/* Header */}
        <div className="text-center mb-16">
          <p className="text-swarm-400 font-mono text-sm tracking-wider uppercase mb-3">
            Case Study
          </p>
          <h2 className="text-4xl md:text-5xl font-black tracking-tight mb-4">
            From Reddit post to <span className="text-gradient-swarm">live product</span>
          </h2>
          <p className="text-slate-400 max-w-2xl mx-auto text-lg">
            A real example of how our agents discovered, built, and shipped an app,
            end to end, autonomously.
          </p>
        </div>

        {/* Case study card */}
        <div className="max-w-4xl mx-auto">
          <div className="rounded-2xl border border-space-700/50 bg-space-900/80 backdrop-blur-sm overflow-hidden">
            {/* Header bar */}
            <div className="px-6 py-4 border-b border-space-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-swarm-400 to-swarm-600 p-[1px]">
                  <div className="w-full h-full rounded-xl bg-space-900 flex items-center justify-center">
                    <Shield className="w-5 h-5 text-swarm-400" />
                  </div>
                </div>
                <div>
                  <h3 className="font-bold text-lg">ComplianceDesk</h3>
                  <p className="text-xs font-mono text-slate-400">compliancedesk.erslabs.net</p>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-swarm-500/10 text-swarm-400 border border-swarm-500/20">
                LIVE
              </span>
            </div>

            {/* Content */}
            <div className="p-6 md:p-8">
              {/* Origin */}
              <div className="mb-8">
                <h4 className="text-xs font-mono text-swarm-400 uppercase tracking-wider mb-3">
                  The Discovery
                </h4>
                <div className="rounded-lg border border-space-700/50 bg-space-800/50 p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <svg className="w-5 h-5 text-orange-400" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z"/>
                      </svg>
                    </div>
                    <div>
                      <p className="text-sm text-slate-300 font-medium mb-1">
                        John healthIT
                      </p>
                      <p className="text-sm text-slate-400 italic leading-relaxed">
                        &ldquo;I spend 10+ hours every week just tracking HIPAA compliance paperwork.
                        There has to be a better way than spreadsheets...&rdquo;
                      </p>
                      <p className="text-xs text-space-600 font-mono mt-2">
                        + 23 similar complaints found across 4 communities
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* What was built */}
              <div className="mb-8">
                <h4 className="text-xs font-mono text-swarm-300 uppercase tracking-wider mb-3">
                  What the agents built
                </h4>
                <p className="text-slate-400 leading-relaxed mb-4">
                  An automated HIPAA compliance tracker for small healthcare providers.
                  Auto-generates audit trails, tracks training deadlines, flags policy violations,
                  and produces ready-to-submit compliance reports, replacing 10+ hours/week of manual work.
                </p>

                <div className="grid sm:grid-cols-2 gap-3">
                  {[
                    { icon: Globe, text: 'Next.js 14 + Tailwind frontend' },
                    { icon: CreditCard, text: 'Stripe Checkout from day 1' },
                    { icon: Shield, text: 'Security audited, zero critical issues' },
                    { icon: Zap, text: 'Deployed on Cloud' },
                  ].map((item) => (
                    <div key={item.text} className="flex items-center gap-2.5 text-sm text-slate-300">
                      <item.icon className="w-4 h-4 text-swarm-400 flex-shrink-0" />
                      {item.text}
                    </div>
                  ))}
                </div>
              </div>

              {/* Timeline */}
              <div>
                <h4 className="text-xs font-mono text-swarm-400 uppercase tracking-wider mb-4">
                  Timeline
                </h4>
                <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-0 sm:justify-between">
                  {[
                    { time: '08:14', label: 'Problem discovered', status: 'done' },
                    { time: '08:16', label: 'Match confirmed (92%)', status: 'done' },
                    { time: '08:22', label: 'Build started', status: 'done' },
                    { time: '11:47', label: 'Code review passed', status: 'done' },
                    { time: '12:03', label: 'Live on erslabs.net', status: 'done' },
                  ].map((step, i) => (
                    <div key={step.label} className="flex sm:flex-col items-center sm:items-center gap-3 sm:gap-1.5">
                      <div className="flex items-center gap-2">
                        <CheckCircle className="w-4 h-4 text-swarm-400" />
                        <span className="font-mono text-xs text-swarm-300">{step.time}</span>
                      </div>
                      <span className="text-xs text-slate-400">{step.label}</span>
                      {i < 4 && (
                        <div className="hidden sm:block w-12 h-px bg-space-700 mt-2" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-space-700/50 flex items-center justify-between bg-space-800/30">
              <div className="flex items-center gap-2 text-xs font-mono text-space-600">
                <Clock className="w-3.5 h-3.5" />
                <span>Total time: <span className="text-swarm-400">3h 49m</span> from discovery to production</span>
              </div>
              <a
                href="https://compliancedesk.erslabs.net"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-mono text-swarm-400 hover:text-swarm-300 transition-colors"
              >
                Visit app &rarr;
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}