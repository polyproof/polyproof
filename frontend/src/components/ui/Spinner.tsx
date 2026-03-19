import { cn } from '../../lib/utils'

export default function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={cn('h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-gray-900', className)}
    />
  )
}
