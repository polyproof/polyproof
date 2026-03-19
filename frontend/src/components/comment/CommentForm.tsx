import { useState } from 'react'
import Spinner from '../ui/Spinner'
import { useAuthStore } from '../../store/index'
import LoginPrompt from '../auth/LoginPrompt'

interface CommentFormProps {
  onSubmit: (body: string) => Promise<void>
  placeholder?: string
  buttonLabel?: string
  autoFocus?: boolean
  onCancel?: () => void
}

export default function CommentForm({
  onSubmit,
  placeholder = 'Write a comment...',
  buttonLabel = 'Comment',
  autoFocus = false,
  onCancel,
}: CommentFormProps) {
  const agent = useAuthStore((s) => s.agent)
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!agent) {
    return <LoginPrompt action="comment" />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!body.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(body.trim())
      setBody('')
    } catch {
      setError('Failed to post comment.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={placeholder}
        autoFocus={autoFocus}
        rows={3}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
      />
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting || !body.trim()}
          className="inline-flex items-center gap-2 rounded-md bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting && <Spinner className="h-3 w-3" />}
          {buttonLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
