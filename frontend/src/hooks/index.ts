import useSWR from 'swr'
import { api } from '../api/client'

export function useProblems() {
  return useSWR('problems', () => api.getProblems())
}

export function useProblem(id: string) {
  return useSWR(['problem', id], () => api.getProblem(id))
}

export function useProblemTree(problemId: string) {
  return useSWR(['problem-tree', problemId], () => api.getProblemTree(problemId))
}

export function useProblemOverview(problemId: string) {
  return useSWR(['problem-overview', problemId], () => api.getProblemOverview(problemId))
}

export function useConjecture(id: string) {
  return useSWR(['conjecture', id], () => api.getConjecture(id))
}

export function useProblemComments(problemId: string) {
  return useSWR(['problem-comments', problemId], () => api.getProblemComments(problemId))
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

export function useProblemActivity(problemId: string, limit = 50) {
  return useSWR(['problem-activity', problemId], () =>
    api.getProblemActivity(problemId, limit),
  )
}

export function useClaimInfo(token: string) {
  return useSWR(['claim-info', token], () => api.getClaimInfo(token))
}

export function useStats() {
  return useSWR('platform-stats', () => api.getStats())
}
