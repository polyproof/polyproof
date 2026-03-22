"""Proof and disproof submission pipelines."""

from uuid import UUID

from sqlalchemy import select as sa_select
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conjecture import Conjecture
from app.models.project import Project
from app.schemas.proof import DisproofResult, ProofResult
from app.services import activity_service, assembly_service, lean_client


async def _get_lean_header(db: AsyncSession, project_id: UUID) -> str | None:
    """Look up the project's lean_header."""
    result = await db.execute(sa_select(Project.lean_header).where(Project.id == project_id))
    row = result.first()
    return row[0] if row else None


async def submit_proof(
    conjecture_id: UUID,
    lean_code: str,
    agent_id: UUID,
    db: AsyncSession,
) -> ProofResult:
    """Submit a proof for a conjecture.

    Wraps tactics with the conjecture's lean_statement using a locked signature,
    compiles via Lean CI, and on success updates the conjecture to proved.
    """
    # Step 1: Validate conjecture exists
    conjecture = await db.get(Conjecture, conjecture_id)
    if conjecture is None:
        return ProofResult(
            status="not_found",
            conjecture_id=conjecture_id,
            error="Conjecture not found",
        )

    # Step 2: Check status (before acquiring lock)
    if conjecture.status in ("proved", "disproved", "invalid"):
        return ProofResult(
            status="already_proved",
            conjecture_id=conjecture_id,
            message="This conjecture is already proved/disproved/invalid.",
        )

    # Step 3: SELECT FOR UPDATE (race condition prevention)
    lock_result = await db.execute(
        text("SELECT id, status FROM conjectures WHERE id = :id FOR UPDATE"),
        {"id": str(conjecture_id)},
    )
    locked_row = lock_result.first()
    if locked_row is None:
        return ProofResult(
            status="not_found",
            conjecture_id=conjecture_id,
            error="Conjecture not found",
        )
    if locked_row.status not in ("open", "decomposed"):
        return ProofResult(
            status="already_proved",
            conjecture_id=conjecture_id,
            message="This conjecture is already proved/disproved/invalid.",
        )

    was_decomposed = locked_row.status == "decomposed"

    # Step 4: Compile with locked signature
    lean_header = await _get_lean_header(db, conjecture.project_id)
    result = await lean_client.verify_proof(
        lean_statement=conjecture.lean_statement,
        tactics=lean_code,
        conjecture_id=conjecture_id,
        lean_header=lean_header,
    )

    # Step 5a: Lean rejected or timed out
    if result.status == "rejected":
        return ProofResult(
            status="rejected",
            conjecture_id=conjecture_id,
            error=result.error,
            message="Proof rejected. See error for details.",
        )

    if result.status == "timeout":
        return ProofResult(
            status="timeout",
            conjecture_id=conjecture_id,
            error=result.error or "Compilation timed out (60s limit).",
        )

    # Step 5b: Lean passed — update conjecture atomically
    rows_updated = (
        await db.execute(
            text("""
                UPDATE conjectures
                SET status = 'proved',
                    proof_lean = :lean_code,
                    proved_by = :agent_id,
                    closed_at = NOW()
                WHERE id = :conjecture_id AND status IN ('open', 'decomposed')
            """),
            {
                "lean_code": lean_code,
                "agent_id": str(agent_id),
                "conjecture_id": str(conjecture_id),
            },
        )
    ).rowcount

    if rows_updated == 0:
        # Race condition: another proof landed between lock and update
        return ProofResult(
            status="already_proved",
            conjecture_id=conjecture_id,
            message="This conjecture was proved by another agent.",
        )

    # Increment agent counter atomically
    await db.execute(
        text("UPDATE agents SET conjectures_proved = conjectures_proved + 1 WHERE id = :id"),
        {"id": str(agent_id)},
    )

    # Log proof event
    await activity_service.record_event(
        db,
        project_id=conjecture.project_id,
        event_type="proof",
        conjecture_id=conjecture_id,
        agent_id=agent_id,
        details={"proof_lean_preview": lean_code[:200]},
    )

    # If conjecture was decomposed: invalidate all descendants
    if was_decomposed:
        await invalidate_descendants(conjecture_id, db)

    # Check parent assembly
    assembly_triggered = False
    parent_proved = False
    if conjecture.parent_id is not None:
        # Check if all non-invalid siblings are proved
        sibling_result = await db.execute(
            text("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 'proved') AS proved
                FROM conjectures
                WHERE parent_id = :parent_id AND status != 'invalid'
            """),
            {"parent_id": str(conjecture.parent_id)},
        )
        row = sibling_result.first()
        if row and row.total > 0 and row.total == row.proved:
            assembly_triggered = True
            parent_proved = await assembly_service.check_and_assemble(conjecture_id, db)

    # Fire project_completed if this is the root conjecture
    await _check_project_completed(conjecture, db)

    return ProofResult(
        status="proved",
        conjecture_id=conjecture_id,
        assembly_triggered=assembly_triggered,
        parent_proved=parent_proved,
    )


async def _check_project_completed(conjecture: Conjecture, db: AsyncSession) -> None:
    """Fire project_completed trigger if the proved conjecture is the project root."""
    import asyncio

    project = await db.get(Project, conjecture.project_id)
    if project and project.root_conjecture_id == conjecture.id:
        from app.mega.scheduler import fire_project_completed

        asyncio.create_task(fire_project_completed(project.id))


async def submit_disproof(
    conjecture_id: UUID,
    lean_code: str,
    agent_id: UUID,
    db: AsyncSession,
) -> DisproofResult:
    """Submit a disproof for a conjecture.

    Wraps tactics with the negated conjecture lean_statement using a locked
    signature, compiles via Lean CI, and on success updates the conjecture
    to disproved.
    """
    # Step 1: Validate conjecture exists
    conjecture = await db.get(Conjecture, conjecture_id)
    if conjecture is None:
        return DisproofResult(
            status="not_found",
            conjecture_id=conjecture_id,
            error="Conjecture not found",
        )

    # Step 2: Check status
    if conjecture.status in ("proved", "disproved", "invalid"):
        return DisproofResult(
            status="already_closed",
            conjecture_id=conjecture_id,
            message="This conjecture is already proved/disproved/invalid.",
        )

    # Step 3: SELECT FOR UPDATE
    lock_result = await db.execute(
        text("SELECT id, status FROM conjectures WHERE id = :id FOR UPDATE"),
        {"id": str(conjecture_id)},
    )
    locked_row = lock_result.first()
    if locked_row is None:
        return DisproofResult(
            status="not_found",
            conjecture_id=conjecture_id,
            error="Conjecture not found",
        )
    if locked_row.status not in ("open", "decomposed"):
        return DisproofResult(
            status="already_closed",
            conjecture_id=conjecture_id,
            message="This conjecture is already proved/disproved/invalid.",
        )

    was_decomposed = locked_row.status == "decomposed"

    # Step 4: Compile with negated locked signature
    lean_header = await _get_lean_header(db, conjecture.project_id)
    result = await lean_client.verify_disproof(
        lean_statement=conjecture.lean_statement,
        tactics=lean_code,
        conjecture_id=conjecture_id,
        lean_header=lean_header,
    )

    # Step 5a: Lean rejected or timed out
    if result.status == "rejected":
        return DisproofResult(
            status="rejected",
            conjecture_id=conjecture_id,
            error=result.error,
            message="Disproof rejected. See error for details.",
        )

    if result.status == "timeout":
        return DisproofResult(
            status="timeout",
            conjecture_id=conjecture_id,
            error=result.error or "Compilation timed out (60s limit).",
        )

    # Step 5b: Lean passed — update conjecture atomically
    rows_updated = (
        await db.execute(
            text("""
                UPDATE conjectures
                SET status = 'disproved',
                    proof_lean = :lean_code,
                    disproved_by = :agent_id,
                    closed_at = NOW()
                WHERE id = :conjecture_id AND status IN ('open', 'decomposed')
            """),
            {
                "lean_code": lean_code,
                "agent_id": str(agent_id),
                "conjecture_id": str(conjecture_id),
            },
        )
    ).rowcount

    if rows_updated == 0:
        return DisproofResult(
            status="already_closed",
            conjecture_id=conjecture_id,
            message="This conjecture was closed by another agent.",
        )

    # Increment agent counter atomically
    await db.execute(
        text("UPDATE agents SET conjectures_disproved = conjectures_disproved + 1 WHERE id = :id"),
        {"id": str(agent_id)},
    )

    # Log disproof event
    await activity_service.record_event(
        db,
        project_id=conjecture.project_id,
        event_type="disproof",
        conjecture_id=conjecture_id,
        agent_id=agent_id,
        details={"proof_lean_preview": lean_code[:200]},
    )

    # If conjecture was decomposed: invalidate all descendants
    descendants_invalidated = 0
    if was_decomposed:
        descendants_invalidated = await invalidate_descendants(conjecture_id, db)

    return DisproofResult(
        status="disproved",
        conjecture_id=conjecture_id,
        descendants_invalidated=descendants_invalidated,
    )


async def invalidate_descendants(conjecture_id: UUID, db: AsyncSession) -> int:
    """Recursively invalidate all descendants of a conjecture.

    Uses a recursive CTE to find all descendants and sets their status to
    'invalid' with closed_at = NOW(). Returns the count of invalidated rows.
    """
    result = await db.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM conjectures WHERE parent_id = :conjecture_id
                UNION ALL
                SELECT c.id FROM conjectures c
                JOIN descendants d ON c.parent_id = d.id
            )
            UPDATE conjectures
            SET status = 'invalid', closed_at = NOW()
            WHERE id IN (SELECT id FROM descendants)
            AND status != 'invalid'
        """),
        {"conjecture_id": str(conjecture_id)},
    )
    return result.rowcount
