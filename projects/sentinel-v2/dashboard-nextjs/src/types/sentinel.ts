export type Phase = 'idle' | 'research' | 'match' | 'build' | 'approve' | 'deploy'

export type FlowState = {
  cycle: number
  phase: string
  opportunity: {
    title?: string
    icon?: string
    problem?: string
    solution?: string
    tech_fit?: number
    complexity?: number
  } | null
  build_output: string | null
  match_score: number
  deployed?: boolean
  updated_at?: string
}

export type FlowMetrics = {
  coverage_percent?: number
  issues_count?: number
  files_changed?: number
  tests_passed?: number
  tests_total?: number
  custom?: Record<string, unknown>
}

export type FlowActivity = {
  type: string
  agent: string
  message: string
  timestamp?: string
}

export type FlowBlocker = {
  id: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
  resolved?: boolean
}

export type FlowBreakdown = {
  cycle: number
  phase: string
  sub_phase: string | null
  status: string
  progress: number
  current_task: string | null
  next_task: string | null
  completed_tasks: string[]
  pending_tasks: string[]
  blockers: FlowBlocker[]
  metrics: FlowMetrics
  opportunity_title?: string | null
  match_score?: number
  deployed?: boolean
  phase_started_at?: string | null
  updated_at?: string
  activities?: FlowActivity[]
}

export type AgentMessage = {
  agent_id: string
  message: string
  hook_type?: string
  phase?: string
  cycle?: number
  metadata?: Record<string, unknown> & {
    role?: string
    goal?: string
    files_reviewed?: number
    issues_found?: number
  }
  timestamp: string
}

// ── Drafts + build queue ──────────────────────────────────────────────────────

export type DraftStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'queued'
  | 'building'
  | 'review'
  | 'testing'
  | 'built'
  | 'deployed'
  | 'failed'

export type Draft = {
  id: string
  cycle: number
  title: string
  tagline?: string
  description: string
  problem?: string
  solution?: string
  tech_fit: number
  complexity: number
  estimated_hours?: number | null
  tags?: string[]
  status: DraftStatus
  created_at?: string
  updated_at?: string
  build_progress?: number
  queue_position?: number | null
  revision_notes?: string | null
  deployment_url?: string | null
}

export type DraftsState = {
  drafts: Draft[]
  build_queue: Draft[]
  updated_at?: string
}
