import { useParams, Link } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { useConjecture, useProject } from '../hooks'
import Layout from '../components/layout/Layout'
import BreadcrumbNav from '../components/ui/BreadcrumbNav'
import LaTeXText from '../components/ui/LaTeXText'
import StatusBadge from '../components/ui/StatusBadge'
import PriorityBadge from '../components/ui/PriorityBadge'
import LeanCodeBlock from '../components/code/LeanCodeBlock'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import CommentThread from '../components/comment/CommentThread'
import ProofForm from '../components/proof/ProofForm'
import VerifyPanel from '../components/proof/VerifyPanel'
import { ROUTES } from '../lib/constants'
import { truncate } from '../lib/utils'
import { api } from '../api/client'
import type { ConjectureSummary } from '../types'

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
        <p className="mt-1 text-xs text-gray-500"><LaTeXText>{truncate(conjecture.description, 80)}</LaTeXText></p>
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
  const { mutate: globalMutate } = useSWRConfig()

  // Fetch project title for breadcrumb
  const { data: project } = useProject(conjecture?.project_id ?? '')

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

  const isClosed = conjecture.status === 'proved' || conjecture.status === 'disproved' || conjecture.status === 'invalid'

  const handleProofSuccess = () => {
    mutate()
    // Revalidate project tree
    if (conjecture.project_id) {
      globalMutate(['project-tree', conjecture.project_id])
      globalMutate(['project', conjecture.project_id])
    }
  }

  const handlePostComment = async (body: string, parentCommentId?: string) => {
    await api.postConjectureComment(id!, body, parentCommentId)
    mutate()
  }

  return (
    <Layout>
      {/* Breadcrumb */}
      <div className="mb-4">
        <BreadcrumbNav
          parent_chain={conjecture.parent_chain}
          projectId={conjecture.project_id}
          projectTitle={project?.title ?? 'Project'}
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
          <p className="text-sm text-gray-700"><LaTeXText>{conjecture.description}</LaTeXText></p>
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

      {/* Discussion */}
      <div className="mb-6">
        <h2 className="mb-3 text-sm font-semibold text-gray-500">Discussion</h2>
        <CommentThread
          thread={conjecture.comments}
          onPostComment={handlePostComment}
        />
      </div>

      {/* Proof/Disproof submission */}
      {!isClosed && (
        <div className="mb-6 grid gap-4 md:grid-cols-2">
          <ProofForm
            conjectureId={id!}
            type="proof"
            onSuccess={handleProofSuccess}
          />
          <ProofForm
            conjectureId={id!}
            type="disproof"
            onSuccess={handleProofSuccess}
          />
        </div>
      )}

      {/* Verify panel */}
      <div className="mb-6">
        <VerifyPanel conjectureId={id} />
      </div>
    </Layout>
  )
}
