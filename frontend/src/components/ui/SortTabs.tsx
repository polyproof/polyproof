import { cn } from '../../lib/utils'

const tabs = [
  { value: 'hot' as const, label: 'Hot' },
  { value: 'new' as const, label: 'New' },
  { value: 'top' as const, label: 'Top' },
]

interface SortTabsProps {
  value: 'hot' | 'new' | 'top'
  onChange: (value: 'hot' | 'new' | 'top') => void
}

export default function SortTabs({ value, onChange }: SortTabsProps) {
  return (
    <div className="flex gap-1 rounded-lg bg-gray-100 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
            value === tab.value
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900',
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
