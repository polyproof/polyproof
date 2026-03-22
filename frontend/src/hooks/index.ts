import useSWR from 'swr'
import { api } from '../api/client'

export function useProjects() {
  return useSWR('projects', () => api.getProjects())
}

export function useProject(id: string) {
  return useSWR(['project', id], () => api.getProject(id))
}

export function useProjectTree(projectId: string) {
  return useSWR(['project-tree', projectId], () => api.getProjectTree(projectId))
}

export function useProjectOverview(projectId: string) {
  return useSWR(['project-overview', projectId], () => api.getProjectOverview(projectId))
}

export function useConjecture(id: string) {
  return useSWR(['conjecture', id], () => api.getConjecture(id))
}

export function useProjectComments(projectId: string) {
  return useSWR(['project-comments', projectId], () => api.getProjectComments(projectId))
}

export function useConjectureComments(conjectureId: string) {
  return useSWR(['conjecture-comments', conjectureId], () =>
    api.getConjectureComments(conjectureId),
  )
}

export function useAgent(agentId: string) {
  return useSWR(['agent', agentId], () => api.getAgent(agentId))
}

export function useLeaderboard() {
  return useSWR('leaderboard', () => api.getLeaderboard())
}

export function useProjectActivity(projectId: string, limit = 50) {
  return useSWR(['project-activity', projectId], () =>
    api.getProjectActivity(projectId, limit),
  )
}
