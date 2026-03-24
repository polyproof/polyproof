"""Sorry extraction — runs a Lean metaprogram to find sorry'd declarations."""

import hashlib
import logging
from uuid import UUID

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sorry import Sorry
from app.models.tracked_file import TrackedFile

logger = logging.getLogger(__name__)

_EXTRACT_TEMPLATE = """import {module}

open Lean Elab Command Meta in
run_cmd do
  let env ← getEnv
  let modName := `{module}
  let some modIdx := env.getModuleIdx? modName | return
  for (name, ci) in env.constants.map₁.toArray do
    if env.getModuleIdxFor? name == some modIdx then
      let hasSorry := match ci with
        | .thmInfo val => val.value.hasSorry
        | .defnInfo val => val.value.hasSorry
        | _ => false
      if hasSorry then
        let typeStr ← liftTermElabM do
          let fmt ← ppExpr ci.type
          return toString fmt
        logInfo m!"SORRY|||{{name}}|||{{typeStr}}"
"""


async def extract_sorries_from_lean(file_path: str) -> list[dict]:
    """Run the Lean metaprogram to find sorry'd declarations in a module.

    Sends the metaprogram to the Kimina Lean server and parses the output.
    Returns a list of dicts with keys: declaration_name, goal_state.
    """
    module = file_path.replace("/", ".").removesuffix(".lean")
    code = _EXTRACT_TEMPLATE.format(module=module)

    try:
        headers: dict[str, str] = {}
        if settings.LEAN_SERVER_SECRET:
            headers["X-Lean-Secret"] = settings.LEAN_SERVER_SECRET

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{settings.LEAN_SERVER_URL}/verify",
                headers=headers,
                json={
                    "codes": [{"custom_id": "extract", "proof": code}],
                    "timeout": 120,
                },
            )
            if resp.status_code != 200:
                logger.warning("Extraction failed: HTTP %d", resp.status_code)
                return []

            data = resp.json()
            results = data.get("results", [])
            if not results:
                return []

            result = results[0]
            resp_data = result.get("response", {})
            messages = resp_data.get("messages", []) if resp_data else []

    except Exception:
        logger.exception("Extraction failed for %s", file_path)
        return []

    sorries = []
    for msg in messages:
        if msg.get("severity") != "info":
            continue
        msg_data = msg.get("data", "")
        if not msg_data.startswith("SORRY|||"):
            continue

        parts = msg_data.split("|||", 2)
        if len(parts) != 3:
            continue

        _, name, goal_state = parts
        sorries.append({
            "declaration_name": name.strip(),
            "goal_state": goal_state.strip(),
        })

    return sorries


async def sync_sorries_for_file(
    db: AsyncSession,
    project_id: UUID,
    tracked_file: TrackedFile,
    parent_sorry_id: UUID | None = None,
) -> dict:
    """Re-extract sorry's for a file and sync with the database.

    Creates new sorry records for declarations not already tracked.
    If parent_sorry_id is provided, new sorry's are created as children.
    Returns counts: {created, skipped, total_extracted}.
    """
    extracted = await extract_sorries_from_lean(tracked_file.file_path)
    if not extracted:
        return {"created": 0, "skipped": 0, "total_extracted": 0}

    created = 0
    skipped = 0

    for item in extracted:
        goal = item["goal_state"]
        decl = item["declaration_name"]
        goal_hash = hashlib.sha256(goal.encode()).hexdigest()[:16]

        # Check if this sorry already exists (by declaration name + goal hash)
        exists = await db.scalar(
            select(func.count())
            .select_from(Sorry)
            .where(
                Sorry.file_id == tracked_file.id,
                Sorry.declaration_name == decl,
                Sorry.goal_hash == goal_hash,
                Sorry.status.notin_(["invalid"]),
            )
        )
        if exists:
            skipped += 1
            continue

        sorry = Sorry(
            file_id=tracked_file.id,
            project_id=project_id,
            declaration_name=decl,
            sorry_index=0,
            goal_state=goal,
            goal_hash=goal_hash,
            parent_sorry_id=parent_sorry_id,
            priority="normal",
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
                Sorry.status.notin_(["invalid"]),
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
