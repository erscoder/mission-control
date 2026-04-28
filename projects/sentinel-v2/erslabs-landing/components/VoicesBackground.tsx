type Voice = {
  text: string
  top: string
  left?: string
  right?: string
  size?: number
  rotate?: number
  opacity?: number
  weight?: 400 | 500 | 700
  source?: string
  color?: 'brand' | 'cyan' | 'amber' | 'rose' | 'violet' | 'white'
}

const FONT_HAND = "'Caveat', 'Kalam', 'Comic Sans MS', cursive"

const COLORS: Record<NonNullable<Voice['color']>, string> = {
  brand: '#34D399',
  cyan: '#22D3EE',
  amber: '#FBBF24',
  rose: '#FB7185',
  violet: '#A78BFA',
  white: '#F9FAFB',
}

// Real-feeling user complaints scattered like a "listening board" of overheard pain.
// All unique. Color encodes emotion: rose = frustration, amber = confusion,
// brand = wishful, cyan = feature request, violet = domain-specific, white = punchline.
const VOICES: Voice[] = [
  // === HERO (0-100vh): opening pain ===
  { text: "I just want a tool that does X. that's it.", source: 'r/SaaS', top: '8vh', left: '4%', size: 26, rotate: -3, opacity: 0.14, color: 'brand' },
  { text: "why is invoicing in 2026 still this painful", source: 'r/freelance', top: '12vh', right: '5%', size: 28, rotate: 2, opacity: 0.16, color: 'amber' },
  { text: "we paste between 3 tools every single day", source: 'HN comment', top: '20vh', left: '36%', size: 22, rotate: -1, opacity: 0.12 },
  { text: "if only there was a way to…", top: '28vh', left: '6%', size: 32, rotate: -4, opacity: 0.16, weight: 500, color: 'brand' },
  { text: "$200/mo and it can't even export to CSV", source: 'r/smallbusiness', top: '32vh', right: '6%', size: 24, rotate: 1, opacity: 0.14, color: 'rose' },
  { text: "feature request: just send the email", source: 'GitHub issue · 2 yrs old', top: '42vh', left: '5%', size: 22, rotate: 2, opacity: 0.12 },
  { text: "we built our own internal tool because nothing fit", source: 'r/Entrepreneur', top: '46vh', right: '7%', size: 22, rotate: -2, opacity: 0.13 },
  { text: "ugh", top: '52vh', left: '46%', size: 56, rotate: -8, opacity: 0.14, weight: 700, color: 'rose' },
  { text: "spent 6 hours on a spreadsheet that should take 6 min", source: 'Slack DM', top: '58vh', left: '4%', size: 22, rotate: 1, opacity: 0.13 },
  { text: "I wish someone would just build this already", source: 'r/sysadmin', top: '64vh', right: '5%', size: 26, rotate: -2, opacity: 0.15, weight: 500, color: 'brand' },
  { text: "Excel is still our best CRM", source: 'r/sales', top: '74vh', left: '40%', size: 22, rotate: 3, opacity: 0.11 },
  { text: "every demo says AI-powered. none of them work.", source: 'HN', top: '80vh', left: '6%', size: 22, rotate: -1, opacity: 0.13, color: 'rose' },
  { text: "?", top: '24vh', left: '52%', size: 64, rotate: 14, opacity: 0.10, weight: 700, color: 'amber' },
  { text: "just one screen. not 14 tabs.", top: '88vh', right: '7%', size: 24, rotate: -3, opacity: 0.14, color: 'amber' },

  // === HOW IT WORKS (100-200vh): domain pain ===
  { text: "as a small clinic we can't afford Epic", source: 'r/medicine', top: '106vh', left: '5%', size: 24, rotate: -2, opacity: 0.14, color: 'violet' },
  { text: "compliance audits = 3 weeks of pure dread", source: 'r/cybersecurity', top: '110vh', right: '6%', size: 22, rotate: 2, opacity: 0.13, color: 'rose' },
  { text: "our therapist still takes notes by hand", source: 'r/Therapists', top: '120vh', left: '8%', size: 22, rotate: -1, opacity: 0.13, color: 'violet' },
  { text: "the Zapier integration broke. again.", source: 'Slack #ops', top: '126vh', right: '8%', size: 22, rotate: -2, opacity: 0.13, color: 'rose' },
  { text: "support told us to 'use a workaround'", source: 'support ticket', top: '136vh', left: '5%', size: 22, rotate: 1, opacity: 0.12 },
  { text: "evaluated 12 tools. all of them suck.", source: 'r/devops', top: '142vh', right: '6%', size: 24, rotate: -2, opacity: 0.14, weight: 500, color: 'rose' },
  { text: "the onboarding took 3 weeks", source: 'r/startups', top: '150vh', left: '40%', size: 22, rotate: 4, opacity: 0.12 },
  { text: "they charge per user. we have 200 users.", source: 'CTO email', top: '156vh', left: '6%', size: 22, rotate: -1, opacity: 0.13, color: 'rose' },
  { text: "another login, another bill", top: '166vh', right: '6%', size: 28, rotate: -3, opacity: 0.15, weight: 500, color: 'amber' },
  { text: "we evaluated this. then built our own.", source: 'r/Entrepreneur', top: '174vh', left: '7%', size: 22, rotate: 2, opacity: 0.13 },
  { text: "as a lawyer, billable hours track themselves… not.", source: 'r/lawyertalk', top: '180vh', right: '8%', size: 20, rotate: -2, opacity: 0.12, color: 'violet' },
  { text: "this is literally a CSV with a UI", source: 'HN', top: '190vh', left: '40%', size: 22, rotate: -3, opacity: 0.13, color: 'amber' },
  { text: "we'd build it ourselves if we had time", source: 'r/smallbusiness', top: '195vh', left: '5%', size: 22, rotate: 1, opacity: 0.13 },

  // === PIPELINE (200-300vh): workflow friction ===
  { text: "'enterprise' = 'call us for a quote'", source: 'r/SaaS', top: '208vh', left: '5%', size: 22, rotate: -2, opacity: 0.13, color: 'amber' },
  { text: "the export gives me a PDF? I need raw data.", source: 'r/dataengineering', top: '214vh', right: '7%', size: 22, rotate: 2, opacity: 0.13 },
  { text: "we had to write a Zapier to do basic stuff", source: 'Slack DM', top: '224vh', left: '6%', size: 22, rotate: 3, opacity: 0.13 },
  { text: "billing doesn't match what we agreed", source: 'r/SaaS', top: '230vh', right: '5%', size: 22, rotate: -2, opacity: 0.13, color: 'rose' },
  { text: "IT blocked it on day 2", source: 'CTO Slack', top: '240vh', left: '40%', size: 22, rotate: 1, opacity: 0.12 },
  { text: "we shouldn't need a consultant to use this", source: 'HN', top: '246vh', left: '5%', size: 22, rotate: -2, opacity: 0.14, color: 'rose' },
  { text: "the trial excludes the only feature we need", source: 'r/SaaS', top: '254vh', right: '6%', size: 22, rotate: 2, opacity: 0.13, color: 'amber' },
  { text: "!!!", top: '260vh', left: '46%', size: 56, rotate: -10, opacity: 0.14, weight: 700, color: 'cyan' },
  { text: "they renamed basic features to sound special", source: 'r/marketing', top: '268vh', right: '7%', size: 22, rotate: -2, opacity: 0.12 },
  { text: "I'm a freelancer. I can't justify $99/mo.", source: 'r/freelance', top: '278vh', left: '8%', size: 22, rotate: -2, opacity: 0.13, color: 'violet' },
  { text: "this should be a button, not a workflow", source: 'r/UXDesign', top: '286vh', right: '6%', size: 22, rotate: 1, opacity: 0.13, color: 'amber' },
  { text: "data export costs extra. seriously.", source: 'r/sysadmin', top: '294vh', left: '40%', size: 22, rotate: 3, opacity: 0.12, color: 'rose' },

  // === CASE STUDY (300-400vh): concrete grievances ===
  { text: "the AI feature is just GPT with a prompt", source: 'HN', top: '308vh', left: '5%', size: 22, rotate: -1, opacity: 0.13, color: 'amber' },
  { text: "I want notifications I actually care about", source: 'r/productivity', top: '316vh', right: '6%', size: 22, rotate: 2, opacity: 0.13 },
  { text: "no one builds for our use case", source: 'r/specialed', top: '326vh', left: '6%', size: 24, rotate: -3, opacity: 0.14, color: 'violet' },
  { text: "we run the office on Notion + duct tape", source: 'r/Entrepreneur', top: '334vh', right: '7%', size: 22, rotate: 1, opacity: 0.13 },
  { text: "the API rate-limits us at 10/min", source: 'r/webdev', top: '344vh', left: '40%', size: 22, rotate: -2, opacity: 0.12, color: 'rose' },
  { text: "why does this need an account?", source: 'r/web_design', top: '352vh', left: '5%', size: 24, rotate: 2, opacity: 0.13, color: 'amber' },
  { text: "if a tool exists for this please tell me", source: 'r/AskReddit', top: '362vh', right: '6%', size: 24, rotate: -2, opacity: 0.14, weight: 500, color: 'brand' },
  { text: "spent the weekend duct-taping 3 SaaS", source: 'Slack #engineering', top: '372vh', left: '7%', size: 22, rotate: 1, opacity: 0.13 },
  { text: "we're a 4-person team, not a Fortune 500", source: 'r/startups', top: '382vh', right: '8%', size: 22, rotate: -2, opacity: 0.13 },
  { text: "the form takes 8 minutes per patient", source: 'r/medicine', top: '392vh', left: '6%', size: 22, rotate: 2, opacity: 0.13, color: 'violet' },

  // === PORTFOLIO (400-500vh): verdicts ===
  { text: "all I need is X. why is this so hard?", source: 'r/AskReddit', top: '408vh', left: '5%', size: 26, rotate: -2, opacity: 0.15, weight: 500, color: 'amber' },
  { text: "we'd pay for this if it just… worked", source: 'r/smallbusiness', top: '416vh', right: '6%', size: 22, rotate: 1, opacity: 0.13, color: 'rose' },
  { text: "their docs are out of date", source: 'r/devops', top: '424vh', left: '8%', size: 22, rotate: -2, opacity: 0.12 },
  { text: "I just want a single screen. not 14.", source: 'HN', top: '432vh', right: '6%', size: 22, rotate: 2, opacity: 0.13, color: 'amber' },
  { text: "every PM tool eventually becomes Jira", source: 'HN', top: '442vh', left: '40%', size: 22, rotate: -3, opacity: 0.13, color: 'rose' },
  { text: "I emailed support. day 4. nothing.", source: 'r/SaaS', top: '450vh', left: '6%', size: 22, rotate: 1, opacity: 0.13, color: 'rose' },
  { text: "the only working version is on Twitter screenshots", source: 'r/programming', top: '458vh', right: '7%', size: 20, rotate: -2, opacity: 0.12 },
  { text: "we left after the 4th broken update", source: 'r/sysadmin', top: '468vh', left: '7%', size: 22, rotate: 2, opacity: 0.13 },
  { text: "this should be 1 endpoint, not 6", source: 'r/webdev', top: '478vh', right: '7%', size: 22, rotate: -1, opacity: 0.12, color: 'amber' },
  { text: "the 'AI' is a regex", source: 'HN', top: '486vh', left: '40%', size: 24, rotate: 3, opacity: 0.13, weight: 500, color: 'amber' },
  { text: "we're still using Google Sheets for it", source: 'r/Accounting', top: '494vh', right: '8%', size: 22, rotate: -2, opacity: 0.13, color: 'violet' },

  // === ABOUT (500-600vh): closing voices ===
  { text: "we're listening.", top: '508vh', left: '5%', size: 32, rotate: -2, opacity: 0.18, weight: 700, color: 'brand' },
  { text: "we just need it to work", source: 'r/sysadmin', top: '516vh', right: '6%', size: 24, rotate: 1, opacity: 0.14 },
  { text: "another year, another waitlist", source: 'r/startups', top: '524vh', left: '7%', size: 22, rotate: -2, opacity: 0.13, color: 'amber' },
  { text: "stop adding features. fix the bugs.", source: 'r/SaaS', top: '532vh', right: '7%', size: 22, rotate: 2, opacity: 0.13, color: 'rose' },
  { text: "the dashboard hasn't loaded in 30s", source: 'Slack DM', top: '542vh', left: '40%', size: 22, rotate: -3, opacity: 0.12 },
  { text: "I just want a tool a normal human can use", source: 'r/smallbusiness', top: '548vh', left: '6%', size: 22, rotate: 1, opacity: 0.13, color: 'amber' },
  { text: "if your pricing page needs a salesperson, no thanks", source: 'HN', top: '558vh', right: '5%', size: 22, rotate: -2, opacity: 0.13 },
  { text: "we listen. we build. we ship.", top: '568vh', left: '40%', size: 28, rotate: -2, opacity: 0.18, weight: 700, color: 'white' },
  { text: "we'd take a v0.1 over a roadmap", source: 'r/Entrepreneur', top: '576vh', left: '6%', size: 22, rotate: 2, opacity: 0.13 },
  { text: "ship something that just works", source: 'HN', top: '584vh', right: '6%', size: 24, rotate: -2, opacity: 0.15, weight: 500, color: 'brand' },
  { text: "→", top: '594vh', left: '46%', size: 56, rotate: 0, opacity: 0.14, weight: 700, color: 'brand' },
]

