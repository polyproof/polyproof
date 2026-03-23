import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { useProblem, useProblemTree, useProblemOverview } from '../hooks'
import Layout from '../components/layout/Layout'
import ProgressBar from '../components/ui/ProgressBar'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import ProofTree from '../components/tree/ProofTree'
import ActivityFeed from '../components/activity/ActivityFeed'
import MarkdownContent from '../components/ui/MarkdownContent'
import type { ReferenceMap } from '../components/ui/MarkdownContent'
import { flattenTree } from '../lib/utils'

export default function ProblemPage() {
  const { id } = useParams<{ id: string }>()
  const { data: problem, error: problemError, isLoading: problemLoading, mutate: mutateProblem } = useProblem(id!)
  const { data: treeData, error: treeError, isLoading: treeLoading } = useProblemTree(id!)
  const { data: overview } = useProblemOverview(id!)
  const { mutate: globalMutate } = useSWRConfig()

  const flatNodes = useMemo(() => {
    if (!treeData?.root || !id) return []
    return flattenTree(treeData.root, id)
  }, [treeData, id])

  // Build UUID -> description map for resolving conjecture references
  const refs: ReferenceMap = useMemo(() => {
    const map: ReferenceMap = {}
    if (overview?.tree) {
      for (const node of overview.tree) {
        map[node.id] = node.description
      }
    }
    return map
  }, [overview])

  if (problemLoading || treeLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-6 w-6" />
        </div>
      </Layout>
    )
  }

  if (problemError || treeError) {
    return (
      <Layout>
        <ErrorBanner
          message="Failed to load problem."
          onRetry={() => {
            mutateProblem()
            globalMutate(['problem-tree', id])
          }}
        />
      </Layout>
    )
  }

  if (!problem) {
    return (
      <Layout>
        <div className="py-12 text-center">
          <h1 className="text-xl font-bold text-gray-900">Problem not found</h1>
          <a href="/" className="mt-2 inline-block text-blue-600 hover:underline">Go home</a>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{problem.title}</h1>
        {problem.description && (
          <div className="mt-1 text-sm text-gray-600"><MarkdownContent>{problem.description}</MarkdownContent></div>
        )}
        <div className="mt-3">
          <ProgressBar
            percent={problem.progress}
            label={`${problem.proved_leaves}/${problem.total_leaves} leaves proved`}
          />
        </div>
      </div>

      {/* Proof Tree */}
      {flatNodes.length > 0 ? (
        <ProofTree tree={flatNodes} />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400">
          No conjectures in this problem yet.
        </div>
      )}

      {/* Pinned mega agent summary */}
      {overview?.tree?.[0]?.summary && (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="mb-2">
            <span className="text-xs font-semibold uppercase text-amber-700">Problem Summary</span>
          </div>
          <div className="text-sm text-gray-700">
            <MarkdownContent references={refs}>{overview.tree[0].summary}</MarkdownContent>
          </div>
        </div>
      )}

      {/* Activity Feed */}
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold text-gray-500">Activity Feed</h2>
        <ActivityFeed problemId={id!} />
      </div>
    </Layout>
  )
}
