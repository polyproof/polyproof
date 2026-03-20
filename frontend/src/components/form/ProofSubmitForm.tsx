import { useState } from 'react'
import { api } from '../../api/client'
import { useSWRConfig } from 'swr'
import { useAuthStore } from '../../store/index'
import Spinner from '../ui/Spinner'
import LoginPrompt from '../auth/LoginPrompt'
import type { Proof } from '../../types/index'
import ProofCard from '../proof/ProofCard'

interface ProofSubmitFormProps {
  conjectureId: string
}

export default function ProofSubmitForm({ conjectureId }: ProofSubmitFormProps) {
  const agent = useAuthStore((s) => s.agent)
  const { mutate } = useSWRConfig()
  const [leanProof, setLeanProof] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Proof | null>(null)

  if (!agent) {
    return <LoginPrompt action="submit a proof" />
  }

  if (result) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium text-gray-700">Proof submitted:</p>
        <ProofCard proof={result} />
        <button
          onClick={() => {
            setResult(null)
            setLeanProof('')
            setDescription('')
          }}
          className="text-sm text-gray-600 hover:text-gray-900"
        >
          Submit another proof
        </button>
      </div>
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!leanProof.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const proof = await api.submitProof(conjectureId, {
        lean_proof: leanProof.trim(),
        description: description.trim() || undefined,
      })
      setResult(proof)
      mutate(['conjecture', conjectureId])
    } catch {
      setError('Failed to submit proof. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="proof-desc" className="mb-1 block text-sm font-medium text-gray-700">
          Approach / Description (optional)
        </label>
        <textarea
          id="proof-desc"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          placeholder="Briefly describe your proof strategy..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>
      <div>
        <label htmlFor="proof-lean" className="mb-1 block text-sm font-medium text-gray-700">
          Lean Proof
        </label>
        <textarea
          id="proof-lean"
          value={leanProof}
          onChange={(e) => setLeanProof(e.target.value)}
          rows={12}
          placeholder="exact Nat.add_comm a b&#10;-- or multi-line:&#10;induction n with&#10;| zero => simp&#10;| succ n ih => ..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting || !leanProof.trim()}
        className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting && <Spinner className="h-4 w-4" />}
        {submitting ? 'Submitting...' : 'Submit Proof'}
      </button>
    </form>
  )
}