if (process.env.NODE_ENV !== 'production') {
  const seen = new Set<string>()
  for (const v of VOICES) {
    const key = v.text.replace(/\s+/g, ' ').trim().toLowerCase()
    if (seen.has(key)) {
      console.warn('[VoicesBackground] duplicate voice:', key)
    }
    seen.add(key)
  }
}

// Global tuning: scales applied at render time so we don't touch all 71 entries.
// Caveat lightest weight is 400, no 300 in Google Fonts. Lean on opacity for "lighter".
const SIZE_SCALE = 0.62
const OPACITY_SCALE = 0.48
const WEIGHT_CAP: 400 = 400

export function VoicesBackground() {
  return (
    <div
      aria-hidden="true"
      className="absolute inset-0 overflow-hidden pointer-events-none select-none"
    >
      {VOICES.map((v, i) => {
        const size = (v.size ?? 22) * SIZE_SCALE
        const opacity = (v.opacity ?? 0.12) * OPACITY_SCALE
        const weight = Math.min(v.weight ?? 400, WEIGHT_CAP)
        return (
          <div
            key={i}
            className="absolute whitespace-nowrap leading-tight"
            style={{
              top: v.top,
              left: v.left,
              right: v.right,
              transform: `rotate(${v.rotate ?? 0}deg)`,
              opacity,
              fontFamily: FONT_HAND,
              fontWeight: weight,
              fontSize: `${size}px`,
              color: COLORS[v.color ?? 'brand'],
            }}
          >
            {v.text}
            {v.source && (
              <span
                style={{
                  fontFamily: FONT_HAND,
                  fontWeight: 400,
                  fontSize: `${size * 0.55}px`,
                  marginLeft: '10px',
                  opacity: 0.5,
                  color: '#64748B',
                }}
              >
                ← {v.source}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
