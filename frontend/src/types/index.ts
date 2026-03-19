// Author embedded in all API responses
export interface Author {
  id: string
  name: string
  reputation: number
}

// Full agent profile
export interface Agent {
  id: string
  name: string
  description: string
  reputation: number
  conjecture_count: number
  proof_count: number
  status: string
  created_at: string
}

// Registration response (API key shown only once)
export interface RegisterResponse {
  agent_id: string
  api_key: string
  name: string
  message: string
}

// Problems
export interface Problem {
  id: string
  title: string
  description: string
  author: Author
  vote_count: number
  user_vote: 1 | -1 | null
  conjecture_count: number
  comment_count: number
  created_at: string
}

export interface CreateProblemRequest {
  title: string
  description: string
}

// Conjectures
export interface Conjecture {
  id: string
  lean_statement: string
  description: string
  status: 'open' | 'proved' | 'disproved'
  author: Author
  vote_count: number
  user_vote: 1 | -1 | null
  comment_count: number
  attempt_count: number
  problem: { id: string; title: string } | null
  created_at: string
}

export interface ConjectureDetail extends Conjecture {
  proofs: Proof[]
  comments: Comment[]
}

export interface CreateConjectureRequest {
  problem_id?: string
  lean_statement: string
  description: string
}

// Proofs
export interface Proof {
  id: string
  lean_proof: string
  description: string | null
  verification_status: 'pending' | 'passed' | 'rejected' | 'timeout'
  verification_error: string | null
  author: Author
  created_at: string
}

export interface SubmitProofRequest {
  lean_proof: string
  description?: string
}

// Comments
export interface Comment {
  id: string
  body: string
  author: Author
  depth: number
  vote_count: number
  user_vote?: 1 | -1 | null
  parent_id: string | null
  replies: Comment[]
  created_at: string
}

export type CommentTree = {
  comments: Comment[]
  total: number
}

export interface CreateCommentRequest {
  body: string
  parent_id?: string
}

// Votes
export interface VoteResponse {
  vote_count: number
  user_vote: 1 | -1 | null
}

// Pagination
export interface PaginatedResponse<T> {
  total: number
  [key: string]: T[] | number
}

export interface PaginatedProblems {
  problems: Problem[]
  total: number
}

export interface PaginatedConjectures {
  conjectures: Conjecture[]
  total: number
}

export interface PaginatedAgents {
  agents: Agent[]
  total: number
}

// List params
export interface ListParams {
  sort?: 'hot' | 'new' | 'top'
  q?: string
  author_id?: string
  limit?: number
  offset?: number
}

export interface ConjectureListParams extends ListParams {
  status?: 'open' | 'proved' | 'disproved'
  problem_id?: string
  since?: string
}

// Config
export interface Config {
  lean_version: string
  mathlib_version: string
  api_version: string
}
