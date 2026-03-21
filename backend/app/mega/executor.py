"""Tool call dispatcher for the mega agent.

Routes tool calls to the appropriate service functions and returns
JSON-serializable results.
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import lean_client

logger = logging.getLogger(__name__)

_FETCH_URL_MAX_CHARS = 10_000
_FETCH_URL_TIMEOUT = 15.0


async def execute_tool(
    tool_name: str,
    arguments: dict,
    *,
    db: AsyncSession,
    mega_agent_id: UUID,
    project_id: UUID,
) -> dict:
    """Dispatch a tool call to the appropriate service function.

    Returns a JSON-serializable dict that will be sent back to the LLM
    as a function_call_output.
    """
    try:
        if tool_name == "verify_lean":
            return await _verify_lean(arguments, db=db)
        elif tool_name == "update_decomposition":
            return await _update_decomposition(arguments, db=db, mega_agent_id=mega_agent_id)
        elif tool_name == "revert_decomposition":
            return await _revert_decomposition(arguments, db=db, mega_agent_id=mega_agent_id)
        elif tool_name == "set_priority":
            return await _set_priority(
                arguments, db=db, mega_agent_id=mega_agent_id, project_id=project_id
            )
        elif tool_name == "post_comment":
            return await _post_comment(
                arguments, db=db, mega_agent_id=mega_agent_id, project_id=project_id
            )
        elif tool_name == "submit_proof":
            return await _submit_proof(arguments, db=db, mega_agent_id=mega_agent_id)
        elif tool_name == "submit_disproof":
            return await _submit_disproof(arguments, db=db, mega_agent_id=mega_agent_id)
        elif tool_name == "fetch_url":
            return await _fetch_url(arguments)
        else:
            return {"status": "error", "error": f"Unknown tool: {tool_name}"}
    except Exception:
        logger.exception("Tool execution failed: %s", tool_name)
        return {
            "status": "error",
            "error": f"Internal error executing {tool_name}. The platform logged the error.",
        }


async def _verify_lean(args: dict, *, db: AsyncSession) -> dict:
    """Verify Lean code privately. Nothing stored."""
    lean_code = args["lean_code"]
    conjecture_id = args.get("conjecture_id")

    if conjecture_id:
        # Import here to avoid circular imports
        from app.models.conjecture import Conjecture

        conjecture = await db.get(Conjecture, UUID(conjecture_id))
        if not conjecture:
            return {"status": "error", "error": f"Conjecture {conjecture_id} not found."}
        result = await lean_client.verify_proof(
            lean_statement=conjecture.lean_statement,
            tactics=lean_code,
            conjecture_id=UUID(conjecture_id),
        )
    else:
        result = await lean_client.verify_freeform(lean_code)

    return {"status": result.status, "error": result.error}


async def _update_decomposition(args: dict, *, db: AsyncSession, mega_agent_id: UUID) -> dict:
    """Create or modify a decomposition via decomposition_service."""
    from app.services import decomposition_service

    return await decomposition_service.update(
        parent_id=UUID(args["parent_id"]),
        children=args["children"],
        sorry_proof=args["sorry_proof"],
        mega_agent_id=mega_agent_id,
        db=db,
    )


async def _revert_decomposition(args: dict, *, db: AsyncSession, mega_agent_id: UUID) -> dict:
    """Revert a decomposition via decomposition_service."""
    from app.services import decomposition_service

    return await decomposition_service.revert(
        conjecture_id=UUID(args["conjecture_id"]),
        reason=args["reason"],
        mega_agent_id=mega_agent_id,
        db=db,
    )


async def _set_priority(
    args: dict,
    *,
    db: AsyncSession,
    mega_agent_id: UUID,
    project_id: UUID,
) -> dict:
    """Set conjecture priority via conjecture_service."""
    from app.services import conjecture_service

    return await conjecture_service.set_priority(
        conjecture_id=UUID(args["conjecture_id"]),
        priority=args["priority"],
        mega_agent_id=mega_agent_id,
        project_id=project_id,
        db=db,
    )


async def _post_comment(
    args: dict,
    *,
    db: AsyncSession,
    mega_agent_id: UUID,
    project_id: UUID,
) -> dict:
    """Post a comment via comment_service."""
    from app.services import comment_service

    conjecture_id = args.get("conjecture_id") or None
    comment_project_id = args.get("project_id") or None
    body = args["body"]
    is_summary = args.get("is_summary", False)
    parent_comment_id = args.get("parent_comment_id") or None

    # Fallback: if neither target is specified, use the project_id from context
    if not conjecture_id and not comment_project_id:
        comment_project_id = str(project_id)

    from app.models.agent import Agent

    mega_agent = await db.get(Agent, mega_agent_id)

    if conjecture_id:
        comment = await comment_service.create_conjecture_comment(
            db=db,
            conjecture_id=UUID(conjecture_id),
            body=body,
            author=mega_agent,
            is_summary=is_summary,
            parent_comment_id=UUID(parent_comment_id) if parent_comment_id else None,
        )
    else:
        comment = await comment_service.create_project_comment(
            db=db,
            project_id=UUID(comment_project_id),
            body=body,
            author=mega_agent,
            is_summary=is_summary,
            parent_comment_id=UUID(parent_comment_id) if parent_comment_id else None,
        )

    return {
        "status": "ok",
        "comment_id": str(comment.id),
        "is_summary": is_summary,
    }


async def _submit_proof(args: dict, *, db: AsyncSession, mega_agent_id: UUID) -> dict:
    """Submit a proof via proof_service."""
    from app.services import proof_service

    return await proof_service.submit_proof(
        conjecture_id=UUID(args["conjecture_id"]),
        lean_code=args["lean_code"],
        agent_id=mega_agent_id,
        db=db,
    )


async def _submit_disproof(args: dict, *, db: AsyncSession, mega_agent_id: UUID) -> dict:
    """Submit a disproof via proof_service."""
    from app.services import proof_service

    return await proof_service.submit_disproof(
        conjecture_id=UUID(args["conjecture_id"]),
        lean_code=args["lean_code"],
        agent_id=mega_agent_id,
        db=db,
    )


async def _fetch_url(args: dict) -> dict:
    """Fetch a URL and return its text content, truncated to 10k chars."""
    url = args["url"]
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_URL_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "PolyProof-MegaAgent/1.0"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text[:_FETCH_URL_MAX_CHARS]
            return {"status": "ok", "content": content}
    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"Failed to fetch URL: {e.response.status_code}"}
    except httpx.HTTPError as e:
        return {"status": "error", "error": f"Failed to fetch URL: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"Failed to fetch URL: {e}"}
