export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const CONJECTURE_STATUS = {
  OPEN: 'open',
  PROVED: 'proved',
  DISPROVED: 'disproved',
} as const

export const VERIFICATION_STATUS = {
  PENDING: 'pending',
  PASSED: 'passed',
  REJECTED: 'rejected',
  TIMEOUT: 'timeout',
} as const

export const SORT_OPTIONS = {
  HOT: 'hot',
  NEW: 'new',
  TOP: 'top',
} as const

export const STATUS_FILTER_OPTIONS = ['all', 'open', 'proved', 'disproved'] as const

export const DEFAULT_PAGE_SIZE = 20
export const MAX_PAGE_SIZE = 100
export const MAX_COMMENT_DEPTH = 10
