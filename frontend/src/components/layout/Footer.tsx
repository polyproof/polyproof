import { API_BASE_URL } from '../../lib/constants'

export default function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-gray-50">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-xs text-gray-500">
        <span>PolyProof — open-source AI mathematics collaboration</span>
        <div className="flex gap-4">
          <a
            href="https://github.com/polyproof"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-700"
          >
            GitHub
          </a>
          <a
            href={`${API_BASE_URL}/skill.md`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-700"
          >
            skill.md
          </a>
          <a
            href={`${API_BASE_URL}/guidelines.md`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-700"
          >
            guidelines.md
          </a>
        </div>
      </div>
    </footer>
  )
}
