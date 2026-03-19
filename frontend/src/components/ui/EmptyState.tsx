import { Link } from 'react-router-dom'

interface EmptyStateProps {
  message: string
  actionLabel?: string
  actionTo?: string
  onAction?: () => void
}

export default function EmptyState({ message, actionLabel, actionTo, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-gray-200 px-6 py-12 text-center">
      <p className="text-sm text-gray-500">{message}</p>
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          {actionLabel}
        </Link>
      )}
      {actionLabel && onAction && !actionTo && (
        <button
          onClick={onAction}
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
        >
          {actionLabel}
        </button>
      )}
    </div>
  )
}
