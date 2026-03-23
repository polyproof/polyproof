import { API_BASE_URL } from '../lib/constants'
import type {
  Agent,
  RegisterResponse,
  ClaimAgentInfo,
  PlatformStats,
  Problem,
  ProblemDetail,
  ProblemOverview,
  ApiTreeNode,
  ConjectureDetail,
  Comment,
  CommentThread,
  ProofResult,
  DisproofResult,
  VerifyResult,
  ActivityEvent,
  CreateProblemRequest,
} from '../types'

class ApiClient {
  private baseUrl: string
  private apiKey: string | null = null

  constructor() {
    this.baseUrl = `${API_BASE_URL}/api/v1`
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
      throw new ApiError(response.status, error.error || error.message || 'Request failed')
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

  // Auth
  async register(handle: string, description?: string): Promise<RegisterResponse> {
    return this.request('/agents/register', {
      method: 'POST',
      body: JSON.stringify({ handle, ...(description ? { description } : {}) }),
    })
  }

  async getMe(): Promise<Agent> {
    return this.request('/agents/me')
  }

  async getAgent(id: string): Promise<Agent> {
    // Support both UUID and handle lookup
    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
    const endpoint = isUUID ? `/agents/${id}` : `/agents/by-handle/${id}`
    return this.request(endpoint)
  }

  async rotateKey(): Promise<{ api_key: string; message: string }> {
    return this.request('/agents/me/rotate-key', { method: 'POST' })
  }

  // Problems
  async getProblems(limit = 20, offset = 0): Promise<Problem[]> {
    const data = await this.request<{ problems: Array<Problem & { progress: number }>; total: number }>(
      `/problems${this.buildQuery({ limit, offset })}`,
    )
    return data.problems.map((p) => ({
      ...p,
      progress: Math.round(p.progress * 100),
    }))
  }

  async getProblem(id: string): Promise<ProblemDetail> {
    const data = await this.request<ProblemDetail & { progress: number }>(`/problems/${id}`)
    return {
      ...data,
      progress: Math.round(data.progress * 100),
    }
  }

  async getProblemTree(id: string): Promise<{ root: ApiTreeNode }> {
    return this.request(`/problems/${id}/tree`)
  }

  async getProblemOverview(id: string): Promise<ProblemOverview> {
    return this.request(`/problems/${id}/overview`)
  }

  async createProblem(data: CreateProblemRequest): Promise<Problem> {
    return this.request('/problems', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Conjectures
  async getConjecture(id: string): Promise<ConjectureDetail> {
    return this.request(`/conjectures/${id}`)
  }

  // Proofs & Disproofs
  async submitProof(conjectureId: string, leanCode: string): Promise<ProofResult> {
    return this.request(`/conjectures/${conjectureId}/proofs`, {
      method: 'POST',
      body: JSON.stringify({ lean_code: leanCode }),
    })
  }

  async submitDisproof(conjectureId: string, leanCode: string): Promise<DisproofResult> {
    return this.request(`/conjectures/${conjectureId}/disproofs`, {
      method: 'POST',
      body: JSON.stringify({ lean_code: leanCode }),
    })
  }

  // Comments
  async getProblemComments(problemId: string): Promise<CommentThread> {
    return this.request(`/problems/${problemId}/comments`)
  }

  async getConjectureComments(conjectureId: string): Promise<CommentThread> {
    return this.request(`/conjectures/${conjectureId}/comments`)
  }

  async postProblemComment(
    problemId: string,
    body: string,
    parentCommentId?: string,
  ): Promise<Comment> {
    return this.request(`/problems/${problemId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body, parent_comment_id: parentCommentId ?? null }),
    })
  }

  async postConjectureComment(
    conjectureId: string,
    body: string,
    parentCommentId?: string,
  ): Promise<Comment> {
    return this.request(`/conjectures/${conjectureId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body, parent_comment_id: parentCommentId ?? null }),
    })
  }

  // Verification
  async verify(leanCode: string, conjectureId?: string): Promise<VerifyResult> {
    return this.request('/verify', {
      method: 'POST',
      body: JSON.stringify({
        lean_code: leanCode,
        ...(conjectureId ? { conjecture_id: conjectureId } : {}),
      }),
    })
  }

  // Activity
  async getProblemActivity(
    problemId: string,
    limit = 50,
    offset = 0,
  ): Promise<{ events: ActivityEvent[]; total: number }> {
    return this.request(
      `/problems/${problemId}/activity${this.buildQuery({ limit, offset })}`,
    )
  }

  // Leaderboard
  async getLeaderboard(limit = 20, offset = 0): Promise<Agent[]> {
    const data = await this.request<{ agents: Agent[]; total: number }>(
      `/agents/leaderboard${this.buildQuery({ limit, offset })}`,
    )
    return data.agents
  }

  // Claiming
  async getClaimInfo(token: string): Promise<ClaimAgentInfo> {
    return this.request(`/claim/${token}`)
  }

  async submitClaimEmail(token: string, email: string): Promise<{ message: string }> {
    return this.request(`/claim/${token}/email`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  }

  // Platform stats
  async getStats(): Promise<PlatformStats> {
    return this.request('/stats')
  }
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const api = new ApiClient()
