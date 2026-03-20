import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { useProblems } from '../../hooks/index'
import Spinner from '../ui/Spinner'

interface ConjectureFormProps {
  defaultProblemId?: string
}

export default function ConjectureForm({ defaultProblemId }: ConjectureFormProps) {
  const navigate = useNavigate()
  const { data: problemsData } = useProblems({ limit: 100 })
  const [leanStatement, setLeanStatement] = useState('')
  const [description, setDescription] = useState('')
  const [problemId, setProblemId] = useState(defaultProblemId || '')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!leanStatement.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const conjecture = await api.createConjecture({
        lean_statement: leanStatement.trim(),
        description: description.trim(),
        problem_id: problemId || undefined,
      })
      navigate(`/c/${conjecture.id}`)
    } catch {
      setError('Failed to create conjecture. Make sure your Lean statement is valid.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="conj-problem" className="mb-1 block text-sm font-medium text-gray-700">
          Problem (optional)
        </label>
        <select
          id="conj-problem"
          value={problemId}
          onChange={(e) => setProblemId(e.target.value)}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        >
          <option value="">No problem selected</option>
          {problemsData?.problems?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label htmlFor="conj-lean" className="mb-1 block text-sm font-medium text-gray-700">
          Lean Statement
        </label>
        <textarea
          id="conj-lean"
          value={leanStatement}
          onChange={(e) => setLeanStatement(e.target.value)}
          rows={8}
          placeholder="&#8704; n : Nat, ..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>
      <div>
        <label htmlFor="conj-desc" className="mb-1 block text-sm font-medium text-gray-700">
          Description
        </label>
        <textarea
          id="conj-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={4}
          placeholder="What does this conjecture claim? Why is it interesting?"
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting || !leanStatement.trim()}
        className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting && <Spinner className="h-4 w-4" />}
        Post Conjecture
      </button>
    </form>
  )
}
