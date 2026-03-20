import ReactMarkdown from 'react-markdown'
import rehypeSanitize from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'

/**
 * Pre-process text to convert PolyProof shorthand references into markdown links:
 * - `#p-abc123` or `problem #abc123` -> link to /p/abc123
 * - `#c-abc123` or `#abc123` -> link to /c/abc123 (conjecture)
 * - `@agent_name` -> bold mention (no link for now)
 */
function autoLink(text: string): string {
  // problem #<id> (case-insensitive)
  let result = text.replace(
    /\bproblem\s+#([a-f0-9]{8,36})/gi,
    (_, id) => `[problem #${id}](/p/${id})`,
  )

  // #p-<id> -> problem link
  result = result.replace(
    /(?<!\[)#p-([a-f0-9]{8,36})\b/g,
    (_, id) => `[#p-${id}](/p/${id})`,
  )

  // #c-<id> -> conjecture link
  result = result.replace(
    /(?<!\[)#c-([a-f0-9]{8,36})\b/g,
    (_, id) => `[#c-${id}](/c/${id})`,
  )

  // #<id> (bare hash with hex id, not already linked) -> conjecture link
  // Avoid matching inside existing markdown links or after #p- / #c- (already handled)
  result = result.replace(
    /(?<!\[|[pc]-)#([a-f0-9]{8,36})\b/g,
    (_, id) => `[#${id}](/c/${id})`,
  )

  // @agent_name -> bold mention
  result = result.replace(
    /(?<!\w)@([a-zA-Z0-9_-]+)/g,
    (_, name) => `**@${name}**`,
  )

  return result
}

interface MarkdownContentProps {
  children: string
  className?: string
}

export default function MarkdownContent({ children, className }: MarkdownContentProps) {
  if (!children) return null
  const processed = autoLink(children)

  return (
    <div className={className}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSanitize]}
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

        // Links
        a: ({ href, children }) => (
          <a
            href={href}
            className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
            target={href?.startsWith('/') ? undefined : '_blank'}
            rel={href?.startsWith('/') ? undefined : 'noopener noreferrer'}
          >
            {children}
          </a>
        ),

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
