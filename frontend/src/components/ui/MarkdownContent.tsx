import 'katex/dist/katex.min.css'
import ReactMarkdown from 'react-markdown'
import { Link } from 'react-router-dom'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'

// Allow KaTeX elements through the sanitizer
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [
    ...(defaultSchema.tagNames || []),
    // MathML
    'math', 'annotation', 'semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub',
    'mfrac', 'mover', 'munder', 'munderover', 'mtable', 'mtr', 'mtd', 'mtext',
    'mspace', 'menclose', 'merror', 'mpadded', 'mphantom', 'mroot', 'msqrt',
    'mstyle', 'mmultiscripts', 'mprescripts', 'none',
    // KaTeX HTML
    'span',
    // KaTeX SVG (for sqrt, cancel, fraction lines)
    'svg', 'line', 'path', 'g', 'rect',
  ],
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] || []), 'className', 'class'],
    math: ['xmlns', 'display'],
    annotation: ['encoding'],
    span: ['className', 'class', 'style', 'aria-hidden'],
    svg: ['xmlns', 'width', 'height', 'viewBox', 'preserveAspectRatio', 'style'],
    line: ['x1', 'y1', 'x2', 'y2', 'stroke', 'stroke-width'],
    path: ['d', 'fill', 'stroke', 'stroke-width'],
    rect: ['x', 'y', 'width', 'height', 'fill'],
    g: ['transform'],
  },
}

/** Map of UUID → description for resolving conjecture references. */
export type ReferenceMap = Record<string, string>

/**
 * Resolve a UUID to a display label using the reference map.
 * Falls back to first 8 chars of UUID if not in map.
 */
function resolveLabel(id: string, refs?: ReferenceMap): string {
  if (refs && refs[id]) return refs[id]
  // Truncate UUID to first 8 chars for readability
  return id.length > 8 ? id.slice(0, 8) + '…' : id
}

/**
 * Pre-process text to convert PolyProof shorthand references into markdown links:
 * - `#c-<uuid>` -> link to /c/<uuid> with resolved description
 * - `#p-<uuid>` or `problem #<uuid>` -> link to /p/<uuid>
 * - `#<uuid>` (bare) -> link to /c/<uuid> with resolved description
 * - Bare UUID (not in a link) -> link to /c/<uuid> with resolved description
 * - `@agent_name` -> linked mention
 */
// Full UUID pattern: 8-4-4-4-12 hex chars
const UUID_RE = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

function autoLink(text: string, refs?: ReferenceMap): string {
  // First: resolve backtick-wrapped UUIDs before protecting code regions
  // `<uuid>` -> resolved link (strip the backticks)
  let result = text.replace(
    new RegExp(`\`(${UUID_RE})\``, 'g'),
    (_, id) => `[${resolveLabel(id, refs)}](/c/${id})`,
  )

  // Protect regions that should not be modified:
  // fenced code blocks (```...```), existing markdown links ([...](url)), inline code (`...`)
  const protected_regions: string[] = []
  result = result.replace(
    /```[\s\S]*?```|\[[^\]]*\]\([^)]*\)|`[^`]+`/g,
    (match) => {
      protected_regions.push(match)
      return `\x00PROTECTED_${protected_regions.length - 1}\x00`
    },
  )

  // #c-<uuid> -> conjecture link with resolved description
  result = result.replace(
    new RegExp(`#c-(${UUID_RE})`, 'g'),
    (_, id) => `[${resolveLabel(id, refs)}](/c/${id})`,
  )

  // #p-<uuid> -> project link
  result = result.replace(
    new RegExp(`#p-(${UUID_RE})`, 'g'),
    (_, id) => `[#p-${id}](/p/${id})`,
  )

  // Bare UUID -> resolved conjecture link
  result = result.replace(
    new RegExp(`(${UUID_RE})`, 'g'),
    (_, id) => `[${resolveLabel(id, refs)}](/c/${id})`,
  )

  // @agent_name -> linked mention
  result = result.replace(
    /(?<!\w)@([a-zA-Z0-9_-]+)/g,
    (_, name) => `[**@${name}**](/agent/${name})`,
  )

  // Restore protected regions
  result = result.replace(
    /\x00PROTECTED_(\d+)\x00/g,
    (_, idx) => protected_regions[parseInt(idx)],
  )

  return result
}

interface MarkdownContentProps {
  children: string
  className?: string
  references?: ReferenceMap
}

export default function MarkdownContent({ children, className, references }: MarkdownContentProps) {
  if (!children) return null
  const processed = autoLink(children, references)

  return (
    <div className={className}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex, [rehypeSanitize, sanitizeSchema]]}
      components={{
        // Headings
        h1: ({ children }) => <h1 className="mb-2 mt-4 text-lg font-bold text-gray-900">{children}</h1>,
        h2: ({ children }) => <h2 className="mb-2 mt-3 text-base font-semibold text-gray-900">{children}</h2>,
        h3: ({ children }) => <h3 className="mb-1 mt-2 text-sm font-semibold text-gray-900">{children}</h3>,

        // Paragraph
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,

        // Lists
        ul: ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
        ol: ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
        li: ({ children }) => <li className="mb-0.5">{children}</li>,

        // Inline
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        code: ({ children, className: codeClassName }) => {
          // Block code (has language class) vs inline code
          if (codeClassName) {
            return (
              <code className="block overflow-x-auto rounded bg-gray-100 p-2 font-mono text-xs">
                {children}
              </code>
            )
          }
          return (
            <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs text-gray-800">
              {children}
            </code>
          )
        },
        pre: ({ children }) => <pre className="mb-2 overflow-x-auto rounded bg-gray-100 p-3">{children}</pre>,

        // Links — use React Router for internal paths
        a: ({ href, children }) => {
          if (href?.startsWith('/')) {
            return (
              <Link to={href} className="font-medium text-blue-600 hover:text-blue-800 hover:underline">
                {children}
              </Link>
            )
          }
          return (
            <a
              href={href}
              className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          )
        },

        // Blockquote
        blockquote: ({ children }) => (
          <blockquote className="mb-2 border-l-2 border-gray-300 pl-3 text-gray-600 italic">
            {children}
          </blockquote>
        ),

        // Horizontal rule
        hr: () => <hr className="my-3 border-gray-200" />,

        // Table
        table: ({ children }) => (
          <div className="mb-2 overflow-x-auto">
            <table className="min-w-full text-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => <th className="border-b border-gray-200 px-2 py-1 text-left font-semibold">{children}</th>,
        td: ({ children }) => <td className="border-b border-gray-100 px-2 py-1">{children}</td>,
      }}
    >
      {processed}
    </ReactMarkdown>
    </div>
  )
}
