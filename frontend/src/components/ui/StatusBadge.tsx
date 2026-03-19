import { cn } from '../../lib/utils'

const statusStyles = {
  open: 'bg-amber-100 text-amber-800 border-amber-300',
  proved: 'bg-green-100 text-green-800 border-green-300',
  disproved: 'bg-red-100 text-red-800 border-red-300',
} as const

export default function StatusBadge({ status }: { status: 'open' | 'proved' | 'disproved' }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide',
        statusStyles[status],
      )}
    >
      {status}
    </span>
  )
}
