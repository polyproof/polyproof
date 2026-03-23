import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Spinner from '../components/ui/Spinner'
import { api, ApiError } from '../api/client'
import { ROUTES } from '../lib/constants'

export default function CreateProblem() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [leanStatement, setLeanStatement] = useState('')
  const [leanDescription, setLeanDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !leanStatement.trim()) return

    setSubmitting(true)
    setError(null)

    try {
      const problem = await api.createProblem({
        title: title.trim(),
        description: description.trim(),
        root_conjecture: {
          lean_statement: leanStatement.trim(),
          description: leanDescription.trim(),
        },
      })
      navigate(ROUTES.PROBLEM(problem.id))
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError('Failed to create problem.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Layout>
      <div className="mx-auto max-w-2xl">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">Create Problem</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Formalize Carmichael's Conjecture"
              maxLength={200}
              className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe the problem goals..."
              rows={3}
              className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Root Lean Statement
            </label>
            <textarea
              value={leanStatement}
              onChange={(e) => setLeanStatement(e.target.value)}
              placeholder="The Lean 4 proposition to prove..."
              rows={4}
              className="w-full rounded-md border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-sm focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Root Conjecture Description
            </label>
            <textarea
              value={leanDescription}
              onChange={(e) => setLeanDescription(e.target.value)}
              placeholder="Describe the root conjecture..."
              rows={2}
              className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={!title.trim() || !leanStatement.trim() || submitting}
            className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <Spinner className="h-4 w-4" />}
            Create Problem
          </button>
        </form>
      </div>
    </Layout>
  )
}
