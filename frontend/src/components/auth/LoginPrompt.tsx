import { Link } from 'react-router-dom'

export default function LoginPrompt({ action = 'vote' }: { action?: string }) {
  return (
    <p className="text-sm text-gray-500">
      <Link to="/login" className="font-medium text-gray-900 underline hover:text-gray-700">
        Log in
      </Link>{' '}
      to {action}
    </p>
  )
}
