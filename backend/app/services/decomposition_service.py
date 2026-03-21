"""Decomposition service: update_decomposition and revert_decomposition.

Handles the creation and modification of proof tree decompositions,
including the sorry-proof validation, child diffing, invalidation cascades,
and reactivation of previously invalidated children.
"""

import logging
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.services import lean_client

logger = logging.getLogger(__name__)

# Regex to extract (name, type) pairs from sorry-proof
SORRY_PATTERN = re.compile(r"have\s+(\w+)\s*:\s*(.+?)\s*:=\s*sorry")


def _normalize_lean(stmt: str) -> str:
    """Normalize a Lean statement by stripping and collapsing whitespace."""
    return " ".join(stmt.split())


async def update(
    parent_id: UUID,
    children: list[dict],
    sorry_proof: str,
    mega_agent_id: UUID,
    db: AsyncSession,
) -> dict:
    """Create or modify a decomposition.

    Steps:
    1. Validate parent is open or decomposed
    2. Validate children (no empty statements, no duplicates)
    3. Verify sorry_proof compiles via lean_client
    4. Parse sorry_proof for have-sorry patterns, validate count/types match
    5. Diff existing children by normalized lean_statement
    6. Apply diff: preserve matched, create new, invalidate removed, reactivate
    7. Update parent sorry_proof and status
    8. Log event
    9. If all children proved, trigger assembly
    """
    # Step 1: Validate parent
    parent = await db.get(Conjecture, parent_id)
    if not parent:
        return {"status": "error", "error": f"Conjecture {parent_id} not found."}

    if parent.status not in ("open", "decomposed"):
        return {
            "status": "error",
            "error": f"Cannot decompose a {parent.status} conjecture.",
        }

    project_id = parent.project_id
    was_already_decomposed = parent.status == "decomposed"

    # Step 2: Validate children
    if not children:
        return {"status": "error", "error": "At least one child is required."}

    for i, child in enumerate(children):
        if not child.get("lean_statement", "").strip():
            return {
                "status": "error",
                "error": f"Child {i} has empty lean_statement.",
            }
        if not child.get("description", "").strip():
            return {
                "status": "error",
                "error": f"Child {i} has empty description.",
            }

    # Check for duplicate lean_statements among new children
    normalized_new = [_normalize_lean(c["lean_statement"]) for c in children]
    if len(set(normalized_new)) != len(normalized_new):
        return {
            "status": "error",
            "error": "Duplicate lean_statements in children list.",
        }

    # Step 3: Verify sorry_proof compiles (sorry is allowed)
    lean_result = await lean_client.verify_sorry_proof(sorry_proof)
    if lean_result.status != "passed":
        return {
            "status": "error",
            "error": f"Sorry-proof failed to compile: {lean_result.error}",
        }

    # Step 4: Parse sorry_proof and validate structure
    sorry_matches = SORRY_PATTERN.findall(sorry_proof)
    sorry_types = [_normalize_lean(m[1]) for m in sorry_matches]

    if len(sorry_types) != len(children):
        return {
            "status": "error",
            "error": (
                f"Sorry-proof has {len(sorry_types)} sorry placeholders "
                f"but {len(children)} children were provided."
            ),
        }

    # Validate each child's lean_statement matches a sorry placeholder
    unmatched_children = []
    sorry_types_remaining = list(sorry_types)
    for i, child in enumerate(children):
        norm = _normalize_lean(child["lean_statement"])
        if norm in sorry_types_remaining:
            sorry_types_remaining.remove(norm)
        else:
            unmatched_children.append(i)

    if unmatched_children:
        return {
            "status": "error",
            "error": (
                f"Children at indices {unmatched_children} do not match "
                f"any sorry placeholder in the sorry-proof. "
                f"Unmatched sorry types: {sorry_types_remaining}"
            ),
        }

    # Step 5: Diff against existing children
    existing_children_result = await db.execute(
        select(Conjecture).where(Conjecture.parent_id == parent_id).order_by(Conjecture.created_at)
    )
    existing_children = list(existing_children_result.scalars().all())

    # Build maps for diffing
    existing_by_norm: dict[str, list[Conjecture]] = {}
    for ec in existing_children:
        norm = _normalize_lean(ec.lean_statement)
        existing_by_norm.setdefault(norm, []).append(ec)

    # Step 6: Apply diff
    children_created: list[str] = []
    children_preserved: list[str] = []
    children_invalidated: list[str] = []
    children_reactivated: list[str] = []
    matched_existing_ids: set[UUID] = set()

    for child_spec in children:
        norm = _normalize_lean(child_spec["lean_statement"])
        priority = child_spec.get("priority", "normal")

        # Check for a match in existing children
        candidates = existing_by_norm.get(norm, [])
        matched = None
        for candidate in candidates:
            if candidate.id not in matched_existing_ids:
                matched = candidate
                matched_existing_ids.add(candidate.id)
                break

        if matched:
            # MATCH: preserve status/proof/comments, update description/priority
            await db.execute(
                sa_update(Conjecture)
                .where(Conjecture.id == matched.id)
                .values(
                    description=child_spec["description"],
                    priority=priority,
                )
            )

            if matched.status == "invalid":
                # REACTIVATE: restore previous status
                restored_status = "open"
                if matched.proof_lean and matched.proved_by:
                    restored_status = "proved"
                await db.execute(
                    sa_update(Conjecture)
                    .where(Conjecture.id == matched.id)
                    .values(status=restored_status)
                )
                children_reactivated.append(str(matched.id))
            else:
                children_preserved.append(str(matched.id))
        else:
            # NEW: create a new child conjecture
            new_child = Conjecture(
                id=uuid4(),
                project_id=project_id,
                parent_id=parent_id,
                lean_statement=child_spec["lean_statement"],
                description=child_spec["description"],
                status="open",
                priority=priority,
            )
            db.add(new_child)
            await db.flush()
            children_created.append(str(new_child.id))

    # REMOVED: existing non-invalid children not matched
    for ec in existing_children:
        if ec.id not in matched_existing_ids and ec.status != "invalid":
            invalidated = await _invalidate_with_descendants(ec.id, db)
            children_invalidated.extend(invalidated)

    # Step 7: Update parent
    await db.execute(
        sa_update(Conjecture)
        .where(Conjecture.id == parent_id)
        .values(
            sorry_proof=sorry_proof,
            status="decomposed",
        )
    )

    # Step 8: Log event
    if was_already_decomposed:
        event_type = "decomposition_updated"
        details = {
            "created": children_created,
            "preserved": children_preserved,
            "invalidated": children_invalidated,
            "reactivated": children_reactivated,
        }
    else:
        event_type = "decomposition_created"
        all_child_ids = children_created + children_preserved + children_reactivated
        details = {
            "children_ids": all_child_ids,
            "children_count": len(all_child_ids),
        }

    activity = ActivityLog(
        id=uuid4(),
        project_id=project_id,
        event_type=event_type,
        conjecture_id=parent_id,
        agent_id=mega_agent_id,
        details=details,
        created_at=datetime.now(UTC),
    )
    db.add(activity)

    await db.commit()

    # Step 9: Check if all children are already proved (triggers assembly)
    all_active_children = await db.execute(
        select(Conjecture.status).where(
            Conjecture.parent_id == parent_id,
            Conjecture.status != "invalid",
        )
    )
    active_statuses = [r[0] for r in all_active_children.all()]
    if active_statuses and all(s == "proved" for s in active_statuses):
        try:
            from app.services import assembly_service

            await assembly_service.check_and_assemble(parent_id, db)
        except Exception:
            logger.exception("Assembly check failed after decomposition for %s", parent_id)

    return {
        "status": "ok",
        "parent_id": str(parent_id),
        "parent_status": "decomposed",
        "children_created": children_created,
        "children_preserved": children_preserved,
        "children_invalidated": children_invalidated,
        "children_reactivated": children_reactivated,
    }


