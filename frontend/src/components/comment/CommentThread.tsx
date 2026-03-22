import { useMemo } from 'react'
import CommentItem from './CommentItem'
import type { Comment, CommentThread as CommentThreadType } from '../../types'

interface CommentThreadProps {
  thread: CommentThreadType
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
}: {
  comment: Comment
  childrenMap: Map<string, Comment[]>
  depth: number
}) {
  const children = childrenMap.get(comment.id) ?? []

  return (
    <>
      <CommentItem comment={comment} depth={depth} />
      {children.map((child) => (
        <CommentWithReplies
          key={child.id}
          comment={child}
          childrenMap={childrenMap}
          depth={depth + 1}
        />
      ))}
    </>
  )
}

export default function CommentThread({ thread }: CommentThreadProps) {
  const { roots, childrenMap } = useMemo(
    () => buildReplyTree(thread.comments_after_summary),
    [thread.comments_after_summary],
  )

  return (
    <div className="space-y-3">
      {/* Summary comment */}
      {thread.summary && (
        <CommentItem comment={thread.summary} depth={0} />
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
        />
      ))}
    </div>
  )
}
