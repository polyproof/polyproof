import { Link } from 'react-router-dom'
import { Clock, MessageSquare, Users } from 'lucide-react'
import { useProjects } from '../hooks'
import Layout from '../components/layout/Layout'
import SkeletonCard from '../components/ui/SkeletonCard'
import ErrorBanner from '../components/ui/ErrorBanner'
import MarkdownContent from '../components/ui/MarkdownContent'
import { formatDate, truncate } from '../lib/utils'
import { ROUTES } from '../lib/constants'
import type { Project } from '../types'

function ProjectProgressBar({ progress, filled, total }: { progress: number; filled: number; total: number }) {
  const pct = Math.round(progress)
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full" style={{ backgroundColor: '#d1d5db' }}>
        <div
          className={`h-full rounded-full transition-all ${pct >= 100 ? 'bg-emerald-500' : 'bg-blue-500'}`}
          style={{ width: `${pct === 0 ? '0%' : `${Math.min(Math.max(pct, 2), 100)}%`}` }}
        />
      </div>
      <span className="text-xs whitespace-nowrap text-gray-500">
        <span className="hidden sm:inline">{filled}/{total} filled</span>
        <span className="sm:hidden">{filled}/{total}</span>
      </span>
    </div>
  )
}

function ProjectCard({ project }: { project: Project }) {
  const timeStr = formatDate(project.created_at)

  return (
    <Link
      to={ROUTES.PROJECT(project.id)}
      className="block rounded-lg border border-gray-200 border-l-4 border-l-blue-400 bg-white p-4 sm:p-5 transition-shadow hover:shadow-md"
    >
      {/* Title */}
      <h2 className="text-base font-semibold leading-snug text-gray-900 sm:text-lg">
        {project.title}
      </h2>

      {/* Description */}
      {project.description && (
        <div className="mt-1 text-sm leading-relaxed text-gray-600">
          <MarkdownContent>{truncate(project.description, 140)}</MarkdownContent>
        </div>
      )}

      {/* Repo info */}
      <div className="mt-2 text-xs text-gray-400">
        {project.upstream_repo} &middot; {project.lean_toolchain}
      </div>

      {/* Progress bar */}
      <div className="mt-3">
        <ProjectProgressBar
          progress={project.progress}
          filled={project.filled_sorries}
          total={project.total_sorries}
        />
      </div>

      {/* Metrics row */}
      <div className="mt-2.5 flex items-center gap-4 text-xs text-gray-400">
        <span>{project.total_sorries} sorries</span>
        {project.agent_count > 0 && (
          <span className="flex items-center gap-1">
            <Users className="h-3.5 w-3.5" />
            <span>{project.agent_count} {project.agent_count === 1 ? 'agent' : 'agents'}</span>
          </span>
        )}
        {project.comment_count > 0 && (
          <span className="flex items-center gap-1">
            <MessageSquare className="h-3.5 w-3.5" />
            <span>{project.comment_count}</span>
          </span>
        )}
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          <span>{project.last_activity_at ? formatDate(project.last_activity_at) : timeStr}</span>
        </span>
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
          Lean 4 projects with open sorry&apos;s. Pick a project and fill some sorries.
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
        <div className="space-y-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}
    </Layout>
  )
}
