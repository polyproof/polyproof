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
import { useConjecture, useConjectureComments } from '../hooks/index'
import { api } from '../api/client'
import { useSWRConfig } from 'swr'
import { formatDate } from '../lib/utils'

export default function ConjecturePage() {
  const { id } = useParams<{ id: string }>()
  const { mutate: globalMutate } = useSWRConfig()
  const { data: conjecture, error, isLoading, mutate: mutateConjecture } = useConjecture(id!)
  const { data: commentsData, mutate: mutateComments } = useConjectureComments(id!)

  const handleVote = async (direction: 'up' | 'down') => {
    if (!id) return
    try {
      await api.voteConjecture(id, direction)
      mutateConjecture()
      globalMutate((key: unknown) => Array.isArray(key) && key[0] === 'conjectures', undefined, { revalidate: true })
    } catch {
      // Vote failed
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
            </div>
          </div>
        </div>

        {/* Proofs */}
        <div id="proofs" className="space-y-3">
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
        </div>

        {/* Submit proof form */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Submit a Proof</h2>
          <ProofSubmitForm conjectureId={id!} />
        </div>

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
