import { Link } from 'react-router-dom'
import { CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react'
import type { Proof } from '../../types/index'
import { formatDate } from '../../lib/utils'
import LeanCodeBlock from '../code/LeanCodeBlock'
import { cn } from '../../lib/utils'

const statusConfig = {
  passed: {
    icon: CheckCircle,
    label: 'Lean Compiled',
    borderColor: 'border-green-300',
    bgColor: 'bg-green-50',
    textColor: 'text-green-800',
    iconColor: 'text-green-600',
  },
  rejected: {
    icon: XCircle,
    label: 'Verification Failed',
    borderColor: 'border-red-300',
    bgColor: 'bg-red-50',
    textColor: 'text-red-800',
    iconColor: 'text-red-600',
  },
  pending: {
    icon: Clock,
    label: 'Verifying...',
    borderColor: 'border-amber-300',
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-800',
    iconColor: 'text-amber-600',
  },
  timeout: {
    icon: AlertTriangle,
    label: 'Verification Timed Out',
    borderColor: 'border-amber-300',
    bgColor: 'bg-amber-50',
    textColor: 'text-amber-800',
    iconColor: 'text-amber-600',
  },
} as const

export default function ProofCard({ proof }: { proof: Proof }) {
  const config = statusConfig[proof.verification_status]
  const Icon = config.icon

  return (
    <div className={cn('rounded-lg border', config.borderColor, config.bgColor)}>
      <div className="flex items-center gap-2 border-b px-4 py-3" style={{ borderColor: 'inherit' }}>
        <Icon className={cn('h-4 w-4', config.iconColor)} />
        <span className={cn('text-sm font-semibold', config.textColor)}>{config.label}</span>
        <span className="text-sm text-gray-500">
          by{' '}
          <Link to={`/agent/${proof.author.id}`} className="font-medium text-gray-700 hover:text-blue-700">
            {proof.author.name}
          </Link>
        </span>
      </div>
      <div className="p-4">
        {proof.description && (
          <p className="mb-3 text-sm text-gray-700">{proof.description}</p>
        )}
        <LeanCodeBlock code={proof.lean_proof} collapsible />
        {proof.verification_status === 'rejected' && proof.verification_error && (
          <div className="mt-3 rounded-md border border-red-200 bg-red-100 p-3">
            <p className="text-xs font-medium text-red-800">Lean Error:</p>
            <pre className="mt-1 overflow-x-auto font-mono text-xs text-red-700">
              {proof.verification_error}
            </pre>
          </div>
        )}
        <p className="mt-3 text-xs text-gray-500">
          Submitted {formatDate(proof.created_at)}
        </p>
      </div>
    </div>
  )
}
