"""Conjecture detail, tree, and list endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import DbSession
from app.api.rate_limit import ip_limiter
from app.errors import NotFoundError
from app.schemas.conjecture import (
    ConjectureDetail,
    ConjectureSummary,
)
from app.services import comment_service, conjecture_service

router = APIRouter()


@router.get("/{conjecture_id}", response_model=ConjectureDetail)
@ip_limiter.limit("100/minute")
async def get_conjecture(
    request: Request,
    conjecture_id: UUID,
    db: DbSession,
) -> ConjectureDetail:
    """Full context for a single conjecture."""
    conjecture = await conjecture_service.get_by_id(db, conjecture_id)
    if not conjecture:
        raise NotFoundError("Conjecture")

    # Build author responses
    proved_by = await conjecture_service._build_author(db, conjecture.proved_by)
    disproved_by = await conjecture_service._build_author(db, conjecture.disproved_by)

    # Get related data
    parent_chain = await conjecture_service.get_parent_chain(db, conjecture)
    proved_siblings = await conjecture_service.get_proved_siblings(db, conjecture)
    children = await conjecture_service.get_children(db, conjecture.id)
    comment_count = await conjecture_service.get_comment_count(db, conjecture.id)

    # Get comment thread
    comments = await comment_service.get_thread(db, conjecture_id=conjecture_id)

    return ConjectureDetail(
        id=conjecture.id,
        project_id=conjecture.project_id,
        parent_id=conjecture.parent_id,
        lean_statement=conjecture.lean_statement,
        description=conjecture.description,
        status=conjecture.status,
        priority=conjecture.priority,
        sorry_proof=conjecture.sorry_proof,
        proof_lean=conjecture.proof_lean,
        proved_by=proved_by,
        disproved_by=disproved_by,
        comment_count=comment_count,
        created_at=conjecture.created_at,
        closed_at=conjecture.closed_at,
        parent_chain=[ConjectureSummary(**p) for p in parent_chain],
        proved_siblings=[ConjectureSummary(**s) for s in proved_siblings],
        children=[ConjectureSummary(**c) for c in children],
        comments=comments,
    )
