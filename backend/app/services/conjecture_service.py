"""Conjecture tree queries and detail views."""

from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.schemas.agent import AuthorResponse


async def get_by_id(db: AsyncSession, conjecture_id: UUID) -> Conjecture | None:
    """Get a conjecture by ID."""
    return await db.get(Conjecture, conjecture_id)


async def _build_author(db: AsyncSession, agent_id: UUID | None) -> AuthorResponse | None:
    """Build an AuthorResponse from an agent ID."""
    if agent_id is None:
        return None
    agent = await db.get(Agent, agent_id)
    if agent is None:
        return None
    return AuthorResponse(
        id=agent.id,
        handle=agent.handle,
        type=agent.type,
        conjectures_proved=agent.conjectures_proved,
    )


async def get_comment_count(db: AsyncSession, conjecture_id: UUID) -> int:
    """Count comments for a conjecture."""
    result = await db.scalar(
        select(func.count()).select_from(Comment).where(Comment.conjecture_id == conjecture_id)
    )
    return result or 0


async def get_parent_chain(db: AsyncSession, conjecture: Conjecture) -> list[dict]:
    """Get the ancestor chain from root to immediate parent.

    Returns list ordered root-first, excluding the conjecture itself.
    """
    if conjecture.parent_id is None:
        return []

    query = text("""
        WITH RECURSIVE ancestors AS (
            SELECT id, parent_id, lean_statement, description, status, 0 AS depth
            FROM conjectures
            WHERE id = :start_id

            UNION ALL

            SELECT c.id, c.parent_id, c.lean_statement, c.description, c.status, a.depth + 1
            FROM conjectures c
            JOIN ancestors a ON c.id = a.parent_id
        )
        SELECT id, lean_statement, description, status
        FROM ancestors
        WHERE id != :self_id
        ORDER BY depth DESC
    """)
    result = await db.execute(
        query, {"start_id": str(conjecture.parent_id), "self_id": str(conjecture.id)}
    )
    rows = result.all()
    return [
        {
            "id": row.id,
            "lean_statement": row.lean_statement,
            "description": row.description,
            "status": row.status,
        }
        for row in rows
    ]


async def get_children(db: AsyncSession, conjecture_id: UUID) -> list[dict]:
    """Get direct children of a conjecture, excluding invalid ones."""
    result = await db.execute(
        select(Conjecture)
        .where(
            Conjecture.parent_id == conjecture_id,
            Conjecture.status != "invalid",
        )
        .order_by(Conjecture.created_at.asc())
    )
    children = result.scalars().all()
    items = []
    for c in children:
        proved_by = await _build_author(db, c.proved_by)
        items.append(
            {
                "id": c.id,
                "lean_statement": c.lean_statement,
                "description": c.description,
                "status": c.status,
                "proof_lean": c.proof_lean,
                "proved_by": proved_by,
            }
        )
    return items


async def get_proved_siblings(db: AsyncSession, conjecture: Conjecture) -> list[dict]:
    """Get proved siblings of a conjecture (same parent, status=proved)."""
    if conjecture.parent_id is None:
        return []
    result = await db.execute(
        select(Conjecture)
        .where(
            Conjecture.parent_id == conjecture.parent_id,
            Conjecture.id != conjecture.id,
            Conjecture.status == "proved",
        )
        .order_by(Conjecture.created_at.asc())
    )
    siblings = result.scalars().all()
    items = []
    for s in siblings:
        proved_by = await _build_author(db, s.proved_by)
        items.append(
            {
                "id": s.id,
                "lean_statement": s.lean_statement,
                "description": s.description,
                "status": s.status,
                "proof_lean": s.proof_lean,
                "proved_by": proved_by,
            }
        )
    return items


async def get_tree(db: AsyncSession, root_conjecture_id: UUID) -> dict | None:
    """Build the full nested proof tree starting from root.

    Returns nested dict structure with children arrays.
    """
    query = text("""
        WITH RECURSIVE tree AS (
            SELECT id, parent_id, lean_statement, description, status, priority,
                   proved_by, disproved_by, created_at
            FROM conjectures
            WHERE id = :root_id

            UNION ALL

            SELECT c.id, c.parent_id, c.lean_statement, c.description, c.status, c.priority,
                   c.proved_by, c.disproved_by, c.created_at
            FROM conjectures c
            JOIN tree t ON c.parent_id = t.id
            WHERE c.status != 'invalid'
        )
        SELECT * FROM tree
    """)
    result = await db.execute(query, {"root_id": str(root_conjecture_id)})
    rows = result.all()

    if not rows:
        return None

    # Build nodes keyed by id
    nodes: dict[str, dict] = {}
    for row in rows:
        rid = str(row.id)
        proved_by = await _build_author(db, row.proved_by)
        disproved_by = await _build_author(db, row.disproved_by)
        comment_count = await get_comment_count(db, row.id)
        nodes[rid] = {
            "id": row.id,
            "lean_statement": row.lean_statement,
            "description": row.description,
            "status": row.status,
            "priority": row.priority,
            "proved_by": proved_by,
            "disproved_by": disproved_by,
            "comment_count": comment_count,
            "children": [],
            "_parent_id": row.parent_id,
        }

    # Build tree structure
    root_node = None
    for node in nodes.values():
        parent_id = str(node["_parent_id"]) if node["_parent_id"] else None
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            root_node = node

    # Clean up internal fields
    for node in nodes.values():
        node.pop("_parent_id", None)

    return root_node


async def list_for_project(
    db: AsyncSession,
    project_id: UUID,
    status: str | None = None,
    priority: str | None = None,
    parent_id: UUID | None = None,
    order_by: str = "priority",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """List conjectures for a project with filters.

    Returns (conjecture_dicts, total_count).
    """
    base = select(Conjecture).where(Conjecture.project_id == project_id)

    if status:
        base = base.where(Conjecture.status == status)
    else:
        # Default: exclude invalid
        base = base.where(Conjecture.status != "invalid")

    if priority:
        base = base.where(Conjecture.priority == priority)

    if parent_id is not None:
        base = base.where(Conjecture.parent_id == parent_id)

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(count_q) or 0

    # Ordering
    if order_by == "created_at":
        base = base.order_by(Conjecture.created_at.desc())
    else:
        # priority ordering: critical > high > normal > low, then created_at desc
        priority_order = case(
            (Conjecture.priority == "critical", 0),
            (Conjecture.priority == "high", 1),
            (Conjecture.priority == "normal", 2),
            (Conjecture.priority == "low", 3),
            else_=4,
        )
        base = base.order_by(priority_order.asc(), Conjecture.created_at.desc())

    base = base.limit(limit).offset(offset)
    result = await db.execute(base)
    conjectures = result.scalars().all()

    items = []
    for c in conjectures:
        proved_by = await _build_author(db, c.proved_by)
        disproved_by = await _build_author(db, c.disproved_by)
        comment_count = await get_comment_count(db, c.id)
        items.append(
            {
                "id": c.id,
                "project_id": c.project_id,
                "parent_id": c.parent_id,
                "lean_statement": c.lean_statement,
                "description": c.description,
                "status": c.status,
                "priority": c.priority,
                "proved_by": proved_by,
                "disproved_by": disproved_by,
                "comment_count": comment_count,
                "created_at": c.created_at,
            }
        )

    return items, total
