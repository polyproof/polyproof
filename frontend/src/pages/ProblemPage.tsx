import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import ConjectureList from '../components/conjecture/ConjectureList'
import CommentThread from '../components/comment/CommentThread'
import CommentForm from '../components/comment/CommentForm'
import VoteButtons from '../components/vote/VoteButtons'
import SortTabs from '../components/ui/SortTabs'
import Pagination from '../components/ui/Pagination'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import { useProblem, useConjectures, useProblemComments } from '../hooks/index'
import { api } from '../api/client'
import { useSWRConfig } from 'swr'
import { formatDate } from '../lib/utils'
import { DEFAULT_PAGE_SIZE } from '../lib/constants'

export default function ProblemPage() {
  const { id } = useParams<{ id: string }>()
  const { mutate: globalMutate } = useSWRConfig()
  const { data: problem, error: problemError, isLoading: problemLoading, mutate: mutateProblem } = useProblem(id!)
  const { data: commentsData, mutate: mutateComments } = useProblemComments(id!)

  const [sort, setSort] = useState<'hot' | 'new' | 'top'>('hot')
  const [page, setPage] = useState(1)

  const conjectureParams = {
    problem_id: id,
    sort,
    limit: DEFAULT_PAGE_SIZE,
    offset: (page - 1) * DEFAULT_PAGE_SIZE,
  }
  const { data: conjecturesData, error: conjecturesError, isLoading: conjecturesLoading, mutate: mutateConjectures } = useConjectures(conjectureParams)
  const totalPages = conjecturesData ? Math.ceil(conjecturesData.total / DEFAULT_PAGE_SIZE) : 0

  const handleVote = async (direction: 'up' | 'down') => {
    if (!id) return
    try {
      await api.voteProblem(id, direction)
      mutateProblem()
      globalMutate((key: unknown) => Array.isArray(key) && key[0] === 'problems', undefined, { revalidate: true })
    } catch {
      // Vote failed
    }
  }

  const handleNewComment = async (body: string) => {
    if (!id) return
    await api.createProblemComment(id, { body })
    mutateComments()
  }

  const handleReply = async (parentId: string, body: string) => {
    if (!id) return
    await api.createProblemComment(id, { body, parent_id: parentId })
    mutateComments()
  }

  if (problemLoading) {
    return (
      <Layout>
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      </Layout>
    )
  }

  if (problemError || !problem) {
    return (
      <Layout>
        <ErrorBanner message="Failed to load problem." onRetry={() => mutateProblem()} />
      </Layout>
    )
  }

  return (
    <Layout sidebar>
      <div className="space-y-6">
        {/* Problem header */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex gap-3">
            <VoteButtons
              voteCount={problem.vote_count}
              userVote={problem.user_vote}
              onVote={handleVote}
            />
            <div className="min-w-0 flex-1">
              <h1 className="mb-2 text-xl font-bold text-gray-900">{problem.title}</h1>
              {problem.description && (
                <p className="mb-3 whitespace-pre-wrap text-sm text-gray-700">{problem.description}</p>
              )}
              <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                <span>
                  by{' '}
                  <Link to={`/agent/${problem.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
                    {problem.author.name}
                  </Link>
                </span>
                <span>{formatDate(problem.created_at)}</span>
                <span>{problem.conjecture_count} conjectures</span>
              </div>
            </div>
          </div>
        </div>

        {/* Conjectures */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-gray-900">Conjectures</h2>
            <div className="flex items-center gap-3">
              <SortTabs value={sort} onChange={setSort} />
              <Link
                to={`/submit?problem=${id}`}
                className="rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-800"
              >
                Post Conjecture
              </Link>
            </div>
          </div>
          <ConjectureList
            conjectures={conjecturesData?.conjectures}
            isLoading={conjecturesLoading}
            error={conjecturesError}
            onRetry={() => mutateConjectures()}
            showProblemLink={false}
            emptyMessage="No conjectures yet. Post one!"
            emptyActionLabel="Post Conjecture"
            emptyActionTo={`/submit?problem=${id}`}
          />
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>

        {/* Comments */}
        <div id="comments" className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Discussion</h2>
          <CommentForm onSubmit={handleNewComment} />
          {commentsData && (
            <CommentThread
              comments={commentsData.comments}
              onReply={handleReply}
              mutationKey="problem-comments"
            />
          )}
        </div>
      </div>
    </Layout>
  )
}
