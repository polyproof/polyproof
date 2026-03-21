import { Link } from 'react-router-dom'
import { useProjects } from '../hooks'
import Layout from '../components/layout/Layout'
import ProgressBar from '../components/ui/ProgressBar'
import SkeletonCard from '../components/ui/SkeletonCard'
import ErrorBanner from '../components/ui/ErrorBanner'
import { formatDate, truncate } from '../lib/utils'
import { ROUTES } from '../lib/constants'
import type { Project } from '../types'

function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      to={ROUTES.PROJECT(project.id)}
      className="block rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md"
    >
      <h2 className="text-lg font-semibold text-gray-900">{project.title}</h2>
      {project.description && (
        <p className="mt-1 text-sm text-gray-600">{truncate(project.description, 120)}</p>
      )}
      <div className="mt-3">
        <ProgressBar
          percent={project.progress}
          label={`${project.proved_leaves}/${project.total_leaves} leaves proved`}
        />
      </div>
      <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
        <span>{project.total_leaves} leaves</span>
        <span>{project.last_activity_at ? formatDate(project.last_activity_at) : formatDate(project.created_at)}</span>
      </div>
    </Link>
  )
}

export default function Home() {
  const { data: projects, error, isLoading, mutate } = useProjects()

  return (
    <Layout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <p className="mt-1 text-sm text-gray-600">
          Collaborative theorem proving efforts. Pick a project and contribute proofs.
        </p>
      </div>

      {isLoading && (
        <div className="space-y-4">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {error && (
        <ErrorBanner message="Failed to load projects." onRetry={() => mutate()} />
      )}

      {projects && projects.length === 0 && (
        <p className="py-12 text-center text-sm text-gray-400">No active projects yet.</p>
      )}

      {projects && projects.length > 0 && (
        <div className="space-y-4">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </Layout>
  )
}
