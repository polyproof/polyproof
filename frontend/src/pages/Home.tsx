import Layout from '../components/layout/Layout'
import ConjectureList from '../components/conjecture/ConjectureList'
import SortTabs from '../components/ui/SortTabs'
import Pagination from '../components/ui/Pagination'
import { useConjectures } from '../hooks/index'
import { useFeedStore } from '../store/index'
import { DEFAULT_PAGE_SIZE } from '../lib/constants'
import { cn } from '../lib/utils'

const statusFilters = [
  { value: 'all' as const, label: 'All' },
  { value: 'open' as const, label: 'Open' },
  { value: 'proved' as const, label: 'Proved' },
]

export default function Home() {
  const { sort, statusFilter, page, setSort, setStatusFilter, setPage } = useFeedStore()

  const params = {
    sort,
    status: statusFilter === 'all' ? undefined : statusFilter,
    limit: DEFAULT_PAGE_SIZE,
    offset: (page - 1) * DEFAULT_PAGE_SIZE,
  }

  const { data, error, isLoading, mutate } = useConjectures(params)
  const totalPages = data ? Math.ceil(data.total / DEFAULT_PAGE_SIZE) : 0

  return (
    <Layout sidebar>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-bold text-gray-900">Conjectures</h1>
          <SortTabs value={sort} onChange={setSort} />
        </div>
        <div className="flex flex-wrap gap-1">
          {statusFilters.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={cn(
                'rounded-full px-3 py-1 text-xs font-medium transition-colors',
                statusFilter === f.value
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        <ConjectureList
          conjectures={data?.conjectures}
          isLoading={isLoading}
          error={error}
          onRetry={() => mutate()}
          emptyMessage={
            statusFilter !== 'all'
              ? 'No conjectures match your filters.'
              : 'No conjectures posted yet. Be the first!'
          }
          emptyActionLabel={statusFilter !== 'all' ? undefined : 'Post Conjecture'}
          emptyActionTo={statusFilter !== 'all' ? undefined : '/submit'}
        />
        <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
      </div>
    </Layout>
  )
}
