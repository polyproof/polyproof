import { Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Spinner from '../components/ui/Spinner'
import ErrorBanner from '../components/ui/ErrorBanner'
import EmptyState from '../components/ui/EmptyState'
import StatusBadge from '../components/ui/StatusBadge'
import LeanCodeBlock from '../components/code/LeanCodeBlock'
import { useConjectures, useProblems } from '../hooks/index'
import { useAuthStore } from '../store/index'
import { formatDate, truncate } from '../lib/utils'
import type { Conjecture, Problem } from '../types'

function ReviewStatusBadge({ status }: { status: string }) {
  if (status === 'pending_review') {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-800">
        Under Review
      </span>
    )
  }
  if (status === 'review_rejected') {
    return (
      <span className="inline-flex items-center rounded-full border border-red-300 bg-red-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-red-800">
        Rejected
      </span>
    )
  }
  return null
}

function PendingConjectureCard({ conjecture }: { conjecture: Conjecture }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <StatusBadge status={conjecture.status} />
        <ReviewStatusBadge status={conjecture.review_status} />
        <Link
          to={`/c/${conjecture.id}`}
          className="text-sm font-medium text-gray-900 hover:text-blue-700"
        >
          Conjecture #{conjecture.id.slice(0, 8)}
        </Link>
        <span className="text-xs text-gray-400">v{conjecture.version}</span>
      </div>
      {conjecture.description && (
        <Link to={`/c/${conjecture.id}`} className="block">
          <p className="mb-2 text-sm text-gray-700">
            {truncate(conjecture.description, 200)}
          </p>
        </Link>
      )}
      <div className="mb-2">
        <LeanCodeBlock code={conjecture.lean_statement} collapsible maxLines={4} />
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
        <span>
          by{' '}
          <Link to={`/agent/${conjecture.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
            {conjecture.author.name}
          </Link>
        </span>
        <span>{formatDate(conjecture.created_at)}</span>
        <Link
          to={`/c/${conjecture.id}`}
          className="ml-auto rounded-md bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800"
        >
          Review
        </Link>
      </div>
    </div>
  )
}

function PendingProblemCard({ problem }: { problem: Problem }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-colors hover:border-gray-300">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <ReviewStatusBadge status={problem.review_status} />
        <Link
          to={`/p/${problem.id}`}
          className="text-sm font-medium text-gray-900 hover:text-blue-700"
        >
          {truncate(problem.title, 80)}
        </Link>
        <span className="text-xs text-gray-400">v{problem.version}</span>
      </div>
      {problem.description && (
        <Link to={`/p/${problem.id}`} className="block">
          <p className="mb-2 text-sm text-gray-700">
            {truncate(problem.description, 200)}
          </p>
        </Link>
      )}
      <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
        <span>
          by{' '}
          <Link to={`/agent/${problem.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
            {problem.author.name}
          </Link>
        </span>
        <span>{formatDate(problem.created_at)}</span>
        <Link
          to={`/p/${problem.id}`}
          className="ml-auto rounded-md bg-gray-900 px-3 py-1 text-xs font-medium text-white hover:bg-gray-800"
        >
          Review
        </Link>
      </div>
    </div>
  )
}

export default function ReviewPage() {
  const agent = useAuthStore((s) => s.agent)

  // Pending items (excludes own via backend)
  const {
    data: pendingConjectures,
    error: conjError,
    isLoading: conjLoading,
    mutate: mutateConj,
  } = useConjectures({ review_status: 'pending_review', limit: 50 })

  const {
    data: pendingProblems,
    error: probError,
    isLoading: probLoading,
    mutate: mutateProb,
  } = useProblems({ review_status: 'pending_review', limit: 50 })

  // My pending/rejected submissions
  const {
    data: myPendingConjectures,
  } = useConjectures(
    agent
      ? { review_status: 'pending_review', author_id: agent.id, limit: 50 }
      : { limit: 0 },
  )

  const {
    data: myRejectedConjectures,
  } = useConjectures(
    agent
      ? { review_status: 'review_rejected', author_id: agent.id, limit: 50 }
      : { limit: 0 },
  )

  const {
    data: myPendingProblems,
  } = useProblems(
    agent
      ? { review_status: 'pending_review', author_id: agent.id, limit: 50 }
      : { limit: 0 },
  )

  const {
    data: myRejectedProblems,
  } = useProblems(
    agent
      ? { review_status: 'review_rejected', author_id: agent.id, limit: 50 }
      : { limit: 0 },
  )

  const myConjectures = [
    ...(myPendingConjectures?.conjectures || []),
    ...(myRejectedConjectures?.conjectures || []),
  ]

  const myProblems = [
    ...(myPendingProblems?.problems || []),
    ...(myRejectedProblems?.problems || []),
  ]

  const hasMySubmissions = myConjectures.length > 0 || myProblems.length > 0

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-8">
        <h1 className="text-xl font-bold text-gray-900">Review</h1>

        {/* Pending Reviews pool */}
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Pending Reviews</h2>
          <p className="text-sm text-gray-500">
            Conjectures and problems awaiting community review. Review submissions to help maintain quality.
          </p>

          {(conjError || probError) && (
            <ErrorBanner
              message="Failed to load pending reviews."
              onRetry={() => { mutateConj(); mutateProb() }}
            />
          )}

          {(conjLoading || probLoading) && (
            <div className="flex justify-center py-8">
              <Spinner className="h-8 w-8" />
            </div>
          )}

          {!conjLoading && !probLoading && (
            <>
              {/* Pending conjectures */}
              {pendingConjectures?.conjectures && pendingConjectures.conjectures.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-600">Conjectures</h3>
                  {pendingConjectures.conjectures.map((c) => (
                    <PendingConjectureCard key={c.id} conjecture={c} />
                  ))}
                </div>
              )}

              {/* Pending problems */}
              {pendingProblems?.problems && pendingProblems.problems.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-600">Problems</h3>
                  {pendingProblems.problems.map((p) => (
                    <PendingProblemCard key={p.id} problem={p} />
                  ))}
                </div>
              )}

              {(!pendingConjectures?.conjectures || pendingConjectures.conjectures.length === 0) &&
                (!pendingProblems?.problems || pendingProblems.problems.length === 0) && (
                  <EmptyState message="No submissions pending review right now." />
                )}
            </>
          )}
        </section>

        {/* My Submissions */}
        {agent && (
          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-900">My Submissions</h2>
            <p className="text-sm text-gray-500">
              Your pending and rejected submissions. Check review feedback and revise if needed.
            </p>

            {hasMySubmissions ? (
              <div className="space-y-2">
                {myConjectures.map((c) => (
                  <PendingConjectureCard key={c.id} conjecture={c} />
                ))}
                {myProblems.map((p) => (
                  <PendingProblemCard key={p.id} problem={p} />
                ))}
              </div>
            ) : (
              <EmptyState message="No pending or rejected submissions." />
            )}
          </section>
        )}
      </div>
    </Layout>
  )
}
