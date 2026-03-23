import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { truncate } from '../../lib/utils'
import { ROUTES } from '../../lib/constants'
import type { ConjectureStatus } from '../../types'

interface BreadcrumbNavProps {
  parent_chain: { id: string; lean_statement: string; description: string; status: ConjectureStatus }[]
  problemId: string
  problemTitle: string
}

export default function BreadcrumbNav({ parent_chain, problemId, problemTitle }: BreadcrumbNavProps) {
  return (
    <nav className="flex flex-wrap items-center gap-1 text-sm text-gray-500">
      <Link to={ROUTES.PROBLEM(problemId)} className="hover:text-gray-900">
        {truncate(problemTitle, 30)}
      </Link>
      {parent_chain.map((ancestor) => (
        <span key={ancestor.id} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3" />
          <Link to={ROUTES.CONJECTURE(ancestor.id)} className="hover:text-gray-900">
            {truncate(ancestor.lean_statement, 30)}
          </Link>
        </span>
      ))}
    </nav>
  )
}
