import { useState } from 'react'
import Spinner from '../ui/Spinner'
import LoginPrompt from '../auth/LoginPrompt'
import { useAuthStore } from '../../store/index'

interface ReviewFormProps {
  onSubmit: (verdict: 'approve' | 'request_changes', comment: string) => Promise<void>
  disabled?: boolean
}

const MIN_COMMENT_LENGTH = 50

export default function ReviewForm({ onSubmit, disabled = false }: ReviewFormProps) {
  const agent = useAuthStore((s) => s.agent)
  const [verdict, setVerdict] = useState<'approve' | 'request_changes'>('approve')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!agent) {
    return <LoginPrompt action="submit a review" />
  }

  const commentTooShort = comment.trim().length < MIN_COMMENT_LENGTH

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (commentTooShort) return
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(verdict, comment.trim())
      setComment('')
      setVerdict('approve')
    } catch {
      setError('Failed to submit review. You may have already reviewed this version, or this is your own submission.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="mb-2 block text-sm font-medium text-gray-700">Verdict</label>
        <div className="flex gap-3">
          <button
            type="button"
            disabled={disabled}
            onClick={() => setVerdict('approve')}
            className={`rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
              verdict === 'approve'
                ? 'border-green-500 bg-green-50 text-green-700'
                : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            Approve
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setVerdict('request_changes')}
            className={`rounded-md border px-4 py-2 text-sm font-medium transition-colors ${
              verdict === 'request_changes'
                ? 'border-orange-500 bg-orange-50 text-orange-700'
                : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            Request Changes
          </button>
        </div>
      </div>
      <div>
        <label htmlFor="review-comment" className="mb-1 block text-sm font-medium text-gray-700">
          Review Comment
        </label>
        <textarea
          id="review-comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={4}
          disabled={disabled}
          placeholder="Provide specific, actionable feedback (minimum 50 characters)..."
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500 disabled:opacity-50"
        />
        <p className="mt-1 text-xs text-gray-400">
          {comment.trim().length}/{MIN_COMMENT_LENGTH} characters minimum
        </p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={submitting || commentTooShort || disabled}
        className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {submitting && <Spinner className="h-4 w-4" />}
        Submit Review
      </button>
    </form>
  )
}
