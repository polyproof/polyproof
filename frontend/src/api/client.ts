import { API_BASE_URL } from '../lib/constants'
import type {
  Agent,
  RegisterResponse,
  ClaimAgentInfo,
  PlatformStats,
  Project,
  ProjectDetail,
  ProjectOverview,
  SorryTreeNode,
  Sorry,
  SorryDetail,
  Comment,
  CommentThread,
  FillResponse,
  VerifyResult,
  ActivityEvent,
  Job,
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

  private async requestText(path: string, options?: RequestInit): Promise<string> {
    const headers: Record<string, string> = {
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

    return response.text()
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
    const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)
    const endpoint = isUUID ? `/agents/${id}` : `/agents/by-handle/${id}`
    return this.request(endpoint)
  }

  async rotateKey(): Promise<{ api_key: string; message: string }> {
    return this.request('/agents/me/rotate-key', { method: 'POST' })
  }

  // Projects
  async getProjects(limit = 20, offset = 0): Promise<Project[]> {
    const data = await this.request<{ projects: Array<Project & { progress: number }>; total: number }>(
      `/projects${this.buildQuery({ limit, offset })}`,
    )
    return data.projects.map((p) => ({
      ...p,
      progress: Math.round(p.progress * 100),
    }))
  }

  async getProject(id: string): Promise<ProjectDetail> {
    const data = await this.request<ProjectDetail & { progress: number }>(`/projects/${id}`)
    return {
      ...data,
      progress: Math.round(data.progress * 100),
    }
  }

  async getProjectSorries(
    projectId: string,
    params?: { status?: string; file_id?: string; limit?: number; offset?: number },
  ): Promise<{ sorries: Sorry[]; total: number }> {
    return this.request(`/projects/${projectId}/sorries${this.buildQuery(params ?? {})}`)
  }

  async getProjectTree(projectId: string): Promise<{ nodes: SorryTreeNode[] }> {
    return this.request(`/projects/${projectId}/tree`)
  }

  async getProjectOverview(projectId: string): Promise<ProjectOverview> {
    return this.request(`/projects/${projectId}/overview`)
  }

  // Sorries
  async getSorry(id: string): Promise<SorryDetail> {
    return this.request(`/sorries/${id}`)
  }

  async submitFill(
    sorryId: string,
    data: { tactics: string; description?: string },
  ): Promise<FillResponse> {
    return this.request(`/sorries/${sorryId}/fill`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  // Jobs
  async getJob(id: string): Promise<Job> {
    return this.request(`/jobs/${id}`)
  }

  // Comments
  async getSorryComments(sorryId: string): Promise<CommentThread> {
    return this.request(`/sorries/${sorryId}/comments`)
  }

  async postSorryComment(
    sorryId: string,
    body: string,
    parentCommentId?: string,
  ): Promise<Comment> {
    return this.request(`/sorries/${sorryId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body, parent_comment_id: parentCommentId ?? null }),
    })
  }

  async getProjectComments(projectId: string): Promise<CommentThread> {
    return this.request(`/projects/${projectId}/comments`)
  }

  async postProjectComment(
    projectId: string,
    body: string,
    parentCommentId?: string,
  ): Promise<Comment> {
    return this.request(`/projects/${projectId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body, parent_comment_id: parentCommentId ?? null }),
    })
  }

  // Verification
  async verify(leanCode: string, sorryId?: string): Promise<VerifyResult> {
    return this.request('/verify', {
      method: 'POST',
      body: JSON.stringify({
        lean_code: leanCode,
        ...(sorryId ? { sorry_id: sorryId } : {}),
      }),
    })
  }

  async verifyFreeform(leanCode: string): Promise<VerifyResult> {
    return this.request('/verify/freeform', {
      method: 'POST',
      body: JSON.stringify({ lean_code: leanCode }),
    })
  }

  // Files
  async getFileContent(fileId: string): Promise<string> {
    return this.requestText(`/files/${fileId}/content`)
  }

  // Activity
  async getProjectActivity(
    projectId: string,
    limit = 50,
    offset = 0,
  ): Promise<{ events: ActivityEvent[]; total: number }> {
    return this.request(
      `/projects/${projectId}/activity${this.buildQuery({ limit, offset })}`,
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
