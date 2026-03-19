import { useState, useCallback } from 'react'
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react'
import { cn } from '../../lib/utils'

const LEAN_KEYWORDS = [
  'theorem', 'lemma', 'def', 'import', 'by', 'sorry', 'apply', 'exact',
  'simp', 'omega', 'linarith', 'Prop', 'Type', 'where', 'have', 'let',
  'fun', 'match', 'with', 'if', 'then', 'else', 'do', 'return', 'structure',
  'class', 'instance', 'open', 'namespace', 'end', 'section', 'variable',
  'example', 'noncomputable', 'private', 'protected', 'set_option',
  'inductive', 'abbrev', 'opaque', 'axiom', 'intro', 'intros', 'rfl',
  'rw', 'rewrite', 'calc', 'show', 'suffices', 'obtain', 'rcases',
  'constructor', 'cases', 'induction', 'ring', 'norm_num', 'decide',
  'contradiction', 'absurd', 'exfalso', 'trivial',
]

function highlightLean(code: string): string {
  // Escape HTML
  let escaped = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Highlight comments (-- single line)
  escaped = escaped.replace(/(--.*$)/gm, '<span class="text-gray-500 italic">$1</span>')

  // Highlight strings
  escaped = escaped.replace(/("(?:[^"\\]|\\.)*")/g, '<span class="text-green-700">$1</span>')

  // Highlight keywords
  const kwPattern = new RegExp(`\\b(${LEAN_KEYWORDS.join('|')})\\b`, 'g')
  escaped = escaped.replace(kwPattern, '<span class="text-purple-700 font-semibold">$1</span>')

  // Highlight special symbols
  escaped = escaped.replace(/(:=|[→∀∃←↔⟨⟩])/g, '<span class="text-blue-600">$1</span>')

  return escaped
}

interface LeanCodeBlockProps {
  code: string
  collapsible?: boolean
  maxLines?: number
}

export default function LeanCodeBlock({ code, collapsible = false, maxLines = 12 }: LeanCodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const lines = code.split('\n')
  const shouldCollapse = collapsible && lines.length > maxLines && !expanded

  const displayCode = shouldCollapse ? lines.slice(0, maxLines).join('\n') : code

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [code])

  return (
    <div className="group relative rounded-md border border-gray-200 bg-gray-50">
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 rounded-md border border-gray-200 bg-white p-1.5 text-gray-500 opacity-0 transition-opacity hover:bg-gray-50 hover:text-gray-700 group-hover:opacity-100"
        title="Copy code"
      >
        {copied ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
      <pre className="overflow-x-auto p-3 text-sm leading-relaxed">
        <code
          className="font-mono"
          dangerouslySetInnerHTML={{ __html: highlightLean(displayCode) }}
        />
      </pre>
      {collapsible && lines.length > maxLines && (
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'flex w-full items-center justify-center gap-1 border-t border-gray-200 py-1.5 text-xs text-gray-500 hover:bg-gray-100 hover:text-gray-700',
          )}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" /> Collapse
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" /> Show full code ({lines.length} lines)
            </>
          )}
        </button>
      )}
    </div>
  )
}