async def revert(
    conjecture_id: UUID,
    reason: str,
    mega_agent_id: UUID,
    db: AsyncSession,
) -> dict:
    """Revert a decomposition: invalidate all children, clear sorry_proof.

    Steps:
    1. Validate conjecture is decomposed
    2. Invalidate all children and descendants
    3. Clear sorry_proof, status -> open
    4. Post reason as comment
    5. Log event
    """
    # Step 1: Validate
    conjecture = await db.get(Conjecture, conjecture_id)
    if not conjecture:
        return {"status": "error", "error": f"Conjecture {conjecture_id} not found."}

    if conjecture.status != "decomposed":
        return {"status": "error", "error": "Conjecture is not decomposed."}

    project_id = conjecture.project_id

    # Step 2: Invalidate all children and descendants
    invalidated_ids = await _invalidate_children_recursive(conjecture_id, db)

    # Step 3: Revert parent
    await db.execute(
        sa_update(Conjecture)
        .where(Conjecture.id == conjecture_id)
        .values(
            status="open",
            sorry_proof=None,
        )
    )

    # Step 4: Post explanation comment
    comment = Comment(
        id=uuid4(),
        conjecture_id=conjecture_id,
        author_id=mega_agent_id,
        body=f"Decomposition reverted: {reason}",
        is_summary=False,
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    await db.flush()

    # Log comment event
    comment_activity = ActivityLog(
        id=uuid4(),
        project_id=project_id,
        event_type="comment",
        conjecture_id=conjecture_id,
        agent_id=mega_agent_id,
        details={"comment_id": str(comment.id)},
        created_at=datetime.now(UTC),
    )
    db.add(comment_activity)

    # Step 5: Log revert event
    revert_activity = ActivityLog(
        id=uuid4(),
        project_id=project_id,
        event_type="decomposition_reverted",
        conjecture_id=conjecture_id,
        agent_id=mega_agent_id,
        details={"children_invalidated": invalidated_ids},
        created_at=datetime.now(UTC),
    )
    db.add(revert_activity)

    await db.commit()

    return {
        "status": "ok",
        "conjecture_id": str(conjecture_id),
        "conjecture_status": "open",
        "children_invalidated": invalidated_ids,
    }


async def _invalidate_with_descendants(conjecture_id: UUID, db: AsyncSession) -> list[str]:
    """Invalidate a conjecture and all its descendants. Returns list of invalidated IDs."""
    invalidated_query = text("""
        WITH RECURSIVE descendants AS (
            SELECT CAST(:root_id AS uuid) AS id
            UNION ALL
            SELECT c.id FROM conjectures c
            JOIN descendants d ON c.parent_id = d.id
        )
        UPDATE conjectures SET status = 'invalid'
        WHERE id IN (SELECT id FROM descendants)
        AND status != 'invalid'
        RETURNING id
    """)
    result = await db.execute(invalidated_query, {"root_id": str(conjecture_id)})
    return [str(row[0]) for row in result.all()]


async def _invalidate_children_recursive(parent_id: UUID, db: AsyncSession) -> list[str]:
    """Invalidate all children of a conjecture and their descendants."""
    invalidated_query = text("""
        WITH RECURSIVE descendants AS (
            SELECT id FROM conjectures WHERE parent_id = :parent_id
            UNION ALL
            SELECT c.id FROM conjectures c
            JOIN descendants d ON c.parent_id = d.id
        )
        UPDATE conjectures SET status = 'invalid'
        WHERE id IN (SELECT id FROM descendants)
        AND status != 'invalid'
        RETURNING id
    """)
    result = await db.execute(invalidated_query, {"parent_id": str(parent_id)})
    return [str(row[0]) for row in result.all()]
