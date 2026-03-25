"""Async job queue for processing sorry fills."""

import asyncio
import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.job import Job
from app.models.project import Project
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile
from app.services import activity_service, github_service, lean_client

logger = logging.getLogger(__name__)


async def get_by_id(db: AsyncSession, job_id: UUID) -> Job | None:
    """Get a job by ID."""
    return await db.get(Job, job_id)


async def get_next_pending(db: AsyncSession, project_id: UUID) -> Job | None:
    """Get the next queued job for a project (FIFO).

    Uses SELECT FOR UPDATE SKIP LOCKED to avoid contention.
    """
    result = await db.execute(
        select(Job)
        .where(
            Job.project_id == project_id,
            Job.status == "queued",
        )
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def process_fill_job(db: AsyncSession, job: Job) -> dict:
    """Process a fill job.

    Steps:
    1. Check sorry still open (fast-path supersession)
    2. Mark job as compiling
    3. Read file from workspace and replace sorry with tactics
    4. Compile full file via Lean server
    5. If fails -> mark job failed with lean output
    6. If succeeds, no new sorry's -> mark sorry filled, job merged
    7. If succeeds, new sorry's -> mark sorry decomposed, create children, job merged
    8. Early supersession: cancel all other queued fills for that sorry

    For MVP, the git commit step is simulated (logged but not executed).
    """
    sorry_id = job.sorry_id
    if sorry_id is None:
        return await _fail_job(db, job, "Job has no sorry_id")

    # Step 1: Check sorry still open
    lock_result = await db.execute(
        text("SELECT id, status, file_id, project_id FROM sorries WHERE id = :id FOR UPDATE"),
        {"id": str(sorry_id)},
    )
    locked_row = lock_result.first()

    if locked_row is None:
        return await _fail_job(db, job, "Sorry not found")

    if locked_row.status not in ("open", "decomposed"):
        return await _supersede_job(db, job, f"Sorry already {locked_row.status}")

    was_decomposed = locked_row.status == "decomposed"

    # Step 2: Mark job as compiling
    await db.execute(update(Job).where(Job.id == job.id).values(status="compiling"))
    await db.flush()

    # Step 3: Read sorry + tracked file for compilation context
    sorry = await db.get(Sorry, sorry_id)
    if sorry is None:
        return await _fail_job(db, job, "Sorry not found after lock")

    tracked_file = await db.get(TrackedFile, sorry.file_id)
    if not tracked_file:
        return await _fail_job(db, job, "Tracked file not found for sorry")

    # Step 4: Fetch source file and compile by patching the sorry
    project = await db.get(Project, job.project_id)
    if not project:
        return await _fail_job(db, job, "Project not found")

    try:
        repo = github_service.parse_repo(project.fork_repo)
        file_content, file_sha = await github_service.get_file_content(
            repo, tracked_file.file_path, project.fork_branch
        )
    except github_service.GitHubError as e:
        return await _fail_job(db, job, f"Could not fetch source file: {e}")

    # Detect decomposition: if tactics contain sorry, this is a partial fill
    is_decomposition = _tactics_contain_sorry(job.tactics)

    # Declarations can contain multiple sorry's. #print axioms checks the
    # WHOLE declaration, so it reports sorryAx from OTHER sorry's that we're
    # not filling. Skip the axiom check when siblings exist — the
    # tactic-level sorry check above is sufficient.
    is_child_sorry = sorry.parent_sorry_id is not None
    has_sibling_sorries = (
        github_service.count_sorries_in_declaration(file_content, sorry.declaration_name) > 1
    )

    result = await lean_client.verify_in_file(
        file_content=file_content,
        declaration_name=sorry.declaration_name,
        tactics=job.tactics,
        allow_sorry=is_decomposition or is_child_sorry or has_sibling_sorries,
        sorry_index=sorry.sorry_index,
    )

    # Step 5: Handle compilation result
    if result.status == "rejected":
        return await _fail_job(db, job, result.error or "Compilation failed", result.messages)

    if result.status == "timeout":
        return await _fail_job(db, job, result.error or "Compilation timed out")

    # Step 6/7: Compilation passed
    if is_decomposition:
        # Decomposition: mark sorry as decomposed, create child sorry records
        await db.execute(
            text("""
                UPDATE sorries
                SET status = 'decomposed',
                    fill_tactics = :tactics,
                    fill_description = :description,
                    filled_by = :agent_id,
                    filled_at = NOW()
                WHERE id = :sorry_id AND status IN ('open', 'decomposed')
            """),
            {
                "tactics": job.tactics,
                "description": job.description,
                "agent_id": str(job.agent_id) if job.agent_id else None,
                "sorry_id": str(sorry_id),
            },
        )

        # Increment agent decomposition counter
        if job.agent_id:
            await db.execute(
                text(
                    "UPDATE agents SET sorries_decomposed = sorries_decomposed + 1 WHERE id = :id"
                ),
                {"id": str(job.agent_id)},
            )

        # Log decomposition event
        await activity_service.record_event(
            db,
            project_id=job.project_id,
            event_type="decomposition",
            sorry_id=sorry_id,
            agent_id=job.agent_id,
            details={"job_id": str(job.id)},
        )

        # Invalidate any existing children (handles re-decomposition)
        await _invalidate_descendants(sorry_id, db)

        # Create child sorry records from the compilation output.
        # The REPL's `sorries` field gives us goal states for each sorry
        # in the compiled file — no workspace rebuild needed.
        if result.sorries:
            try:
                patched = github_service.replace_sorry_in_declaration(
                    file_content,
                    sorry.declaration_name,
                    job.tactics,
                    sorry_index=sorry.sorry_index,
                )
                await _create_child_sorries(
                    db=db,
                    parent_sorry=sorry,
                    tracked_file=tracked_file,
                    original_content=file_content,
                    patched_content=patched,
                    lean_sorries=result.sorries,
                )
                logger.info(
                    "Created child sorry records for %s",
                    sorry.declaration_name,
                )
            except Exception:
                logger.exception(
                    "Child sorry creation failed for %s (decomposition still recorded)",
                    sorry_id,
                )
    else:
        # Full fill: mark sorry as filled
        rows_updated = (
            await db.execute(
                text("""
                    UPDATE sorries
                    SET status = 'filled',
                        fill_tactics = :tactics,
                        fill_description = :description,
                        filled_by = :agent_id,
                        filled_at = NOW()
                    WHERE id = :sorry_id AND status IN ('open', 'decomposed')
                """),
                {
                    "tactics": job.tactics,
                    "description": job.description,
                    "agent_id": str(job.agent_id) if job.agent_id else None,
                    "sorry_id": str(sorry_id),
                },
            )
        ).rowcount

        if rows_updated == 0:
            return await _supersede_job(db, job, "Sorry was filled by another agent")

        # Increment agent fill counter
        if job.agent_id:
            await db.execute(
                text("UPDATE agents SET sorries_filled = sorries_filled + 1 WHERE id = :id"),
                {"id": str(job.agent_id)},
            )

        # If sorry was decomposed, invalidate descendants
        if was_decomposed:
            await _invalidate_descendants(sorry_id, db)

        # Log fill event
        await activity_service.record_event(
            db,
            project_id=job.project_id,
            event_type="fill",
            sorry_id=sorry_id,
            agent_id=job.agent_id,
            details={"job_id": str(job.id), "status": "merged"},
        )

    # Commit the fill to the GitHub fork (best-effort — fill is recorded regardless)
    # Sequential job processing per project guarantees no SHA conflicts.
    if settings.GITHUB_PAT and tracked_file and project:
        try:
            repo = github_service.parse_repo(project.fork_repo)
            file_content, file_sha = await github_service.get_file_content(
                repo, tracked_file.file_path, project.fork_branch
            )
            new_content = github_service.replace_sorry_in_declaration(
                file_content,
                sorry.declaration_name,
                job.tactics,
                sorry_index=sorry.sorry_index,
            )
            agent_handle = None
            if job.agent_id:
                agent_row = await db.execute(
                    text("SELECT handle FROM agents WHERE id = :id"),
                    {"id": str(job.agent_id)},
                )
                row = agent_row.first()
                agent_handle = row.handle if row else None

            commit_msg = (
                f"fill: {sorry.declaration_name}\n\n"
                f"{job.description or 'sorry filled'}\n\n"
                f"Agent: @{agent_handle or 'unknown'}"
            )
            new_sha = await github_service.commit_file(
                repo,
                tracked_file.file_path,
                new_content,
                commit_msg,
                project.fork_branch,
                file_sha,
                author_name=agent_handle or "PolyProof",
                author_email="noreply@polyproof.org",
            )
            await db.execute(
                text("UPDATE projects SET current_commit = :sha WHERE id = :id"),
                {"sha": new_sha, "id": str(project.id)},
            )
            logger.info("Committed fill for %s -> %s", sorry.declaration_name, new_sha[:8])
        except Exception:
            logger.exception("GitHub commit failed for sorry %s (fill still recorded)", sorry_id)
    else:
        logger.info("GITHUB_PAT not set — skipping commit for sorry %s", sorry_id)

    # Mark job as merged
    await db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status="merged",
            result={"sorry_status": "decomposed" if is_decomposition else "filled"},
            completed_at=datetime.now(UTC),
        )
    )

    # Supersede all other queued fills for this sorry
    await _supersede_queued_for_sorry(db, sorry_id, exclude_job_id=job.id)

    await db.flush()

    return {
        "status": "merged",
        "job_id": str(job.id),
        "sorry_status": "decomposed" if is_decomposition else "filled",
    }


