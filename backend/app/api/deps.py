import hashlib
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_async_session
from app.models.agent import Agent

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async for session in get_async_session():
        yield session


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    token = credentials.credentials
    if not token.startswith("pp_") or len(token) != 67:
        raise HTTPException(status_code=401, detail="Invalid API key format")
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    agent = await db.scalar(select(Agent).where(Agent.api_key_hash == key_hash))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if agent.status != "active":
        raise HTTPException(status_code=403, detail="Agent account is suspended")
    return agent


async def get_current_agent_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Agent | None:
    if credentials is None:
        return None
    token = credentials.credentials
    if not token.startswith("pp_") or len(token) != 67:
        return None
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    return await db.scalar(select(Agent).where(Agent.api_key_hash == key_hash))


CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
OptionalAgent = Annotated[Agent | None, Depends(get_current_agent_optional)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
