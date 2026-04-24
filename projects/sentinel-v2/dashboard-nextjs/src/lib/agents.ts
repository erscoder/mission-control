import {
  Search,
  TrendingUp,
  Target,
  Wrench,
  Code2,
  Server,
  ShieldCheck,
  ClipboardCheck,
  Rocket,
  Brain,
  Users,
  Globe,
  type LucideIcon,
  Bot,
} from 'lucide-react'
import type { Phase } from '@/types/sentinel'

// ── Agent registry ────────────────────────────────────────────────────────────

export type AgentRoleDef = {
  id: string
  name: string
  phase: Phase
  icon: LucideIcon
  accent: string
  gradient: string
}

export const AGENTS: Record<string, AgentRoleDef> = {
  'web-scout': {
    id: 'web-scout',
    name: 'Web Scout',
    phase: 'research',
    icon: Search,
    accent: 'text-sky-400',
    gradient: 'from-sky-500 to-blue-600',
  },
  'market-analyst': {
    id: 'market-analyst',
    name: 'Market Analyst',
    phase: 'research',
    icon: TrendingUp,
    accent: 'text-sky-400',
    gradient: 'from-sky-500 to-cyan-500',
  },
  'profile-researcher': {
    id: 'profile-researcher',
    name: 'Profile Researcher',
    phase: 'match',
    icon: Users,
    accent: 'text-amber-300',
    gradient: 'from-amber-400 to-orange-500',
  },
  matcher: {
    id: 'matcher',
    name: 'Matcher',
    phase: 'match',
    icon: Target,
    accent: 'text-amber-300',
    gradient: 'from-amber-400 to-rose-500',
  },
  'strategic-manager': {
    id: 'strategic-manager',
    name: 'Strategic Manager',
    phase: 'build',
    icon: Brain,
    accent: 'text-indigo-300',
    gradient: 'from-indigo-500 to-violet-500',
  },
  'frontend-lead': {
    id: 'frontend-lead',
    name: 'Frontend Lead',
    phase: 'build',
    icon: Code2,
    accent: 'text-violet-300',
    gradient: 'from-violet-500 to-fuchsia-500',
  },
  'backend-lead': {
    id: 'backend-lead',
    name: 'Backend Lead',
    phase: 'build',
    icon: Server,
    accent: 'text-fuchsia-300',
    gradient: 'from-fuchsia-500 to-pink-500',
  },
  'code-reviewer': {
    id: 'code-reviewer',
    name: 'Code Reviewer',
    phase: 'build',
    icon: ClipboardCheck,
    accent: 'text-violet-300',
    gradient: 'from-violet-500 to-indigo-500',
  },
  'security-auditor': {
    id: 'security-auditor',
    name: 'Security Auditor',
    phase: 'build',
    icon: ShieldCheck,
    accent: 'text-emerald-300',
    gradient: 'from-emerald-500 to-teal-500',
  },
  'qa-lead': {
    id: 'qa-lead',
    name: 'QA Lead',
    phase: 'build',
    icon: Wrench,
    accent: 'text-indigo-300',
    gradient: 'from-indigo-500 to-blue-500',
  },
  'deployment-engineer': {
    id: 'deployment-engineer',
    name: 'Deployment Engineer',
    phase: 'deploy',
    icon: Rocket,
    accent: 'text-emerald-300',
    gradient: 'from-emerald-500 to-green-500',
  },
  'qa-verifier': {
    id: 'qa-verifier',
    name: 'QA Verifier',
    phase: 'deploy',
    icon: ClipboardCheck,
    accent: 'text-emerald-300',
    gradient: 'from-teal-500 to-emerald-500',
  },
  orchestrator: {
    id: 'orchestrator',
    name: 'Sentinel',
    phase: 'idle',
    icon: Globe,
    accent: 'text-indigo-300',
    gradient: 'from-indigo-500 to-violet-600',
  },
  sentinel: {
    id: 'sentinel',
    name: 'Sentinel',
    phase: 'idle',
    icon: Globe,
    accent: 'text-indigo-300',
    gradient: 'from-indigo-500 to-violet-600',
  },
}

export function getAgent(agent_id: string): AgentRoleDef {
  const key = agent_id?.toLowerCase().replace(/\s+/g, '-')
  return (
    AGENTS[key] ?? {
      id: key || 'unknown',
      name: humanize(key || 'Agent'),
      phase: 'idle',
      icon: Bot,
      accent: 'text-muted-foreground',
      gradient: 'from-zinc-600 to-zinc-500',
    }
  )
}

export function humanize(slug: string) {
  return slug
    .split(/[-_]/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

// ── Phase registry ────────────────────────────────────────────────────────────

export type PhaseDef = {
  id: Phase
  label: string
  description: string
  icon: LucideIcon
  accent: string
  gradient: string
  agents: string[]
}

export const PHASES: PhaseDef[] = [
  {
    id: 'research',
    label: 'Research',
    description: 'Scouting the web for opportunities',
    icon: Search,
    accent: 'text-sky-400',
    gradient: 'from-sky-500 to-blue-500',
    agents: ['web-scout', 'market-analyst'],
  },
  {
    id: 'match',
    label: 'Match',
    description: 'Scoring fit against Kike’s profile',
    icon: Target,
    accent: 'text-amber-300',
    gradient: 'from-amber-400 to-rose-500',
    agents: ['profile-researcher', 'matcher'],
  },
  {
    id: 'build',
    label: 'Build',
    description: 'Hierarchical build crew in action',
    icon: Wrench,
    accent: 'text-violet-300',
    gradient: 'from-violet-500 to-fuchsia-500',
    agents: [
      'strategic-manager',
      'frontend-lead',
      'backend-lead',
      'code-reviewer',
      'security-auditor',
      'qa-lead',
    ],
  },
  {
    id: 'approve',
    label: 'Approve',
    description: 'Human-in-the-loop gate',
    icon: ClipboardCheck,
    accent: 'text-indigo-300',
    gradient: 'from-indigo-500 to-violet-500',
    agents: ['orchestrator'],
  },
  {
    id: 'deploy',
    label: 'Deploy',
    description: 'Shipping to production',
    icon: Rocket,
    accent: 'text-emerald-300',
    gradient: 'from-emerald-500 to-teal-500',
    agents: ['deployment-engineer', 'qa-verifier'],
  },
]

export function phaseIndex(phase: string): number {
  const idx = PHASES.findIndex((p) => p.id === phase)
  return idx
}