async def start_worker(project_id: UUID) -> None:
    """Background worker that processes jobs sequentially for a project.

    Runs in an asyncio task. Processes one job at a time, then checks for more.
    """
    from app.db.connection import async_session_factory

    logger.info("Job worker started for project %s", project_id)

    while True:
        try:
            async with async_session_factory() as db:
                job = await get_next_pending(db, project_id)
                if job is None:
                    # No more jobs, worker exits
                    logger.info("Job worker idle for project %s, exiting", project_id)
                    return

                try:
                    result = await process_fill_job(db, job)
                    await db.commit()
                    logger.info("Job %s completed: %s", job.id, result.get("status"))
                except Exception:
                    await db.rollback()
                    logger.exception("Job %s failed with exception", job.id)
                    # Mark the job as failed
                    async with async_session_factory() as err_db:
                        await err_db.execute(
                            update(Job)
                            .where(Job.id == job.id)
                            .values(
                                status="failed",
                                lean_output="Internal error during processing",
                                completed_at=datetime.now(UTC),
                            )
                        )
                        await err_db.commit()

        except Exception:
            logger.exception("Job worker error for project %s", project_id)
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tactics_contain_sorry(tactics: str) -> bool:
    """Check if tactics contain sorry outside of comments (indicating decomposition).

    Strips Lean line comments (-- ...) and block comments (/- ... -/)
    before checking, so ``-- sorry`` in a comment doesn't trigger.
    """
    # Strip block comments (non-greedy, handles nesting poorly but good enough)
    stripped = re.sub(r"/-.*?-/", "", tactics, flags=re.DOTALL)
    # Strip line comments
    stripped = re.sub(r"--.*$", "", stripped, flags=re.MULTILINE)
    return bool(re.search(r"\bsorry\b", stripped))


