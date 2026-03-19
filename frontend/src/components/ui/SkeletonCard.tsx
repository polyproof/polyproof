export default function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-lg border border-gray-200 bg-white p-4">
      <div className="flex gap-3">
        <div className="flex flex-col items-center gap-1">
          <div className="h-5 w-5 rounded bg-gray-200" />
          <div className="h-4 w-6 rounded bg-gray-200" />
          <div className="h-5 w-5 rounded bg-gray-200" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex items-center gap-2">
            <div className="h-5 w-16 rounded-full bg-gray-200" />
            <div className="h-5 w-48 rounded bg-gray-200" />
          </div>
          <div className="h-4 w-full rounded bg-gray-200" />
          <div className="h-20 w-full rounded bg-gray-100" />
          <div className="flex gap-4">
            <div className="h-3 w-24 rounded bg-gray-200" />
            <div className="h-3 w-20 rounded bg-gray-200" />
          </div>
        </div>
      </div>
    </div>
  )
}
