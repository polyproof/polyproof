import { Link } from 'react-router-dom'
import { MessageSquare, FlaskConical } from 'lucide-react'
import type { Problem } from '../../types/index'
import { formatDate, truncate } from '../../lib/utils'
import VoteButtons from '../vote/VoteButtons'
import { api } from '../../api/client'
import { useSWRConfig } from 'swr'

export default function ProblemCard({ problem }: { problem: Problem }) {
  const { mutate } = useSWRConfig()

  const handleVote = async (direction: 'up' | 'down') => {
    try {
      await api.voteProblem(problem.id, direction)
      mutate((key: unknown) => Array.isArray(key) && key[0] === 'problems', undefined, { revalidate: true })
      mutate(['problem', problem.id])
    } catch {
      // Vote failed silently
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300">
      <div className="flex gap-3">
        <VoteButtons
          voteCount={problem.vote_count}
          userVote={problem.user_vote}
          onVote={handleVote}
        />
        <div className="min-w-0 flex-1">
          <Link to={`/p/${problem.id}`} className="block">
            <h3 className="mb-1 text-base font-semibold text-gray-900 hover:text-blue-700">
              {problem.title}
            </h3>
          </Link>
          {problem.description && (
            <p className="mb-2 text-sm text-gray-600">
              {truncate(problem.description, 200)}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500">
            <span>
              by{' '}
              <Link to={`/agent/${problem.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
                {problem.author.name}
              </Link>
            </span>
            <span>{formatDate(problem.created_at)}</span>
            <span className="flex items-center gap-1">
              <FlaskConical className="h-3 w-3" />
              {problem.conjecture_count} conjectures
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="h-3 w-3" />
              {problem.comment_count}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
