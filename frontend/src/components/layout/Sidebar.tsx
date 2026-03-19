import { Link } from 'react-router-dom'
import { useProblems } from '../../hooks/index'
import { truncate } from '../../lib/utils'

export default function Sidebar() {
  const { data } = useProblems({ sort: 'hot', limit: 10 })
  const problems = data?.problems

  return (
    <aside className="space-y-4">
      <div className="rounded-lg border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-4 py-3">
          <h2 className="text-sm font-semibold text-gray-900">Top Problems</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {problems && problems.length > 0 ? (
            problems.map((p, i) => (
              <Link
                key={p.id}
                to={`/p/${p.id}`}
                className="flex items-start gap-2 px-4 py-2.5 text-sm hover:bg-gray-50"
              >
                <span className="mt-0.5 text-xs font-medium text-gray-400">{i + 1}</span>
                <span className="text-gray-700 hover:text-blue-700">{truncate(p.title, 50)}</span>
              </Link>
            ))
          ) : (
            <p className="px-4 py-3 text-xs text-gray-400">No problems yet.</p>
          )}
        </div>
      </div>
      <Link
        to="/submit"
        className="flex w-full items-center justify-center rounded-lg bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
      >
        Create Problem
      </Link>
    </aside>
  )
}
