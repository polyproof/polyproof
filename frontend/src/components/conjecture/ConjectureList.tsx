import type { Conjecture } from '../../types/index'
import ConjectureCard from './ConjectureCard'
import SkeletonCard from '../ui/SkeletonCard'
import EmptyState from '../ui/EmptyState'
import ErrorBanner from '../ui/ErrorBanner'

interface ConjectureListProps {
  conjectures: Conjecture[] | undefined
  isLoading: boolean
  error: Error | undefined
  onRetry?: () => void
  showProblemLink?: boolean
  emptyMessage?: string
  emptyActionLabel?: string
  emptyActionTo?: string
}

export default function ConjectureList({
  conjectures,
  isLoading,
  error,
  onRetry,
  showProblemLink = true,
  emptyMessage = 'No conjectures yet.',
  emptyActionLabel,
  emptyActionTo,
}: ConjectureListProps) {
  if (error) {
    return <ErrorBanner message="Failed to load conjectures." onRetry={onRetry} />
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

  if (!conjectures || conjectures.length === 0) {
    return (
      <EmptyState
        message={emptyMessage}
        actionLabel={emptyActionLabel}
        actionTo={emptyActionTo}
      />
    )
  }

  return (
    <div className="space-y-3">
      {conjectures.map((c) => (
        <ConjectureCard key={c.id} conjecture={c} showProblemLink={showProblemLink} />
      ))}
    </div>
  )
}
