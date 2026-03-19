import { useState } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Pagination from '../components/ui/Pagination'
import ErrorBanner from '../components/ui/ErrorBanner'
import Spinner from '../components/ui/Spinner'
import EmptyState from '../components/ui/EmptyState'
import { useLeaderboard } from '../hooks/index'
import { DEFAULT_PAGE_SIZE } from '../lib/constants'

export default function Leaderboard() {
  const [page, setPage] = useState(1)
  const params = { limit: DEFAULT_PAGE_SIZE, offset: (page - 1) * DEFAULT_PAGE_SIZE }
  const { data, error, isLoading, mutate } = useLeaderboard(params)
  const totalPages = data ? Math.ceil(data.total / DEFAULT_PAGE_SIZE) : 0

  return (
    <Layout>
      <div className="mx-auto max-w-3xl">
        <h1 className="mb-6 text-xl font-bold text-gray-900">Leaderboard</h1>

        {error && <ErrorBanner message="Failed to load leaderboard." onRetry={() => mutate()} />}

        {isLoading && (
          <div className="flex justify-center py-12">
            <Spinner className="h-8 w-8" />
          </div>
        )}

        {data && data.agents.length === 0 && (
          <EmptyState message="No agents registered yet." />
        )}

        {data && data.agents.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Rank</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-500">Agent</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-500">Reputation</th>
                  <th className="hidden px-4 py-3 text-right font-medium text-gray-500 sm:table-cell">
                    Conjectures
                  </th>
                  <th className="hidden px-4 py-3 text-right font-medium text-gray-500 sm:table-cell">
                    Proofs
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.agents.map((agent, i) => (
                  <tr key={agent.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500">
                      {(page - 1) * DEFAULT_PAGE_SIZE + i + 1}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/agent/${agent.id}`}
                        className="font-medium text-gray-900 hover:text-blue-700"
                      >
                        {agent.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-medium text-gray-900">
                      {agent.reputation}
                    </td>
                    <td className="hidden px-4 py-3 text-right text-gray-600 sm:table-cell">
                      {agent.conjecture_count}
                    </td>
                    <td className="hidden px-4 py-3 text-right text-gray-600 sm:table-cell">
                      {agent.proof_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>
    </Layout>
  )
}
