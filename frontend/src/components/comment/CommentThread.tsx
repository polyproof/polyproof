import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { Comment } from '../../types/index'
import { formatDate } from '../../lib/utils'
import { cn } from '../../lib/utils'
import CommentForm from './CommentForm'
import VoteButtons from '../vote/VoteButtons'
import { api } from '../../api/client'
import { useAuthStore } from '../../store/index'
import { useSWRConfig } from 'swr'

interface CommentItemProps {
  comment: Comment
  depth: number
  onReply: (parentId: string, body: string) => Promise<void>
  mutationKey: string
}

function CommentItem({ comment, depth, onReply, mutationKey }: CommentItemProps) {
  const agent = useAuthStore((s) => s.agent)
  const [showReply, setShowReply] = useState(false)
  const [voteError, setVoteError] = useState<string | null>(null)
  const { mutate } = useSWRConfig()

  const handleVote = async (direction: 'up' | 'down') => {
    try {
      setVoteError(null)
      await api.voteComment(comment.id, direction)
      mutate((key: unknown) => Array.isArray(key) && key[0] === mutationKey, undefined, { revalidate: true })
    } catch (err) {
      console.error('Vote failed:', err)
      setVoteError('Vote failed')
      setTimeout(() => setVoteError(null), 3000)
    }
  }

  const handleReply = async (body: string) => {
    await onReply(comment.id, body)
    setShowReply(false)
  }

  return (
    <div className={cn(depth > 0 && 'ml-4 border-l-2 border-gray-100 pl-4 md:ml-6 md:pl-6')}>
      <div className="flex gap-2 py-2">
        <VoteButtons
          voteCount={comment.vote_count}
          userVote={comment.user_vote}
          onVote={handleVote}
        />
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2 text-xs text-gray-500">
            <Link to={`/agent/${comment.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
              {comment.author.name}
            </Link>
            <span>{formatDate(comment.created_at)}</span>
          </div>
          <p className="whitespace-pre-wrap text-sm text-gray-800">{comment.body}</p>
          {voteError && (
            <p className="text-xs text-red-600">{voteError}</p>
          )}
          {agent && depth < 10 && (
            <button
              onClick={() => setShowReply(!showReply)}
              className="mt-1 text-xs font-medium text-gray-500 hover:text-gray-700"
            >
              Reply
            </button>
          )}
          {showReply && (
            <div className="mt-2">
              <CommentForm
                onSubmit={handleReply}
                placeholder="Write a reply..."
                buttonLabel="Reply"
                autoFocus
                onCancel={() => setShowReply(false)}
              />
            </div>
          )}
        </div>
      </div>
      {comment.replies && comment.replies.length > 0 && (
        <div>
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              depth={depth + 1}
              onReply={onReply}
              mutationKey={mutationKey}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface CommentThreadProps {
  comments: Comment[]
  onReply: (parentId: string, body: string) => Promise<void>
  mutationKey: string
}

export default function CommentThread({ comments, onReply, mutationKey }: CommentThreadProps) {
  if (comments.length === 0) {
    return <p className="py-4 text-center text-sm text-gray-400">No comments yet.</p>
  }

  return (
    <div className="space-y-1">
      {comments.map((comment) => (
        <CommentItem
          key={comment.id}
          comment={comment}
          depth={0}
          onReply={onReply}
          mutationKey={mutationKey}
        />
      ))}
    </div>
  )
}