async def _fail_job(
    db: AsyncSession,
    job: Job,
    error: str,
    messages: list[dict] | None = None,
) -> dict:
    """Mark a job as failed."""
    await db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status="failed",
            lean_output=error,
            completed_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return {"status": "failed", "job_id": str(job.id), "error": error}


async def _supersede_job(db: AsyncSession, job: Job, reason: str) -> dict:
    """Mark a job as superseded."""
    await db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(
            status="superseded",
            lean_output=reason,
            completed_at=datetime.now(UTC),
        )
    )
    await db.flush()
    return {"status": "superseded", "job_id": str(job.id), "reason": reason}


async def _supersede_queued_for_sorry(
    db: AsyncSession, sorry_id: UUID, exclude_job_id: UUID
) -> int:
    """Cancel all other queued fills for a sorry after one merges."""
    result = await db.execute(
        update(Job)
        .where(
            Job.sorry_id == sorry_id,
            Job.status == "queued",
            Job.id != exclude_job_id,
        )
        .values(
            status="superseded",
            lean_output="Another fill for this sorry was merged",
            completed_at=datetime.now(UTC),
        )
    )
    return result.rowcount


async def _create_child_sorries(
    db: AsyncSession,
    parent_sorry: Sorry,
    tracked_file: TrackedFile,
    original_content: str,
    patched_content: str,
    lean_sorries: list,
) -> None:
    """Create child sorry records from the REPL's sorries field.

    Compares sorry positions in the patched file against the original
    to find only NEW sorry's introduced by the decomposition. Filters
    to sorry's within the parent declaration's boundaries.
    """
    import hashlib

    short_name = parent_sorry.declaration_name.rsplit(".", 1)[-1]

    # Map sorry positions in the patched file to declaration names
    decl_names = github_service.map_positions_to_declarations(
        patched_content,
        [(s.line, s.col) for s in lean_sorries],
    )

    # Find sorry positions in the ORIGINAL file to exclude pre-existing ones
    original_sorry_positions: set[tuple[int, int]] = set()
    for line_idx, line_text in enumerate(original_content.splitlines(), 1):
        col = line_text.find("sorry")
        while col >= 0:
            original_sorry_positions.add((line_idx, col))
            col = line_text.find("sorry", col + 1)

    child_index = 0
    for sorry_info, enclosing_name in zip(lean_sorries, decl_names):
        # Only create children within the parent declaration
        if enclosing_name is None:
            continue
        if enclosing_name != short_name and not enclosing_name.endswith("." + short_name):
            continue

        # Skip sorry's that existed in the original file (same position)
        if (sorry_info.line, sorry_info.col) in original_sorry_positions:
            continue

        goal = sorry_info.goal
        if not goal:
            continue

        goal_hash = hashlib.sha256(goal.encode()).hexdigest()[:16]

        child = Sorry(
            file_id=tracked_file.id,
            project_id=parent_sorry.project_id,
            declaration_name=parent_sorry.declaration_name,
            sorry_index=child_index,
            goal_state=goal,
            goal_hash=goal_hash,
            parent_sorry_id=parent_sorry.id,
            line=sorry_info.line,
            col=sorry_info.col,
            priority="normal",
        )
        db.add(child)
        child_index += 1

    await db.flush()


async def _invalidate_descendants(sorry_id: UUID, db: AsyncSession) -> int:
    """Recursively invalidate all descendants of a sorry.

    Uses a recursive CTE to find all descendants and sets their status to
    'invalid'. Returns the count of invalidated rows.
    """
    result = await db.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM sorries WHERE parent_sorry_id = :sorry_id
                UNION ALL
                SELECT s.id FROM sorries s
                JOIN descendants d ON s.parent_sorry_id = d.id
            )
            UPDATE sorries
            SET status = 'invalid'
            WHERE id IN (SELECT id FROM descendants)
            AND status != 'invalid'
        """),
        {"sorry_id": str(sorry_id)},
    )
    return result.rowcount
