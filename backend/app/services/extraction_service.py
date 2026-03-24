"""Sorry extraction — compiles files and reads the REPL's `sorries` field."""

import hashlib
import logging
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile
from app.services import github_service
from app.services.lean_client import _FILE_LEAN_TIMEOUT, _send_to_lean

logger = logging.getLogger(__name__)


async def extract_sorries_from_file(file_content: str) -> list[dict]:
    """Compile a file and extract sorry positions + goal states from the REPL.

    Sends the full file to Kimina for compilation. The REPL returns a
    ``sorries`` field with goal states for each sorry. We map each sorry
    position to its enclosing declaration name.

    Returns a list of dicts: {declaration_name, goal_state, sorry_index, line, col}.
    """
    result = await _send_to_lean(
        file_content, allow_sorry=True, timeout=_FILE_LEAN_TIMEOUT
    )

    if result.status != "passed":
        logger.warning("Extraction compilation failed: %s", result.error)
        return []

    if not result.sorries:
        return []

    # Map positions to declaration names
    positions = [(s.line, s.col) for s in result.sorries]
    decl_names = github_service.map_positions_to_declarations(file_content, positions)

    # Group by declaration to assign sorry_index
    decl_counts: dict[str, int] = {}
    sorries = []
    for sorry_info, decl_name in zip(result.sorries, decl_names):
        if decl_name is None:
            continue

        idx = decl_counts.get(decl_name, 0)
        decl_counts[decl_name] = idx + 1

        sorries.append({
            "declaration_name": decl_name,
            "goal_state": sorry_info.goal,
            "sorry_index": idx,
            "line": sorry_info.line,
            "col": sorry_info.col,
        })

    return sorries


async def sync_sorries_for_file(
    db: AsyncSession,
    project_id: UUID,
    tracked_file: TrackedFile,
    file_content: str | None = None,
    parent_sorry_id: UUID | None = None,
) -> dict:
    """Extract sorry's for a file and sync with the database.

    If file_content is provided, compiles it directly. Otherwise fetches
    from the project's GitHub fork.

    Creates new sorry records for declarations not already tracked.
    Returns counts: {created, skipped, total_extracted}.
    """
    if file_content is None:
        # Fetch from GitHub
        from app.models.project import Project

        project = await db.get(Project, project_id)
        if not project:
            return {"created": 0, "skipped": 0, "total_extracted": 0}

        try:
            repo = github_service.parse_repo(project.fork_repo)
            file_content, _sha = await github_service.get_file_content(
                repo, tracked_file.file_path, project.fork_branch
            )
        except github_service.GitHubError:
            logger.warning("Could not fetch %s from GitHub", tracked_file.file_path)
            return {"created": 0, "skipped": 0, "total_extracted": 0}

    extracted = await extract_sorries_from_file(file_content)
    if not extracted:
        return {"created": 0, "skipped": 0, "total_extracted": 0}

    created = 0
    skipped = 0

    for item in extracted:
        goal = item["goal_state"]
        decl = item["declaration_name"]
        sorry_index = item["sorry_index"]
        goal_hash = hashlib.sha256(goal.encode()).hexdigest()[:16]

        # Check if this sorry already exists
        exists = await db.scalar(
            select(func.count())
            .select_from(Sorry)
            .where(
                Sorry.file_id == tracked_file.id,
                Sorry.declaration_name == decl,
                Sorry.sorry_index == sorry_index,
                Sorry.goal_hash == goal_hash,
                Sorry.status != "invalid",
            )
        )
        if exists:
            skipped += 1
            continue

        sorry = Sorry(
            file_id=tracked_file.id,
            project_id=project_id,
            declaration_name=decl,
            sorry_index=sorry_index,
            goal_state=goal,
            goal_hash=goal_hash,
            parent_sorry_id=parent_sorry_id,
            priority="normal",
            line=item.get("line"),
            col=item.get("col"),
        )
        db.add(sorry)
        created += 1

    if created > 0:
        await db.flush()

        # Update sorry count on tracked file
        count = await db.scalar(
            select(func.count())
            .select_from(Sorry)
            .where(
                Sorry.file_id == tracked_file.id,
                Sorry.status != "invalid",
            )
        )
        await db.execute(
            text("UPDATE tracked_files SET sorry_count = :count WHERE id = :id"),
            {"count": count or 0, "id": str(tracked_file.id)},
        )
        await db.flush()

    logger.info(
        "Extraction for %s: %d extracted, %d created, %d skipped",
        tracked_file.file_path,
        len(extracted),
        created,
        skipped,
    )

    return {
        "created": created,
        "skipped": skipped,
        "total_extracted": len(extracted),
    }
