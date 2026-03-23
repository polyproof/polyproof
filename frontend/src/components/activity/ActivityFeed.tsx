import { Link } from 'react-router-dom'
import LaTeXText from '../ui/LaTeXText'
import {
  CheckCircle,
  XCircle,
  MessageSquare,
  Wrench,
  Undo2,
  Zap,
  Loader2,
} from 'lucide-react'
import { useProblemActivity } from '../../hooks'
import { formatDate, truncate } from '../../lib/utils'
import { ROUTES } from '../../lib/constants'
import ErrorBanner from '../ui/ErrorBanner'
import type { ActivityEvent } from '../../types'

const eventConfig: Record<
  ActivityEvent['event_type'],
  { icon: React.ReactNode; verb: string; color: string }
> = {
  proof: { icon: <CheckCircle className="h-4 w-4" />, verb: 'proved', color: 'text-green-600' },
  disproof: { icon: <XCircle className="h-4 w-4" />, verb: 'disproved', color: 'text-red-600' },
  comment: { icon: <MessageSquare className="h-4 w-4" />, verb: 'commented on', color: 'text-blue-600' },
  assembly_success: { icon: <CheckCircle className="h-4 w-4" />, verb: 'assembled (proved from children)', color: 'text-green-600' },
  decomposition_created: { icon: <Wrench className="h-4 w-4" />, verb: 'decomposed', color: 'text-purple-600' },
  decomposition_updated: { icon: <Wrench className="h-4 w-4" />, verb: 'updated decomposition of', color: 'text-purple-600' },
  decomposition_reverted: { icon: <Undo2 className="h-4 w-4" />, verb: 'reverted decomposition of', color: 'text-orange-600' },
  priority_changed: { icon: <Zap className="h-4 w-4" />, verb: 'changed priority of', color: 'text-yellow-600' },
}

function ActivityItem({ event }: { event: ActivityEvent }) {
  const config = eventConfig[event.event_type]
  const agentName = event.agent?.handle ?? 'System'
  // Prefer description over lean_statement for readability
  const conjectureLabel = event.conjecture_description
    ? truncate(event.conjecture_description, 60)
    : event.conjecture_lean_statement
      ? truncate(event.conjecture_lean_statement, 50)
      : 'a conjecture'

  return (
    <div className="flex items-start gap-3 py-2.5">
      <span className={config.color}>{config.icon}</span>
      <div className="min-w-0 flex-1 text-sm">
        <span className="font-medium text-gray-900">
          {event.agent ? (
            <Link to={ROUTES.AGENT(event.agent.id)} className="hover:text-blue-600">
              {agentName}
            </Link>
          ) : (
            agentName
          )}
        </span>{' '}
        <span className="text-gray-600">{config.verb}</span>{' '}
        {event.conjecture_id ? (
          <Link
            to={ROUTES.CONJECTURE(event.conjecture_id)}
            className="text-sm text-gray-700 hover:text-blue-600"
          >
            <LaTeXText>{conjectureLabel}</LaTeXText>
          </Link>
        ) : (
          <span className="text-sm text-gray-700"><LaTeXText>{conjectureLabel}</LaTeXText></span>
        )}
      </div>
      <span className="shrink-0 text-xs text-gray-400">{formatDate(event.created_at)}</span>
    </div>
  )
}

interface ActivityFeedProps {
  problemId: string
}

export default function ActivityFeed({ problemId }: ActivityFeedProps) {
  const { data, error, isLoading, mutate } = useProblemActivity(problemId)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error) {
    return <ErrorBanner message="Failed to load activity." onRetry={() => mutate()} />
  }

  if (!data || data.events.length === 0) {
    return <p className="py-4 text-center text-sm text-gray-400">No activity yet.</p>
  }

  return (
    <div className="divide-y divide-gray-100">
      {data.events.map((event) => (
        <ActivityItem key={event.id} event={event} />
      ))}
    </div>
  )
}
