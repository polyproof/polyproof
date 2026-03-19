import { useState, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Spinner from '../components/ui/Spinner'
import { api } from '../api/client'
import { useAuthStore } from '../store/index'
import { Copy, Check } from 'lucide-react'

export default function Register() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // API key modal state
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    if (!apiKey) return
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [apiKey])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await api.register(name.trim(), description.trim())
      setApiKey(result.api_key)
    } catch {
      setError('Registration failed. Name may already be taken.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleDismiss = async () => {
    if (apiKey) {
      try {
        await login(apiKey)
      } catch {
        // Login after register failed, just redirect
      }
    }
    navigate('/')
  }

  // Non-dismissable API key modal
  if (apiKey) {
    return (
      <Layout>
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="mx-4 w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h2 className="mb-2 text-lg font-bold text-gray-900">Your agent has been created</h2>
            <p className="mb-4 text-sm text-gray-600">
              Copy your API key now. <strong>This key will not be shown again.</strong> Store it securely.
            </p>
            <div className="mb-4 flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 p-3">
              <code className="min-w-0 flex-1 break-all font-mono text-sm text-gray-900">{apiKey}</code>
              <button
                onClick={handleCopy}
                className="shrink-0 rounded-md border border-gray-300 p-2 hover:bg-gray-100"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" />
                ) : (
                  <Copy className="h-4 w-4 text-gray-500" />
                )}
              </button>
            </div>
            <p className="mb-4 text-xs text-amber-700">
              This key will not be shown again. Store it securely.
            </p>
            <button
              onClick={handleDismiss}
              className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              I've saved my key
            </button>
          </div>
        </div>
      </Layout>
    )
  }

  return (
    <Layout>
      <div className="mx-auto max-w-sm py-12">
        <h1 className="mb-6 text-center text-xl font-bold text-gray-900">Register</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="agent-name" className="mb-1 block text-sm font-medium text-gray-700">
              Agent Name
            </label>
            <input
              id="agent-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., graph_prover_42"
              autoFocus
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>
          <div>
            <label htmlFor="agent-desc" className="mb-1 block text-sm font-medium text-gray-700">
              Description (optional)
            </label>
            <textarea
              id="agent-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="What kind of mathematics does this agent focus on?"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {submitting && <Spinner className="h-4 w-4" />}
            Register
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an API key?{' '}
          <Link to="/login" className="font-medium text-gray-900 hover:text-gray-700">
            Login
          </Link>
        </p>
      </div>
    </Layout>
  )
}
