import type { Problem } from '../../types/index'
import ProblemCard from './ProblemCard'
import SkeletonCard from '../ui/SkeletonCard'
import EmptyState from '../ui/EmptyState'
import ErrorBanner from '../ui/ErrorBanner'

interface ProblemListProps {
  problems: Problem[] | undefined
  isLoading: boolean
  error: Error | undefined
  onRetry?: () => void
}

export default function ProblemList({ problems, isLoading, error, onRetry }: ProblemListProps) {
  if (error) {
    return <ErrorBanner message="Failed to load problems." onRetry={onRetry} />
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (!problems || problems.length === 0) {
    return (
      <EmptyState
        message="No problems posted yet. Be the first!"
        actionLabel="Create Problem"
        actionTo="/submit"
      />
    )
  }

  return (
    <div className="space-y-3">
      {problems.map((p) => (
        <ProblemCard key={p.id} problem={p} />
      ))}
    </div>
  )
}
