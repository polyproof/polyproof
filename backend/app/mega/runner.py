"""Mega agent runner -- the agentic loop using OpenAI Responses API.

Builds context, calls the model, executes tools, feeds results back,
and repeats until the model stops calling tools or the safety cap is hit.
"""

import json
import logging
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.mega.context import build_context_packet
from app.mega.executor import execute_tool
from app.mega.prompt import MEGA_AGENT_SYSTEM_PROMPT
from app.mega.tools import MEGA_AGENT_TOOLS

logger = logging.getLogger(__name__)

_MODEL = "gpt-5.4"
_MAX_TOOL_CALLS = 50


async def run_mega_agent(
    project_id: UUID,
    trigger: dict,
    mega_agent_id: UUID,
    db: AsyncSession,
) -> dict:
    """Run one mega agent invocation for a project.

    Returns a summary dict with token usage and tool call count.
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Build context packet
    context = await build_context_packet(project_id, trigger, db)
    logger.info(
        "Mega agent invocation: project=%s trigger=%s context_length=%d",
        project_id,
        trigger.get("trigger"),
        len(context),
    )

    tools = MEGA_AGENT_TOOLS

    # Initial call
    total_tool_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0

    try:
        response = await client.responses.create(
            model=_MODEL,
            instructions=MEGA_AGENT_SYSTEM_PROMPT,
            input=context,
            tools=tools,
        )
    except Exception:
        logger.exception("OpenAI API call failed for project %s", project_id)
        return {
            "status": "error",
            "error": "OpenAI API call failed",
            "tool_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    # Track token usage from initial call
    if hasattr(response, "usage") and response.usage:
        total_input_tokens += getattr(response.usage, "input_tokens", 0)
        total_output_tokens += getattr(response.usage, "output_tokens", 0)

    # Agent loop: execute tools and feed results back
    while response.output and total_tool_calls < _MAX_TOOL_CALLS:
        # Log any text the model produced
        for item in response.output:
            if hasattr(item, "text") and item.text:
                logger.info("Mega agent says:\n%s", item.text[:1000])

        tool_calls = [o for o in response.output if o.type == "function_call"]
        if not tool_calls:
            break

        tool_results = []
        for call in tool_calls:
            total_tool_calls += 1
            if total_tool_calls > _MAX_TOOL_CALLS:
                tool_results.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            {
                                "status": "error",
                                "error": f"Tool call limit reached ({_MAX_TOOL_CALLS}).",
                            }
                        ),
                    }
                )
                break

            try:
                args = json.loads(call.arguments)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON in tool arguments: %s", call.arguments[:200])
                tool_results.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(
                            {
                                "status": "error",
                                "error": "Invalid JSON in tool arguments.",
                            }
                        ),
                    }
                )
                continue

            args_preview = json.dumps(args, default=str)
            if len(args_preview) > 500:
                args_preview = args_preview[:500] + "..."
            logger.info(
                "Tool call %d/%d: %s(%s)",
                total_tool_calls,
                _MAX_TOOL_CALLS,
                call.name,
                args_preview,
            )

            result = await execute_tool(
                call.name,
                args,
                db=db,
                mega_agent_id=mega_agent_id,
                project_id=project_id,
            )

            result_str = json.dumps(result, default=str)
            result_preview = result_str[:300] + "..." if len(result_str) > 300 else result_str
            logger.info("Tool result: %s", result_preview)

            tool_results.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result_str,
                }
            )

        if total_tool_calls >= _MAX_TOOL_CALLS:
            logger.warning(
                "Mega agent hit tool call cap (%d) for project %s",
                _MAX_TOOL_CALLS,
                project_id,
            )
            break

        # Feed results back to the model
        try:
            response = await client.responses.create(
                model=_MODEL,
                instructions=MEGA_AGENT_SYSTEM_PROMPT,
                input=tool_results,
                tools=tools,
                previous_response_id=response.id,
            )
        except Exception:
            logger.exception(
                "OpenAI API call failed during tool loop for project %s",
                project_id,
            )
            break

        if hasattr(response, "usage") and response.usage:
            total_input_tokens += getattr(response.usage, "input_tokens", 0)
            total_output_tokens += getattr(response.usage, "output_tokens", 0)

    logger.info(
        "Mega agent invocation complete: project=%s tool_calls=%d input_tokens=%d output_tokens=%d",
        project_id,
        total_tool_calls,
        total_input_tokens,
        total_output_tokens,
    )

    return {
        "status": "ok",
        "tool_calls": total_tool_calls,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    }
