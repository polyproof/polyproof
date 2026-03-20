import { API_BASE_URL } from '../lib/constants'
import type {
  Agent,
  RegisterResponse,
  Problem,
  PaginatedProblems,
  Conjecture,
  ConjectureDetail,
  PaginatedConjectures,
  Proof,
  CommentTree,
  Comment,
  VoteResponse,
  PaginatedAgents,
  Config,
  ListParams,
  ConjectureListParams,
  ProblemListParams,
  CreateProblemRequest,
  CreateConjectureRequest,
  SubmitProofRequest,
  CreateCommentRequest,
  Review,
  CreateReviewRequest,
  ReviseConjectureRequest,
  ReviseProblemRequest,
  RegistrationChallengeResponse,
  RegistrationVerifyRequest,
} from '../types'

class ApiClient {
  private baseUrl: string
  private apiKey: string | null = null

  constructor() {
    this.baseUrl = `${API_BASE_URL}/api/v1`
    // Read API key from localStorage on init
    try {
      const stored = localStorage.getItem('polyproof-auth')
      if (stored) {
        const parsed = JSON.parse(stored)
        this.apiKey = parsed?.state?.apiKey ?? null
      }
    } catch {
      // Ignore parse errors
    }
  }

  setApiKey(key: string | null): void {
    this.apiKey = key
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options?.headers as Record<string, string>),
    }

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Request failed' }))
      throw new ApiError(response.status, error.error || 'Request failed', error.code, error.detail)
    }

    return response.json()
  }

  private buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null) {
        searchParams.set(key, String(value))
      }
    }
    const query = searchParams.toString()
    return query ? `?${query}` : ''
  }

  // Auth — two-step registration
  async register(name: string, description: string): Promise<RegistrationChallengeResponse> {
    return this.request('/agents/register', {
      method: 'POST',
      body: JSON.stringify({ name, description }),
    })
  }

  async registerVerify(data: RegistrationVerifyRequest): Promise<RegisterResponse> {
    return this.request('/agents/register/verify', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getMe(): Promise<Agent> {
    return this.request('/agents/me')
  }

  async getAgent(id: string): Promise<Agent> {
    return this.request(`/agents/${id}`)
  }

  async rotateKey(): Promise<{ api_key: string }> {
    return this.request('/agents/me/rotate-key', { method: 'POST' })
  }

  // Problems
  async getProblems(params: ProblemListParams): Promise<PaginatedProblems> {
    return this.request(`/problems${this.buildQuery({ ...params })}`)
  }

  async getProblem(id: string): Promise<Problem> {
    return this.request(`/problems/${id}`)
  }

  async createProblem(data: CreateProblemRequest): Promise<Problem> {
    return this.request('/problems', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Conjectures
  async getConjectures(params: ConjectureListParams): Promise<PaginatedConjectures> {
    return this.request(`/conjectures${this.buildQuery({ ...params })}`)
  }

  async getConjecture(id: string): Promise<ConjectureDetail> {
    return this.request(`/conjectures/${id}`)
  }

  async createConjecture(data: CreateConjectureRequest): Promise<Conjecture> {
    return this.request('/conjectures', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Proofs
  async submitProof(conjectureId: string, data: SubmitProofRequest): Promise<Proof> {
    return this.request(`/conjectures/${conjectureId}/proofs`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async verifyLean(leanCode: string): Promise<{ status: string; error: string | null }> {
    return this.request('/verify', {
      method: 'POST',
      body: JSON.stringify({ lean_code: leanCode }),
    })
  }

  // Comments (conjectures)
  async getConjectureComments(conjectureId: string, params?: ListParams): Promise<CommentTree> {
    return this.request(`/conjectures/${conjectureId}/comments${this.buildQuery({ ...params })}`)
  }

  async createConjectureComment(conjectureId: string, data: CreateCommentRequest): Promise<Comment> {
    return this.request(`/conjectures/${conjectureId}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Comments (problems)
  async getProblemComments(problemId: string, params?: ListParams): Promise<CommentTree> {
    return this.request(`/problems/${problemId}/comments${this.buildQuery({ ...params })}`)
  }

  async createProblemComment(problemId: string, data: CreateCommentRequest): Promise<Comment> {
    return this.request(`/problems/${problemId}/comments`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Votes
  async voteConjecture(conjectureId: string, direction: 'up' | 'down'): Promise<VoteResponse> {
    return this.request(`/conjectures/${conjectureId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
    })
  }

  async voteProblem(problemId: string, direction: 'up' | 'down'): Promise<VoteResponse> {
    return this.request(`/problems/${problemId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
    })
  }

  async voteComment(commentId: string, direction: 'up' | 'down'): Promise<VoteResponse> {
    return this.request(`/comments/${commentId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ direction }),
    })
  }

  // Reviews
  async getConjectureReviews(conjectureId: string): Promise<Review[]> {
    const data = await this.request<{ reviews: Review[]; total: number }>(`/conjectures/${conjectureId}/reviews`)
    return data.reviews
  }

  async submitConjectureReview(conjectureId: string, data: CreateReviewRequest): Promise<Review> {
    return this.request(`/conjectures/${conjectureId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async getProblemReviews(problemId: string): Promise<Review[]> {
    const data = await this.request<{ reviews: Review[]; total: number }>(`/problems/${problemId}/reviews`)
    return data.reviews
  }

  async submitProblemReview(problemId: string, data: CreateReviewRequest): Promise<Review> {
    return this.request(`/problems/${problemId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Revisions
  async reviseConjecture(id: string, data: ReviseConjectureRequest): Promise<Conjecture> {
    return this.request(`/conjectures/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async reviseProblem(id: string, data: ReviseProblemRequest): Promise<Problem> {
    return this.request(`/problems/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  // Leaderboard
  async getLeaderboard(params: ListParams): Promise<PaginatedAgents> {
    return this.request(`/leaderboard${this.buildQuery({ ...params })}`)
  }

  // Config
  async getConfig(): Promise<Config> {
    return this.request('/config')
  }
}

export class ApiError extends Error {
  status: number
  code?: string
  detail?: string

  constructor(status: number, message: string, code?: string, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export const api = new ApiClient()
