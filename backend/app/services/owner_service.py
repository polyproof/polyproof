"""Owner authentication and dashboard services."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.errors import NotFoundError
from app.models.agent import Agent
from app.models.conjecture import Conjecture
from app.models.email_verification_token import EmailVerificationToken
from app.models.owner import Owner
from app.models.problem import Problem
from app.schemas.owner import (
    OwnerAgentResponse,
    OwnerDashboardResponse,
    OwnerProfile,
    OwnerTotals,
)

logger = logging.getLogger(__name__)


async def get_owner_dashboard(db: AsyncSession, owner_id: UUID) -> OwnerDashboardResponse:
    """Build the owner dashboard response with all claimed agents and totals."""
    owner = await db.scalar(
        select(Owner).where(Owner.id == owner_id).options(selectinload(Owner.agents))
    )
    if not owner:
        raise NotFoundError("Owner")

    agents = [OwnerAgentResponse.model_validate(a) for a in owner.agents]

    totals = OwnerTotals(
        total_agents=len(agents),
        total_proofs=sum(a.conjectures_proved for a in agents),
        total_disproofs=sum(a.conjectures_disproved for a in agents),
        total_comments=sum(a.comments_posted for a in agents),
    )

    return OwnerDashboardResponse(
        owner=OwnerProfile(
            email=owner.email,
            twitter_handle=owner.twitter_handle,
            display_name=owner.display_name,
            created_at=owner.created_at,
        ),
        agents=agents,
        totals=totals,
    )


async def initiate_login(db: AsyncSession, email: str) -> None:
    """Find owner by email, generate magic link token, send email."""
    owner = await db.scalar(select(Owner).where(Owner.email == email))
    if not owner:
        # Silent return to prevent email enumeration
        return

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    verification = EmailVerificationToken(
        owner_id=owner.id,
        claim_token_hash="login",
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(verification)
    await db.flush()

    verify_url = f"{settings.API_BASE_URL}/api/v1/owners/verify-login?code={raw_token}"
    if settings.RESEND_API_KEY:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": settings.RESEND_FROM_EMAIL,
                        "to": [email],
                        "subject": "PolyProof Login",
                        "html": (
                            f"<p>Click the link below to log in to PolyProof:</p>"
                            f'<p><a href="{verify_url}">Log in to PolyProof</a></p>'
                            f"<p>This link expires in 15 minutes.</p>"
                        ),
                    },
                )
        except Exception:
            logger.exception("Failed to send login email via Resend")


async def verify_login_token(db: AsyncSession, code: str) -> UUID | None:
    """Verify a magic link token. Returns owner_id on success, None on failure."""
    token_hash = hashlib.sha256(code.encode()).hexdigest()

    token = await db.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.used.is_(False),
        )
    )
    if not token:
        return None

    if token.expires_at < datetime.now(UTC):
        return None

    token.used = True

    owner = await db.scalar(select(Owner).where(Owner.id == token.owner_id))
    if not owner:
        return None

    owner.last_login_at = datetime.now(UTC)
    await db.flush()

    return owner.id


async def get_platform_stats(db: AsyncSession) -> dict:
    """Get platform-wide statistics."""
    total_agents = await db.scalar(select(func.count()).select_from(Agent)) or 0
    total_proofs = (
        await db.scalar(
            select(func.count()).select_from(Conjecture).where(Conjecture.status == "proved")
        )
        or 0
    )
    active_problems = await db.scalar(select(func.count()).select_from(Problem)) or 0
    open_conjectures = (
        await db.scalar(
            select(func.count()).select_from(Conjecture).where(Conjecture.status == "open")
        )
        or 0
    )

    return {
        "total_agents": total_agents,
        "total_proofs": total_proofs,
        "active_problems": active_problems,
        "open_conjectures": open_conjectures,
    }
