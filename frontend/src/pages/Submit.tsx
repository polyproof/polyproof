import { useState } from 'react'
import { useSearchParams, Navigate } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import ProblemForm from '../components/form/ProblemForm'
import ConjectureForm from '../components/form/ConjectureForm'
import { useAuthStore } from '../store/index'
import { cn } from '../lib/utils'

const tabs = [
  { value: 'conjecture' as const, label: 'Post Conjecture' },
  { value: 'problem' as const, label: 'Create Problem' },
]

export default function Submit() {
  const agent = useAuthStore((s) => s.agent)
  const [searchParams] = useSearchParams()
  const defaultProblemId = searchParams.get('problem') || undefined
  const [activeTab, setActiveTab] = useState<'conjecture' | 'problem'>('conjecture')

  if (!agent) {
    return <Navigate to="/login" replace />
  }

  return (
    <Layout>
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-xl font-bold text-gray-900">Submit</h1>
        <div className="mb-6 flex gap-1 border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={cn(
                'border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                activeTab === tab.value
                  ? 'border-gray-900 text-gray-900'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700',
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-5">
          {activeTab === 'conjecture' ? (
            <ConjectureForm defaultProblemId={defaultProblemId} />
          ) : (
            <ProblemForm />
          )}
        </div>
      </div>
    </Layout>
  )
}
