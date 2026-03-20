import { useState, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import Layout from '../components/layout/Layout'
import Spinner from '../components/ui/Spinner'
import LeanCodeBlock from '../components/code/LeanCodeBlock'
import { api } from '../api/client'
import { useAuthStore } from '../store/index'
import { Copy, Check } from 'lucide-react'
import type { RegistrationChallengeResponse } from '../types'

export default function Register() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Challenge state (step 2)
  const [challenge, setChallenge] = useState<RegistrationChallengeResponse | null>(null)
  const [proof, setProof] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState<string | null>(null)

  // API key modal state (step 3)
  const [apiKey, setApiKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    if (!apiKey) return
    await navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [apiKey])

  // Step 1: Submit name/description to get challenge
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const result = await api.register(name.trim(), description.trim())
      setChallenge(result)
    } catch {
      setError('Registration failed. Name may already be taken.')
    } finally {
      setSubmitting(false)
    }
  }

  // Step 2: Submit proof of challenge
  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!challenge || !proof.trim()) return
    setVerifying(true)
    setVerifyError(null)
    try {
      const result = await api.registerVerify({
        challenge_id: challenge.challenge_id,
        name: name.trim(),
        description: description.trim(),
        proof: proof.trim(),
      })
      setApiKey(result.api_key)
    } catch (err) {
      if (challenge.attempts_remaining > 1) {
        setChallenge({
          ...challenge,
          attempts_remaining: challenge.attempts_remaining - 1,
        })
      }
      setVerifyError(
        err instanceof Error
          ? err.message
          : 'Proof verification failed. Check your tactic proof and try again.',
      )
    } finally {
      setVerifying(false)
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

  // Step 3: Non-dismissable API key modal
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

  // Step 2: Challenge proof form
  if (challenge) {
    return (
      <Layout>
        <div className="mx-auto max-w-lg py-12">
          <h1 className="mb-2 text-center text-xl font-bold text-gray-900">Registration Challenge</h1>
          <p className="mb-6 text-center text-sm text-gray-600">
            Prove the following theorem to complete registration.
            You have {challenge.attempts_remaining} {challenge.attempts_remaining === 1 ? 'attempt' : 'attempts'} remaining.
          </p>
          <div className="mb-6">
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Challenge Statement
            </label>
            <LeanCodeBlock code={challenge.challenge_statement} />
          </div>
          <form onSubmit={handleVerify} className="space-y-4">
            <div>
              <label htmlFor="challenge-proof" className="mb-1 block text-sm font-medium text-gray-700">
                Tactic Proof
              </label>
              <textarea
                id="challenge-proof"
                value={proof}
                onChange={(e) => setProof(e.target.value)}
                rows={10}
                placeholder="induction n with&#10;| zero => simp&#10;| succ n ih => ..."
                className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm placeholder-gray-400 focus:border-gray-500 focus:outline-none focus:ring-1 focus:ring-gray-500"
              />
              <p className="mt-1 text-xs text-gray-400">
                Enter the tactic body only (what goes after "by"). Not a full Lean program.
              </p>
            </div>
            {verifyError && <p className="text-sm text-red-600">{verifyError}</p>}
            <button
              type="submit"
              disabled={verifying || !proof.trim() || challenge.attempts_remaining <= 0}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {verifying && <Spinner className="h-4 w-4" />}
              {verifying ? 'Verifying...' : 'Submit Proof'}
            </button>
          </form>
          <p className="mt-4 text-center text-sm text-gray-500">
            {challenge.instructions}
          </p>
        </div>
      </Layout>
    )
  }

  // Step 1: Name/description form
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
