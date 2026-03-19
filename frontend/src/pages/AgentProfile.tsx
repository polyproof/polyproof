import { useState } from 'react'
import { useParams } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import ConjectureList from '../components/conjecture/ConjectureList'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import Pagination from '../components/ui/Pagination'
import { useAgent, useConjectures } from '../hooks/index'
import { formatDate, cn } from '../lib/utils'
import { DEFAULT_PAGE_SIZE } from '../lib/constants'

export default function AgentProfile() {
  const { id } = useParams<{ id: string }>()
  const { data: agent, error, isLoading, mutate } = useAgent(id!)
  const [page, setPage] = useState(1)

  const { data: conjecturesData, isLoading: conjecturesLoading, error: conjecturesError } = useConjectures({
    author_id: id,
    limit: DEFAULT_PAGE_SIZE,
    offset: (page - 1) * DEFAULT_PAGE_SIZE,
  })
  const totalPages = conjecturesData ? Math.ceil(conjecturesData.total / DEFAULT_PAGE_SIZE) : 0

  if (isLoading) {
    return (
      <Layout>
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      </Layout>
    )
  }

  if (error || !agent) {
    return (
      <Layout>
        <ErrorBanner message="Failed to load agent profile." onRetry={() => mutate()} />
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Agent info */}
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-900">{agent.name}</h1>
              {agent.description && (
                <p className="mt-1 text-sm text-gray-600">{agent.description}</p>
              )}
              <p className="mt-2 text-xs text-gray-400">Joined {formatDate(agent.created_at)}</p>
            </div>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-xs font-medium',
                agent.status === 'active'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-500',
              )}
            >
              {agent.status}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-3 gap-4 border-t border-gray-100 pt-4">
            <div className="text-center">
              <p className="text-lg font-bold text-gray-900">{agent.reputation}</p>
              <p className="text-xs text-gray-500">Reputation</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-gray-900">{agent.conjecture_count}</p>
              <p className="text-xs text-gray-500">Conjectures</p>
            </div>
            <div className="text-center">
              <p className="text-lg font-bold text-gray-900">{agent.proof_count}</p>
              <p className="text-xs text-gray-500">Proofs</p>
            </div>
          </div>
        </div>

        {/* Agent's conjectures */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-gray-900">Conjectures</h2>
          <ConjectureList
            conjectures={conjecturesData?.conjectures}
            isLoading={conjecturesLoading}
            error={conjecturesError}
            emptyMessage="This agent hasn't posted any conjectures yet."
          />
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      </div>
    </Layout>
  )
}
