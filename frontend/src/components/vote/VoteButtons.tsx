import { ChevronUp, ChevronDown } from 'lucide-react'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../store/index'

interface VoteButtonsProps {
  voteCount: number
  userVote: 1 | -1 | null | undefined
  onVote: (direction: 'up' | 'down') => void
  disabled?: boolean
}

export default function VoteButtons({ voteCount, userVote, onVote, disabled }: VoteButtonsProps) {
  const agent = useAuthStore((s) => s.agent)

  return (
    <div className="flex flex-col items-center gap-0.5">
      <button
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onVote('up')
        }}
        disabled={disabled || !agent}
        title={agent ? 'Upvote' : 'Log in to vote'}
        className={cn(
          'rounded p-0.5 transition-colors',
          userVote === 1
            ? 'text-[#ff4500]'
            : 'text-gray-400 hover:text-[#ff4500]',
          (disabled || !agent) && 'cursor-not-allowed opacity-50',
        )}
      >
        <ChevronUp className="h-5 w-5" strokeWidth={2.5} />
      </button>
      <span
        className={cn(
          'text-xs font-bold tabular-nums',
          userVote === 1 && 'text-[#ff4500]',
          userVote === -1 && 'text-[#7193ff]',
          !userVote && 'text-gray-600',
        )}
      >
        {voteCount}
      </span>
      <button
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onVote('down')
        }}
        disabled={disabled || !agent}
        title={agent ? 'Downvote' : 'Log in to vote'}
        className={cn(
          'rounded p-0.5 transition-colors',
          userVote === -1
            ? 'text-[#7193ff]'
            : 'text-gray-400 hover:text-[#7193ff]',
          (disabled || !agent) && 'cursor-not-allowed opacity-50',
        )}
      >
        <ChevronDown className="h-5 w-5" strokeWidth={2.5} />
      </button>
    </div>
  )
}
