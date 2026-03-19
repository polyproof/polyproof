import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import Spinner from '../ui/Spinner'

export default function ProblemForm() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const titleValid = title.trim().length >= 5 && title.trim().length <= 200

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!titleValid) return
    setSubmitting(true)
    setError(null)
    try {
      const problem = await api.createProblem({ title: title.trim(), description: description.trim() })
      navigate(`/p/${problem.id}`)
    } catch {
      setError('Failed to create problem. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="problem-title" className="mb-1 block text-sm font-medium text-gray-700">
          Title
        </label>
        <input
          id="problem-title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={200}
          placeholder="e.g., Bounds on domination numbers of planar graphs"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
        <p className="mt-1 text-xs text-gray-400">
          {title.trim().length}/200 characters (minimum 5)
        </p>
      </div>
      <div>
        <label htmlFor="problem-desc" className="mb-1 block text-sm font-medium text-gray-700">
          Description
        </label>
        <textarea
          id="problem-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={5}
          placeholder="Describe the problem area, relevant background, and what kinds of conjectures you're looking for..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting || !titleValid}
        className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting && <Spinner className="h-4 w-4" />}
        Create Problem
      </button>
    </form>
  )
}
