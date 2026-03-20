import { Link } from 'react-router-dom'
import type { Review } from '../../types'
import { formatDate } from '../../lib/utils'
import { cn } from '../../lib/utils'

interface ReviewHistoryProps {
  reviews: Review[]
  currentVersion: number
}

export default function ReviewHistory({ reviews, currentVersion }: ReviewHistoryProps) {
  if (reviews.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-gray-400">
        No reviews yet.
      </p>
    )
  }

  // Group reviews by version
  const byVersion = new Map<number, Review[]>()
  for (const review of reviews) {
    const existing = byVersion.get(review.version) || []
    existing.push(review)
    byVersion.set(review.version, existing)
  }

  const versions = Array.from(byVersion.keys()).sort((a, b) => a - b)

  return (
    <div className="space-y-4">
      {versions.map((version) => {
        const versionReviews = byVersion.get(version) || []
        return (
          <div key={version} className="space-y-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Version {version}
            </h4>
            {versionReviews.map((review) => (
              <div
                key={review.id}
                className="rounded-md border border-gray-200 bg-white p-3"
              >
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-gray-500">
                  <Link
                    to={`/agent/${review.reviewer.id}`}
                    className="font-medium text-gray-700 hover:text-blue-700"
                  >
                    @{review.reviewer.name}
                  </Link>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase',
                      review.verdict === 'approve'
                        ? 'bg-green-100 text-green-700'
                        : 'bg-orange-100 text-orange-700',
                    )}
                  >
                    {review.verdict === 'approve' ? 'Approved' : 'Changes Requested'}
                  </span>
                  <span>{formatDate(review.created_at)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-gray-700">
                  {review.comment}
                </p>
              </div>
            ))}
            {version < currentVersion && (
              <p className="text-xs italic text-gray-400">
                Author revised to v{version + 1}
              </p>
            )}
            {version === currentVersion && versionReviews.length < 3 && (
              <p className="text-xs italic text-gray-400">
                Awaiting {3 - versionReviews.length} more{' '}
                {3 - versionReviews.length === 1 ? 'review' : 'reviews'}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
