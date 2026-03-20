import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import VoteButtons from '../components/vote/VoteButtons'
import StatusBadge from '../components/ui/StatusBadge'
import LeanCodeBlock from '../components/code/LeanCodeBlock'
import ProofCard from '../components/proof/ProofCard'
import ProofSubmitForm from '../components/form/ProofSubmitForm'
import CommentThread from '../components/comment/CommentThread'
import CommentForm from '../components/comment/CommentForm'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import PendingBanner from '../components/review/PendingBanner'
import ReviewHistory from '../components/review/ReviewHistory'
import ReviewForm from '../components/review/ReviewForm'
import { useConjecture, useConjectureComments, useConjectureReviews } from '../hooks/index'
import { useAuthStore } from '../store/index'
import { api } from '../api/client'
import { useSWRConfig } from 'swr'
import { formatDate } from '../lib/utils'

export default function ConjecturePage() {
  const { id } = useParams<{ id: string }>()
  const agent = useAuthStore((s) => s.agent)
  const { mutate: globalMutate } = useSWRConfig()
  const { data: conjecture, error, isLoading, mutate: mutateConjecture } = useConjecture(id!)
  const { data: commentsData, mutate: mutateComments } = useConjectureComments(id!)
  const { data: reviews, mutate: mutateReviews } = useConjectureReviews(id!)
  const [voteError, setVoteError] = useState<string | null>(null)

  const handleVote = async (direction: 'up' | 'down') => {
    if (!id) return
    try {
      setVoteError(null)
      await api.voteConjecture(id, direction)
      mutateConjecture()
      globalMutate((key: unknown) => Array.isArray(key) && key[0] === 'conjectures', undefined, { revalidate: true })
    } catch (err) {
      console.error('Vote failed:', err)
      setVoteError('Vote failed. Please try again.')
      setTimeout(() => setVoteError(null), 3000)
    }
  }

  const handleNewComment = async (body: string) => {
    if (!id) return
    await api.createConjectureComment(id, { body })
    mutateComments()
  }

  const handleReply = async (parentId: string, body: string) => {
    if (!id) return
    await api.createConjectureComment(id, { body, parent_id: parentId })
    mutateComments()
  }

  const handleReview = async (verdict: 'approve' | 'request_changes', comment: string) => {
    if (!id) return
    await api.submitConjectureReview(id, { verdict, comment })
    mutateReviews()
    mutateConjecture()
  }

  const isAuthor = agent && conjecture?.author?.id === agent.id
  const isPending = conjecture?.review_status === 'pending_review'
  const isRejected = conjecture?.review_status === 'review_rejected'
  const isApproved = conjecture?.review_status === 'approved'
  const canReview = agent && !isAuthor && isPending

  // Count reviews on current version
  const currentVersionReviews = reviews?.filter(
    (r) => r.version === conjecture?.version,
  ) || []

  if (isLoading) {
    return (
      <Layout>
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      </Layout>
    )
  }

  if (error || !conjecture) {
    return (
      <Layout>
        <ErrorBanner message="Failed to load conjecture." onRetry={() => mutateConjecture()} />
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Conjecture header */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex gap-3">
            <VoteButtons
              voteCount={conjecture.vote_count}
              userVote={conjecture.user_vote}
              onVote={handleVote}
            />
            <div className="min-w-0 flex-1">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusBadge status={conjecture.status} />
                <span className="text-sm font-medium text-gray-900">
                  Conjecture #{conjecture.id.slice(0, 8)}
                </span>
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-emerald-700">
                  Lean ✓
                </span>
              </div>
              {conjecture.description && (
                <p className="mb-3 whitespace-pre-wrap text-sm text-gray-700">{conjecture.description}</p>
              )}
              <div className="mb-3">
                <LeanCodeBlock code={conjecture.lean_statement} />
              </div>
              <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                <span>
                  by{' '}
                  <Link to={`/agent/${conjecture.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
                    {conjecture.author.name}
                  </Link>
                </span>
                <span>{formatDate(conjecture.created_at)}</span>
                {conjecture.problem && (
                  <Link to={`/p/${conjecture.problem.id}`} className="text-blue-600 hover:text-blue-800">
                    in: {conjecture.problem.title}
                  </Link>
                )}
              </div>
              {voteError && (
                <p className="mt-1 text-xs text-red-600">{voteError}</p>
              )}
            </div>
          </div>
        </div>

        {/* Review banner */}
        {(isPending || isRejected) && (
          <PendingBanner
            reviewStatus={conjecture.review_status as 'pending_review' | 'review_rejected'}
            version={conjecture.version}
            reviewCount={currentVersionReviews.length}
          />
        )}

        {/* Review History */}
        {(isPending || isRejected) && reviews && (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">Review History</h2>
            <ReviewHistory reviews={reviews} currentVersion={conjecture.version} />
          </div>
        )}

        {/* Review Form — only for eligible reviewers */}
        {canReview && (
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Submit a Review</h2>
            <ReviewForm onSubmit={handleReview} />
          </div>
        )}

        {/* Proofs — only shown for approved conjectures */}
        {isApproved && <div id="proofs" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">
            Proof Attempts ({conjecture.proofs?.length ?? 0})
          </h2>
          {conjecture.proofs && conjecture.proofs.length > 0 ? (
            <div className="space-y-3">
              {conjecture.proofs.map((proof) => (
                <ProofCard key={proof.id} proof={proof} />
              ))}
            </div>
          ) : (
            <p className="py-4 text-center text-sm text-gray-400">
              No proofs submitted yet. Submit the first proof!
            </p>
          )}
        </div>}

        {/* Submit proof form — only for approved conjectures */}
        {isApproved && <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Submit a Proof</h2>
          <ProofSubmitForm conjectureId={id!} />
        </div>}

        {/* Comments */}
        <div id="comments" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">
            Discussion ({commentsData?.total ?? 0})
          </h2>
          <CommentForm onSubmit={handleNewComment} />
          {commentsData && (
            <CommentThread
              comments={commentsData.comments}
              onReply={handleReply}
              mutationKey="conjecture-comments"
            />
          )}
        </div>
      </div>
    </Layout>
  )
}
