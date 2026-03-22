import { useMemo } from 'react'
import CommentItem from './CommentItem'
import type { Comment, CommentThread as CommentThreadType } from '../../types'
import type { ReferenceMap } from '../ui/MarkdownContent'

interface CommentThreadProps {
  thread: CommentThreadType
  references?: ReferenceMap
}

/** Build a tree of comments from flat list using parent_comment_id */
function buildReplyTree(comments: Comment[]): { roots: Comment[]; childrenMap: Map<string, Comment[]> } {
  const childrenMap = new Map<string, Comment[]>()
  const roots: Comment[] = []

  for (const comment of comments) {
    if (comment.parent_comment_id) {
      if (!childrenMap.has(comment.parent_comment_id)) {
        childrenMap.set(comment.parent_comment_id, [])
      }
      childrenMap.get(comment.parent_comment_id)!.push(comment)
    } else {
      roots.push(comment)
    }
  }

  return { roots, childrenMap }
}

function CommentWithReplies({
  comment,
  childrenMap,
  depth,
  references,
}: {
  comment: Comment
  childrenMap: Map<string, Comment[]>
  depth: number
  references?: ReferenceMap
}) {
  const children = childrenMap.get(comment.id) ?? []

  return (
    <>
      <CommentItem comment={comment} depth={depth} references={references} />
      {children.map((child) => (
        <CommentWithReplies
          key={child.id}
          comment={child}
          childrenMap={childrenMap}
          depth={depth + 1}
          references={references}
        />
      ))}
    </>
  )
}

export default function CommentThread({ thread, references }: CommentThreadProps) {
  const { roots, childrenMap } = useMemo(
    () => buildReplyTree(thread.comments_after_summary),
    [thread.comments_after_summary],
  )

  return (
    <div className="space-y-3">
      {/* Summary comment */}
      {thread.summary && (
        <CommentItem comment={thread.summary} depth={0} references={references} />
      )}

      {/* Comments after summary */}
      {roots.length === 0 && !thread.summary && (
        <p className="py-4 text-center text-sm text-gray-400">No discussion yet.</p>
      )}

      {roots.map((comment) => (
        <CommentWithReplies
          key={comment.id}
          comment={comment}
          childrenMap={childrenMap}
          depth={0}
          references={references}
        />
      ))}
    </div>
  )
}
