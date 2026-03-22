"""Automatic parent assembly — substitutes sorry with child proofs."""

import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conjecture import Conjecture
from app.services import activity_service, lean_client


def _normalize_whitespace(s: str) -> str:
    """Collapse all whitespace to single spaces and strip."""
    return " ".join(s.split())


def _parse_sorry_positions(sorry_proof: str) -> list[tuple[str, str, str]]:
    r"""Parse ``have <name> : <type> := sorry`` patterns from a sorry-proof.

    Returns list of (full_match, name, type) tuples.
    The regex is non-greedy on the type and anchored to ``:= sorry``.
    """
    pattern = r"(have\s+(\w+)\s*:\s*(.+?)\s*:=\s*sorry)"
    return re.findall(pattern, sorry_proof, re.DOTALL)


async def check_and_assemble(conjecture_id: UUID, db: AsyncSession) -> bool:
    """Check if the parent of the given conjecture can be assembled.

    If all non-invalid siblings are proved, builds the assembled proof by
    substituting sorry with child proofs and compiles it.

    Returns True if the parent was successfully proved (assembly succeeded).
    """
    conjecture = await db.get(Conjecture, conjecture_id)
    if conjecture is None or conjecture.parent_id is None:
        return False

    parent = await db.get(Conjecture, conjecture.parent_id)
    if parent is None or parent.status != "decomposed":
        return False

    # Check if all non-invalid children are proved.
    # Use populate_existing to bypass the identity map and get fresh data
    # from the database (child proofs may have been set via raw SQL).
    children_result = await db.execute(
        select(Conjecture)
        .where(
            Conjecture.parent_id == parent.id,
            Conjecture.status != "invalid",
        )
        .order_by(Conjecture.created_at.asc())
        .execution_options(populate_existing=True)
    )
    children = list(children_result.scalars().all())

    total = len(children)
    proved = sum(1 for c in children if c.status == "proved")

    if total == 0 or total != proved:
        return False

    # All children proved — attempt assembly
    if not parent.sorry_proof:
        await activity_service.record_event(
            db,
            project_id=parent.project_id,
            event_type="assembly_failure",
            conjecture_id=parent.id,
            details={"error": "Parent has no sorry_proof to assemble"},
        )
        return False

    # Parse sorry positions
    positions = _parse_sorry_positions(parent.sorry_proof)
    if len(positions) != len(children):
        await activity_service.record_event(
            db,
            project_id=parent.project_id,
            event_type="assembly_failure",
            conjecture_id=parent.id,
            details={
                "error": (
                    f"Sorry position count ({len(positions)}) does not match "
                    f"children count ({len(children)})"
                )
            },
        )
        return False

    # Match children to sorry positions by normalized lean_statement
    assembled = parent.sorry_proof
    matched_children: list[UUID] = []

    for full_match, _name, sorry_type in positions:
        normalized_sorry = _normalize_whitespace(sorry_type)
        matched_child = None
        for child in children:
            if _normalize_whitespace(child.lean_statement) == normalized_sorry:
                matched_child = child
                break

        if matched_child is None:
            await activity_service.record_event(
                db,
                project_id=parent.project_id,
                event_type="assembly_failure",
                conjecture_id=parent.id,
                details={"error": f"No child matches sorry type: {sorry_type}"},
            )
            return False

        if matched_child.proof_lean is None:
            await activity_service.record_event(
                db,
                project_id=parent.project_id,
                event_type="assembly_failure",
                conjecture_id=parent.id,
                details={"error": f"Child {matched_child.id} is proved but has no proof_lean"},
            )
            return False

        # Replace ``<name> : <type> := sorry`` with ``<name> : <type> := by <proof>``
        replacement = full_match.replace(":= sorry", f":= by {matched_child.proof_lean}")
        assembled = assembled.replace(full_match, replacement, 1)
        matched_children.append(matched_child.id)

    # Compile the assembled proof
    from app.services.proof_service import _get_lean_header

    lean_header = await _get_lean_header(db, parent.project_id)
    result = await lean_client.verify_sorry_proof(assembled, lean_header=lean_header)

    if result.status != "passed":
        await activity_service.record_event(
            db,
            project_id=parent.project_id,
            event_type="assembly_failure",
            conjecture_id=parent.id,
            details={"error": result.error or "Assembly compilation failed"},
        )
        return False

    # Assembly succeeded — extract tactics from the assembled proof.
    # Store the full assembled Lean code as proof_lean for the parent.
    # The assembled code is the complete theorem, so we store the full thing.
    # For consistency with children (which store just tactics), we store
    # the full assembled code since it includes the theorem wrapper.
    rows_updated = (
        await db.execute(
            text("""
                UPDATE conjectures
                SET status = 'proved',
                    proof_lean = :assembled,
                    proved_by = NULL,
                    closed_at = NOW()
                WHERE id = :parent_id AND status = 'decomposed'
            """),
            {"assembled": assembled, "parent_id": str(parent.id)},
        )
    ).rowcount

    if rows_updated == 0:
        # Race condition: parent status changed between check and update
        return False

    # Refresh parent to reflect the update
    await db.refresh(parent)

    # Log assembly success
    await activity_service.record_event(
        db,
        project_id=parent.project_id,
        event_type="assembly_success",
        conjecture_id=parent.id,
        details={"children_ids": [str(cid) for cid in matched_children]},
    )

    # Fire project_completed if parent is the root
    from app.services.proof_service import _check_project_completed

    await _check_project_completed(parent, db)

    # Recurse upward: check if grandparent can now be assembled
    if parent.parent_id is not None:
        await check_and_assemble(parent.id, db)

    return True
