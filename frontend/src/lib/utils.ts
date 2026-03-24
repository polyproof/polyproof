import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { SorryTreeNode } from '../types'

/** Merge Tailwind classes with clsx */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format an ISO date string as a relative time */
export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSeconds < 60) return 'just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
}

/** Truncate a string to a maximum length, adding ellipsis if needed. */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return str.slice(0, maxLength - 1).trimEnd() + '\u2026'
}

/**
 * Flatten nested sorry tree into a flat array with parent references.
 * Used for building the tree view.
 */
export interface FlatSorryNode {
  id: string
  declaration_name: string
  sorry_index: number
  goal_state: string
  status: string
  priority: string
  filled_by?: string
  active_agents: number
  comment_count: number
  parent_sorry_id?: string
  child_count: number
  filled_child_count: number
}

export function flattenSorryTree(
  nodes: SorryTreeNode[],
  parentId?: string,
): FlatSorryNode[] {
  const result: FlatSorryNode[] = []

  for (const node of nodes) {
    const filledChildCount = node.children.filter(
      (c) => c.status === 'filled' || c.status === 'filled_externally',
    ).length

    result.push({
      id: node.id,
      declaration_name: node.declaration_name,
      sorry_index: node.sorry_index,
      goal_state: node.goal_state,
      status: node.status,
      priority: node.priority,
      filled_by: node.filled_by,
      active_agents: node.active_agents,
      comment_count: node.comment_count,
      parent_sorry_id: parentId,
      child_count: node.children.length,
      filled_child_count: filledChildCount,
    })

    if (node.children.length > 0) {
      result.push(...flattenSorryTree(node.children, node.id))
    }
  }

  return result
}
