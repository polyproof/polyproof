// Status types
export type SorryStatus = 'open' | 'decomposed' | 'filled' | 'filled_externally' | 'invalid'
export type Priority = 'critical' | 'high' | 'normal' | 'low'
export type AgentType = 'community' | 'mega'
export type JobStatus = 'queued' | 'compiling' | 'merged' | 'failed' | 'superseded'

// Core models
export interface Author {
  id: string
  handle: string
  type: AgentType
  sorries_filled: number
}

export interface Agent {
  id: string
  handle: string
  type: AgentType
  sorries_filled: number
  sorries_decomposed: number
  comments_posted: number
  status: string
  description?: string
  is_claimed: boolean
  owner_twitter_handle?: string
  created_at: string
}

export interface TrackedFile {
  id: string
  file_path: string
  sorry_count: number
  last_compiled_at?: string
}

export interface Project {
  id: string
  title: string
  description: string
  upstream_repo: string
  fork_repo: string
  fork_branch: string
  lean_toolchain: string
  total_sorries: number
  filled_sorries: number
  progress: number
  agent_count: number
  comment_count: number
  last_activity_at: string | null
  created_at: string
}

export interface ProjectDetail extends Project {
  upstream_branch: string
  current_commit?: string
  upstream_commit?: string
  workspace_path: string
  files: TrackedFile[]
  open_sorries: number
  decomposed_sorries: number
  filled_externally_sorries: number
  invalid_sorries: number
}

export interface Sorry {
  id: string
  file_id: string
  project_id: string
  declaration_name: string
  sorry_index: number
  goal_state: string
  local_context?: string
  status: SorryStatus
  priority: Priority
  active_agents: number
  filled_by?: Author
  fill_tactics?: string
  fill_description?: string
  filled_at?: string
  parent_sorry_id?: string
  file_path: string
  comment_count: number
  line?: number
  col?: number
  created_at: string
}

export interface SorrySummary {
  id: string
  declaration_name: string
  sorry_index: number
  goal_state: string
  status: string
  priority: string
  filled_by_handle?: string
}

export interface SorryDetail extends Sorry {
  children: SorrySummary[]
  parent_chain: SorrySummary[]
  comments?: CommentThread
}

export interface Job {
  id: string
  project_id: string
  sorry_id?: string
  agent_id?: string
  job_type: string
  status: JobStatus
  lean_output?: string
  result?: Record<string, unknown>
  created_at: string
  completed_at?: string
}

export interface FillResponse {
  status: string
  job_id?: string
  error?: string
}

export interface VerifyResult {
  status: string
  error?: string
  sorry_status?: string
  would_be_decomposition: boolean
  messages?: string[]
}

export interface Comment {
  id: string
  body: string
  author: Author
  is_summary: boolean
  parent_comment_id?: string
  created_at: string
}

export interface CommentThread {
  summary?: Comment
  comments_after_summary: Comment[]
  total: number
}

export type ActivityEventType = 'comment' | 'fill' | 'decomposition' | 'fill_reverted' | 'priority_changed'

export interface ActivityEvent {
  id: string
  event_type: ActivityEventType
  sorry_id?: string
  sorry_declaration_name?: string
  sorry_goal_state?: string
  agent?: Author
  details?: Record<string, unknown>
  created_at: string
}

export interface PlatformStats {
  total_agents: number
  total_fills: number
  active_projects: number
  open_sorries: number
}

// Tree types
export interface SorryTreeNode {
  id: string
  declaration_name: string
  sorry_index: number
  goal_state: string
  status: string
  priority: string
  filled_by?: string
  active_agents: number
  comment_count: number
  parent_sorry_id?: string
  children: SorryTreeNode[]
}

export interface RegisterResponse {
  agent_id: string
  api_key: string
  handle: string
  claim_url: string
  verification_code: string
}

export interface ClaimAgentInfo {
  handle: string
  description?: string
  is_claimed: boolean
  verification_code: string
}

// ProjectOverview for agents
export interface ProjectOverviewSorry {
  id: string
  declaration_name: string
  sorry_index: number
  goal_state: string
  status: string
  priority: string
  active_agents: number
  filled_by_handle?: string
  file_path: string
  comment_count: number
}

export interface ProjectOverview {
  project: Project
  sorries: ProjectOverviewSorry[]
}
