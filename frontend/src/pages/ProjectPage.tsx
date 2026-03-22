import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { useProject, useProjectTree, useProjectOverview } from '../hooks'
import Layout from '../components/layout/Layout'
import LaTeXText from '../components/ui/LaTeXText'
import ProgressBar from '../components/ui/ProgressBar'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import ProofTree from '../components/tree/ProofTree'
import ActivityFeed from '../components/activity/ActivityFeed'
import MarkdownContent from '../components/ui/MarkdownContent'
import { flattenTree } from '../lib/utils'

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const { data: project, error: projectError, isLoading: projectLoading, mutate: mutateProject } = useProject(id!)
  const { data: treeData, error: treeError, isLoading: treeLoading } = useProjectTree(id!)
  const { data: overview } = useProjectOverview(id!)
  const { mutate: globalMutate } = useSWRConfig()

  const flatNodes = useMemo(() => {
    if (!treeData?.root || !id) return []
    return flattenTree(treeData.root, id)
  }, [treeData, id])

  if (projectLoading || treeLoading) {
    return (
      <Layout>
        <div className="flex items-center justify-center py-20">
          <Spinner className="h-6 w-6" />
        </div>
      </Layout>
    )
  }

  if (projectError || treeError) {
    return (
      <Layout>
        <ErrorBanner
          message="Failed to load project."
          onRetry={() => {
            mutateProject()
            globalMutate(['project-tree', id])
          }}
        />
      </Layout>
    )
  }

  if (!project) {
    return (
      <Layout>
        <div className="py-12 text-center">
          <h1 className="text-xl font-bold text-gray-900">Project not found</h1>
          <a href="/" className="mt-2 inline-block text-blue-600 hover:underline">Go home</a>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">{project.title}</h1>
        {project.description && (
          <p className="mt-1 text-sm text-gray-600"><LaTeXText>{project.description}</LaTeXText></p>
        )}
        <div className="mt-3">
          <ProgressBar
            percent={project.progress}
            label={`${project.proved_leaves}/${project.total_leaves} leaves proved`}
          />
        </div>
      </div>

      {/* Proof Tree */}
      {flatNodes.length > 0 ? (
        <ProofTree tree={flatNodes} />
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white px-6 py-12 text-center text-sm text-gray-400">
          No conjectures in this project yet.
        </div>
      )}

      {/* Pinned mega agent summary */}
      {overview?.tree?.[0]?.summary && (
        <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700">
              MEGA
            </span>
            <span className="text-xs font-semibold uppercase text-amber-700">Project Summary</span>
          </div>
          <div className="text-sm text-gray-700">
            <MarkdownContent>{overview.tree[0].summary}</MarkdownContent>
          </div>
        </div>
      )}

      {/* Activity Feed */}
      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold text-gray-500">Activity Feed</h2>
        <ActivityFeed projectId={id!} />
      </div>
    </Layout>
  )
}
