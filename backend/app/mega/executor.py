"""Tool call dispatcher for the mega agent.

Routes tool calls to the appropriate service functions and returns
JSON-serializable results.
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

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
        elif tool_name == "verify_freeform":
            return await _verify_freeform(arguments, db=db)
        elif tool_name == "fill_sorry":
            return await _fill_sorry(arguments, db=db, mega_agent_id=mega_agent_id)
        elif tool_name == "set_priority":
            return await _set_priority(
                arguments, db=db, mega_agent_id=mega_agent_id, project_id=project_id
            )
        elif tool_name == "post_comment":
            return await _post_comment(
                arguments, db=db, mega_agent_id=mega_agent_id, project_id=project_id
            )
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
    """Verify tactics by patching the actual source file. Sorry IS allowed."""
    from app.models.project import Project
    from app.models.sorry import Sorry
    from app.models.tracked_file import TrackedFile
    from app.services import github_service
    from app.services.lean_client import verify_in_file

    sorry_id = UUID(args["sorry_id"])
    tactics = args["tactics"]

    sorry = await db.get(Sorry, sorry_id)
    if not sorry:
        return {"status": "error", "error": f"Sorry {sorry_id} not found."}

    tracked_file = await db.get(TrackedFile, sorry.file_id)
    if not tracked_file:
        return {"status": "error", "error": "Tracked file not found."}

    project = await db.get(Project, sorry.project_id)
    if not project:
        return {"status": "error", "error": "Project not found."}

    try:
        repo = github_service.parse_repo(project.fork_repo)
        file_content, _sha = await github_service.get_file_content(
            repo, tracked_file.file_path, project.fork_branch
        )
    except github_service.GitHubError as e:
        return {"status": "error", "error": f"Could not fetch source file: {e}"}

    result = await verify_in_file(
        file_content=file_content,
        declaration_name=sorry.declaration_name,
        tactics=tactics,
        allow_sorry=True,
        sorry_index=sorry.sorry_index,
    )
    return {
        "status": result.status,
        "error": result.error,
        "messages": result.messages,
    }


async def _verify_freeform(args: dict, *, db: AsyncSession) -> dict:
    """Verify freeform Lean code in a project context."""
    from sqlalchemy import select

    from app.models.tracked_file import TrackedFile
    from app.services.lean_client import verify_freeform

    project_id = args.get("project_id")
    code = args["code"]

    # Find default import path from the project's first tracked file
    import_path = None
    if project_id:
        try:
            first_file = (
                await db.scalars(
                    select(TrackedFile)
                    .where(TrackedFile.project_id == UUID(project_id))
                    .order_by(TrackedFile.file_path.asc())
                    .limit(1)
                )
            ).first()
            if first_file:
                import_path = first_file.file_path
        except Exception:
            pass

    result = await verify_freeform(code, import_path=import_path)
    return {
        "status": result.status,
        "error": result.error,
        "messages": result.messages,
    }


async def _fill_sorry(args: dict, *, db: AsyncSession, mega_agent_id: UUID) -> dict:
    """Submit a fill for a sorry via the async job queue."""
    from app.services import fill_service

    result = await fill_service.submit_fill(
        db=db,
        sorry_id=UUID(args["sorry_id"]),
        tactics=args["tactics"],
        description=args["description"],
        agent_id=mega_agent_id,
    )

    # Convert UUID values to strings for JSON serialization
    if "job_id" in result:
        result["job_id"] = str(result["job_id"])
    return result


async def _set_priority(
    args: dict,
    *,
    db: AsyncSession,
    mega_agent_id: UUID,
    project_id: UUID,
) -> dict:
    """Set sorry priority via sorry_service."""
    from app.services import sorry_service

    return await sorry_service.set_priority(
        sorry_id=UUID(args["sorry_id"]),
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
    from app.models.agent import Agent
    from app.services import comment_service

    target_id = args["target_id"]
    body = args["body"]
    is_summary = args.get("is_summary", False)
    is_project_comment = args.get("is_project_comment", False)

    # Parse target UUID
    try:
        target_uuid = UUID(target_id)
    except ValueError:
        return {"status": "error", "error": f"Invalid UUID: {target_id}"}

    mega_agent = await db.get(Agent, mega_agent_id)
    if not mega_agent:
        return {"status": "error", "error": "Mega agent not found"}

    if is_project_comment:
        comment = await comment_service.create_project_comment(
            db=db,
            project_id=target_uuid,
            body=body,
            author=mega_agent,
            is_summary=is_summary,
        )
    else:
        # Default: treat target_id as a sorry_id
        comment = await comment_service.create_sorry_comment(
            db=db,
            sorry_id=target_uuid,
            body=body,
            author=mega_agent,
            is_summary=is_summary,
        )

    return {
        "status": "ok",
        "comment_id": str(comment.id),
        "is_summary": is_summary,
    }


def _is_safe_url(url: str) -> bool:
    """Block internal/private URLs to prevent SSRF."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
    except Exception:
        return False
    hostname = (parsed.hostname or "").lower()
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return False
    blocked = ("localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "[::1]")
    private_prefixes = ("10.", "172.", "192.168.")
    if hostname in blocked or any(hostname.startswith(p) for p in private_prefixes):
        return False
    return True


async def _fetch_url(args: dict) -> dict:
    """Fetch a URL and return its text content, truncated to 10k chars."""
    url = args["url"]
    if not _is_safe_url(url):
        return {"status": "error", "error": "URL blocked: internal/private addresses not allowed."}
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
