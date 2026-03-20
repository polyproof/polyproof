const getApiUrl = () => {
  const url = import.meta.env.VITE_API_URL;
  if (url) return url.trim();
  if (import.meta.env.DEV) return 'http://localhost:8000';
  throw new Error('VITE_API_URL environment variable is required in production');
};
export const API_BASE_URL = getApiUrl()

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

export const STATUS_FILTER_OPTIONS = ['all', 'open', 'proved'] as const

export const DEFAULT_PAGE_SIZE = 20
export const MAX_PAGE_SIZE = 100
export const MAX_COMMENT_DEPTH = 10
