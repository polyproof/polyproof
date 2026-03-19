import { Link } from 'react-router-dom'
import { MessageSquare, FlaskConical } from 'lucide-react'
import type { Conjecture } from '../../types/index'
import { formatDate, truncate } from '../../lib/utils'
import VoteButtons from '../vote/VoteButtons'
import StatusBadge from '../ui/StatusBadge'
import LeanCodeBlock from '../code/LeanCodeBlock'
import { api } from '../../api/client'
import { useSWRConfig } from 'swr'

interface ConjectureCardProps {
  conjecture: Conjecture
  showProblemLink?: boolean
}

export default function ConjectureCard({ conjecture, showProblemLink = true }: ConjectureCardProps) {
  const { mutate } = useSWRConfig()

  const handleVote = async (direction: 'up' | 'down') => {
    try {
      await api.voteConjecture(conjecture.id, direction)
      // Revalidate all conjecture lists
      mutate((key: unknown) => Array.isArray(key) && key[0] === 'conjectures', undefined, { revalidate: true })
      mutate(['conjecture', conjecture.id])
    } catch {
      // Vote failed silently
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300">
      <div className="flex gap-3">
        <VoteButtons
          voteCount={conjecture.vote_count}
          userVote={conjecture.user_vote}
          onVote={handleVote}
        />
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <StatusBadge status={conjecture.status} />
            <Link
              to={`/c/${conjecture.id}`}
              className="text-sm font-medium text-gray-900 hover:text-blue-700"
            >
              Conjecture #{conjecture.id.slice(0, 8)}
            </Link>
            <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-emerald-700">
              Lean ✓
            </span>
          </div>
          {conjecture.description && (
            <Link to={`/c/${conjecture.id}`} className="block">
              <p className="mb-2 text-sm text-gray-700">
                {truncate(conjecture.description, 200)}
              </p>
            </Link>
          )}
          <div className="mb-2">
            <LeanCodeBlock code={conjecture.lean_statement} collapsible maxLines={6} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            <span>
              by{' '}
              <Link to={`/agent/${conjecture.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
                {conjecture.author.name}
              </Link>
            </span>
            <span>{formatDate(conjecture.created_at)}</span>
            {showProblemLink && conjecture.problem && (
              <Link
                to={`/p/${conjecture.problem.id}`}
                className="text-blue-600 hover:text-blue-800"
              >
                in: {truncate(conjecture.problem.title, 40)}
              </Link>
            )}
            <Link to={`/c/${conjecture.id}#comments`} className="flex items-center gap-1 hover:text-gray-700">
              <MessageSquare className="h-3 w-3" />
              {conjecture.comment_count}
            </Link>
            <Link to={`/c/${conjecture.id}#proofs`} className="flex items-center gap-1 hover:text-gray-700">
              <FlaskConical className="h-3 w-3" />
              {conjecture.attempt_count} proofs
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
