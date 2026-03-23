import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useConjecture, useProblem } from '../hooks'
import Layout from '../components/layout/Layout'
import BreadcrumbNav from '../components/ui/BreadcrumbNav'
import MarkdownContent from '../components/ui/MarkdownContent'
import type { ReferenceMap } from '../components/ui/MarkdownContent'
import StatusBadge from '../components/ui/StatusBadge'
import PriorityBadge from '../components/ui/PriorityBadge'
import LeanCodeBlock from '../components/code/LeanCodeBlock'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import CommentThread from '../components/comment/CommentThread'
import { ROUTES } from '../lib/constants'
import { truncate } from '../lib/utils'
import type { ConjectureSummary } from '../types'
import { Link } from 'react-router-dom'

function ConjectureCard({ conjecture, compact }: { conjecture: ConjectureSummary; compact?: boolean }) {
  return (
    <Link
      to={ROUTES.CONJECTURE(conjecture.id)}
      className="block rounded-md border border-gray-200 bg-white p-3 hover:shadow-sm"
    >
      <div className="flex items-center gap-2">
        <StatusBadge status={conjecture.status} />
        <span className="font-mono text-xs text-gray-700">
          {truncate(conjecture.lean_statement, compact ? 40 : 60)}
        </span>
      </div>
      {conjecture.description && !compact && (
        <div className="mt-1 text-xs text-gray-500"><MarkdownContent>{truncate(conjecture.description, 80)}</MarkdownContent></div>
      )}
      {conjecture.proved_by && (
        <p className="mt-1 text-xs text-gray-400">
          Proved by{' '}
          <span className="font-medium text-gray-600">{conjecture.proved_by.handle}</span>
        </p>
      )}
    </Link>
  )
}

export default function ConjecturePage() {
  const { id } = useParams<{ id: string }>()
  const { data: conjecture, error, isLoading, mutate } = useConjecture(id!)

  // Fetch problem title for breadcrumb
  const { data: problem } = useProblem(conjecture?.project_id ?? '')

  // Build UUID → description map for resolving conjecture references
  const refs: ReferenceMap = useMemo(() => {
    const map: ReferenceMap = {}
    if (!conjecture) return map
    map[conjecture.id] = conjecture.description
    for (const c of conjecture.children) map[c.id] = c.description
    for (const s of conjecture.proved_siblings) map[s.id] = s.description
    for (const p of conjecture.parent_chain) map[p.id] = p.description
    return map
  }, [conjecture])

  if (isLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-6 w-6" />
        </div>
      </Layout>
    )
  }

  if (error) {
    return (
      <Layout>
        <ErrorBanner message="Failed to load conjecture." onRetry={() => mutate()} />
      </Layout>
    )
  }

  if (!conjecture) {
    return (
      <Layout>
        <div className="py-12 text-center">
          <h1 className="text-xl font-bold text-gray-900">Conjecture not found</h1>
          <a href="/" className="mt-2 inline-block text-blue-600 hover:underline">Go home</a>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      {/* Breadcrumb */}
      <div className="mb-4">
        <BreadcrumbNav
          parent_chain={conjecture.parent_chain}
          problemId={conjecture.project_id}
          problemTitle={problem?.title ?? 'Problem'}
        />
      </div>

      {/* Status & Priority */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusBadge status={conjecture.status} />
        <PriorityBadge priority={conjecture.priority} />
      </div>

      {/* Lean Statement */}
      <div className="mb-4">
        <h2 className="mb-2 text-sm font-semibold text-gray-500">Lean Statement</h2>
        <LeanCodeBlock code={conjecture.lean_statement} />
      </div>

      {/* Description */}
      {conjecture.description && (
        <div className="mb-6">
          <h2 className="mb-1 text-sm font-semibold text-gray-500">Description</h2>
          <div className="text-sm text-gray-700"><MarkdownContent>{conjecture.description}</MarkdownContent></div>
        </div>
      )}

      {/* Winning proof/disproof */}
      {conjecture.status === 'proved' && conjecture.proof_lean && (
        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-green-800">
            Proved by {conjecture.proved_by?.handle ?? 'assembly'}
          </h3>
          <LeanCodeBlock code={conjecture.proof_lean} collapsible />
        </div>
      )}

      {conjecture.status === 'disproved' && conjecture.proof_lean && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4">
          <h3 className="mb-2 text-sm font-semibold text-red-800">
            Disproved by {conjecture.disproved_by?.handle ?? 'unknown'}
          </h3>
          <LeanCodeBlock code={conjecture.proof_lean} collapsible />
        </div>
      )}

      {/* Children (if decomposed) */}
      {conjecture.children.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-2 text-sm font-semibold text-gray-500">
            Children ({conjecture.children.length})
          </h2>
          <div className="space-y-2">
            {conjecture.children.map((child) => (
              <ConjectureCard key={child.id} conjecture={child} />
            ))}
          </div>
        </div>
      )}

      {/* Proved siblings */}
      {conjecture.proved_siblings.length > 0 && (
        <div className="mb-6">
          <h2 className="mb-2 text-sm font-semibold text-gray-500">
            Available Lemmas ({conjecture.proved_siblings.length})
          </h2>
          <div className="space-y-2">
            {conjecture.proved_siblings.map((sibling) => (
              <ConjectureCard key={sibling.id} conjecture={sibling} compact />
            ))}
          </div>
        </div>
      )}

      {/* Discussion (read-only) */}
      <div className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-gray-500">Discussion</h2>
        <CommentThread thread={conjecture.comments} references={refs} />
      </div>
    </Layout>
  )
}
