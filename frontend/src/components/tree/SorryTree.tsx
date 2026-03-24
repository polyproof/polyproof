import { Link } from 'react-router-dom'
import { ChevronRight, ChevronDown, Check, MessageSquare } from 'lucide-react'
import { cn, truncate } from '../../lib/utils'
import type { FlatSorryNode } from '../../lib/utils'
import { ROUTES } from '../../lib/constants'
import { useUIStore } from '../../store/ui'
import type { Priority } from '../../types'

const statusDot: Record<string, string> = {
  open: 'bg-gray-400',
  decomposed: 'bg-blue-500',
  filled: 'bg-green-500',
  filled_externally: 'bg-emerald-400',
  invalid: 'bg-gray-300',
}

const priorityIndicator: Record<Priority, string> = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-400',
  normal: 'border-l-transparent',
  low: 'border-l-transparent',
}

interface SorryTreeProps {
  tree: FlatSorryNode[]
}

export default function SorryTree({ tree }: SorryTreeProps) {
  const { treeCollapsed, toggleCollapse } = useUIStore()

  // Build parent -> children map
  const childrenMap = new Map<string | undefined, FlatSorryNode[]>()
  for (const node of tree) {
    const parentId = node.parent_sorry_id
    if (!childrenMap.has(parentId)) {
      childrenMap.set(parentId, [])
    }
    childrenMap.get(parentId)!.push(node)
  }

  const rootNodes = childrenMap.get(undefined) ?? []

  function renderNode(node: FlatSorryNode, depth: number): React.ReactNode {
    const children = childrenMap.get(node.id) ?? []
    const isCollapsed = treeCollapsed.has(node.id)
    const hasChildren = children.length > 0
    const isInvalid = node.status === 'invalid'

    const label = node.declaration_name + (node.sorry_index > 0 ? ` #${node.sorry_index}` : '')

    return (
      <div key={node.id}>
        <div
          className={cn(
            'flex items-center gap-2 border-b border-gray-100 border-l-2 py-2.5 pr-3 transition-colors hover:bg-gray-50',
            priorityIndicator[node.priority as Priority] ?? 'border-l-transparent',
            isInvalid && 'opacity-50',
          )}
          style={{ paddingLeft: `${depth * 24 + 12}px` }}
        >
          {/* Collapse toggle */}
          {hasChildren ? (
            <button
              onClick={() => toggleCollapse(node.id)}
              className="shrink-0 rounded p-0.5 hover:bg-gray-200"
            >
              {isCollapsed ? (
                <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
              )}
            </button>
          ) : (
            <span className="w-[22px] shrink-0" />
          )}

          {/* Status dot */}
          <div className={cn('h-2.5 w-2.5 shrink-0 rounded-full', statusDot[node.status] ?? 'bg-gray-400')} />

          {/* Declaration name (clickable) */}
          <Link
            to={ROUTES.SORRY(node.id)}
            className={cn(
              'min-w-0 flex-1 font-mono text-sm hover:text-blue-600',
              isInvalid && 'text-gray-400 line-through',
              !isInvalid && 'text-gray-800',
            )}
          >
            {truncate(label, 60)}
          </Link>

          {/* Goal state preview */}
          <span className="hidden text-xs text-gray-400 sm:inline">
            {truncate(node.goal_state, 40)}
          </span>

          {/* Status icons */}
          {(node.status === 'filled' || node.status === 'filled_externally') && (
            <Check className="h-3.5 w-3.5 shrink-0 text-green-600" />
          )}

          {/* Comment count */}
          {node.comment_count > 0 && (
            <span className="flex shrink-0 items-center gap-0.5 text-xs text-gray-400">
              <MessageSquare className="h-3 w-3" />
              {node.comment_count}
            </span>
          )}

          {/* Active agents */}
          {node.active_agents > 0 && (
            <span className="shrink-0 text-xs text-gray-400">
              {node.active_agents} working
            </span>
          )}
        </div>

        {/* Children */}
        {hasChildren && !isCollapsed && children.map((child) => renderNode(child, depth + 1))}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white">
      {rootNodes.map((node) => renderNode(node, 0))}
    </div>
  )
}
