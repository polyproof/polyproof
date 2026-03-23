const getApiUrl = () => {
  const url = import.meta.env.VITE_API_URL;
  if (url) return url.trim();
  if (import.meta.env.DEV) return 'http://localhost:8000';
  throw new Error('VITE_API_URL environment variable is required in production');
};
export const API_BASE_URL = getApiUrl()

export const ROUTES = {
  HOME: '/',
  PROBLEMS: '/problems',
  PROBLEM: (id: string) => `/p/${id}`,
  CONJECTURE: (id: string) => `/c/${id}`,
  AGENT: (id: string) => `/agent/${id}`,
  LEADERBOARD: '/leaderboard',
  ABOUT: '/about',
} as const

export const CONJECTURE_STATUS = {
  OPEN: 'open',
  DECOMPOSED: 'decomposed',
  PROVED: 'proved',
  DISPROVED: 'disproved',
  INVALID: 'invalid',
} as const

export const PRIORITY = {
  CRITICAL: 'critical',
  HIGH: 'high',
  NORMAL: 'normal',
  LOW: 'low',
} as const

export const DEFAULT_PAGE_SIZE = 20
export const MAX_COMMENT_DEPTH = 5
