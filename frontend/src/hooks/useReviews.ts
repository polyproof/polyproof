import useSWR from 'swr'
import { api } from '../api/client'

export function useConjectureReviews(conjectureId: string) {
  return useSWR(
    ['conjecture-reviews', conjectureId],
    () => api.getConjectureReviews(conjectureId),
  )
}

export function useProblemReviews(problemId: string) {
  return useSWR(
    ['problem-reviews', problemId],
    () => api.getProblemReviews(problemId),
  )
}
