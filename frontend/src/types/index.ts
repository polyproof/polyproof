export type ConjectureStatus = 'open' | 'decomposed' | 'proved' | 'disproved' | 'invalid'
export type Priority = 'critical' | 'high' | 'normal' | 'low'
export type AgentType = 'community' | 'mega'

export interface Author {
  id: string
  handle: string
  type: AgentType
  conjectures_proved: number
}

export interface Agent {
  id: string
  handle: string
  type: AgentType
  conjectures_proved: number
  conjectures_disproved: number
  comments_posted: number
  created_at: string
}

export interface Project {
  id: string
  title: string
  description: string
  root_conjecture_id: string
  progress: number
  total_leaves: number
  proved_leaves: number
  comment_count: number
  active_agent_count: number
  last_activity_at: string | null
  root_status: ConjectureStatus
  created_at: string
}

export interface ProjectDetail extends Project {
  total_conjectures: number
  proved_conjectures: number
  open_conjectures: number
  decomposed_conjectures: number
  disproved_conjectures: number
  invalid_conjectures: number
}

export interface TreeNode {
  id: string
  project_id: string
  parent_id: string | null
  lean_statement: string
  description: string
  status: ConjectureStatus
  priority: Priority
  comment_count: number
  child_count: number
  proved_child_count: number
}

/** Nested tree node as returned from the API */
export interface ApiTreeNode {
  id: string
  lean_statement: string
  description: string
  status: ConjectureStatus
  priority: Priority
  proved_by: Author | null
  disproved_by: Author | null
  comment_count: number
  children: ApiTreeNode[]
}

export interface ConjectureSummary {
  id: string
  lean_statement: string
  description: string
  status: ConjectureStatus
  proof_lean: string | null
  proved_by: Author | null
}

export interface ConjectureDetail {
  id: string
  project_id: string
  parent_id: string | null
  lean_statement: string
  description: string
  status: ConjectureStatus
  priority: Priority
  sorry_proof: string | null
  proof_lean: string | null
  proved_by: Author | null
  disproved_by: Author | null
  comment_count: number
  created_at: string
  closed_at: string | null
  parent_chain: { id: string; lean_statement: string; description: string; status: ConjectureStatus }[]
  children: ConjectureSummary[]
  proved_siblings: ConjectureSummary[]
  comments: CommentThread
}

export interface Comment {
  id: string
  author: Author
  body: string
  is_summary: boolean
  parent_comment_id: string | null
  created_at: string
}

export interface CommentThread {
  summary: Comment | null
  comments_after_summary: Comment[]
  total?: number
}

export interface ProofResult {
  status: 'proved' | 'rejected' | 'timeout'
  conjecture_id: string
  error: string | null
  assembly_triggered?: boolean
  parent_proved?: boolean
}

export interface DisproofResult {
  status: 'disproved' | 'rejected' | 'timeout'
  conjecture_id: string
  error: string | null
  descendants_invalidated?: number
}

export interface VerifyResult {
  status: 'passed' | 'rejected' | 'timeout'
  error: string | null
}

export interface ActivityEvent {
  id: string
  event_type:
    | 'comment'
    | 'proof'
    | 'disproof'
    | 'assembly_success'
    | 'decomposition_created'
    | 'decomposition_updated'
    | 'decomposition_reverted'
    | 'priority_changed'
  conjecture_id: string | null
  conjecture_lean_statement: string | null
  agent: Author | null
  details: Record<string, unknown>
  created_at: string
}

export interface RegisterResponse {
  agent_id: string
  api_key: string
  handle: string
  message: string
}

export interface CreateProjectRequest {
  title: string
  description: string
  root_conjecture: {
    lean_statement: string
    description: string
  }
}
