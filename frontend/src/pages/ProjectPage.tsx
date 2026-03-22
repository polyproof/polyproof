import { useState, useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { useSWRConfig } from 'swr'
import { useProject, useProjectTree, useProjectComments } from '../hooks'
import Layout from '../components/layout/Layout'
import LaTeXText from '../components/ui/LaTeXText'
import ProgressBar from '../components/ui/ProgressBar'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import ProofTree from '../components/tree/ProofTree'
import ActivityFeed from '../components/activity/ActivityFeed'
import CommentThread from '../components/comment/CommentThread'
import { flattenTree } from '../lib/utils'
import { cn } from '../lib/utils'
import { api } from '../api/client'

type Tab = 'activity' | 'discussion'

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>()
  const { data: project, error: projectError, isLoading: projectLoading, mutate: mutateProject } = useProject(id!)
  const { data: treeData, error: treeError, isLoading: treeLoading } = useProjectTree(id!)
  const { data: comments, mutate: mutateComments } = useProjectComments(id!)
  const { mutate: globalMutate } = useSWRConfig()
  const [activeTab, setActiveTab] = useState<Tab>('activity')

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

  const handlePostComment = async (body: string, parentCommentId?: string) => {
    await api.postProjectComment(id!, body, parentCommentId)
    mutateComments()
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

      {/* Tabs */}
      <div className="mt-6 border-b border-gray-200">
        <div className="flex gap-4">
          {(['activity', 'discussion'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'border-b-2 px-1 pb-2 text-sm font-medium capitalize transition-colors',
                activeTab === tab
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:text-gray-700',
              )}
            >
              {tab === 'activity' ? 'Activity Feed' : 'Discussion'}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="mt-4">
        {activeTab === 'activity' && <ActivityFeed projectId={id!} />}
        {activeTab === 'discussion' && comments && (
          <CommentThread thread={comments} onPostComment={handlePostComment} />
        )}
      </div>
    </Layout>
  )
}
