import { cn } from '../../lib/utils'

interface PendingBannerProps {
  reviewStatus: 'pending_review' | 'review_rejected'
  version: number
  reviewCount?: number
  minReviews?: number
}

export default function PendingBanner({
  reviewStatus,
  version,
  reviewCount = 0,
  minReviews = 3,
}: PendingBannerProps) {
  const isPending = reviewStatus === 'pending_review'
  const remaining = Math.max(0, minReviews - reviewCount)

  return (
    <div
      className={cn(
        'rounded-lg border px-4 py-3 text-sm font-medium',
        isPending
          ? 'border-amber-300 bg-amber-50 text-amber-800'
          : 'border-red-300 bg-red-50 text-red-800',
      )}
    >
      {isPending ? (
        <>
          PENDING REVIEW — Version {version} — {reviewCount}/{minReviews}{' '}
          {reviewCount === 1 ? 'review' : 'reviews'}
          {remaining > 0 && `, ${remaining} more needed`}
        </>
      ) : (
        <>REJECTED AFTER REVIEW — Version {version}</>
      )}
    </div>
  )
}
