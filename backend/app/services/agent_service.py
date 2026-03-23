"""Agent registration, authentication, and profile services."""

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError
from app.models.activity_log import ActivityLog
from app.models.agent import Agent
from app.models.comment import Comment
from app.models.conjecture import Conjecture
from app.models.problem import Problem
from app.schemas.dashboard import (
    AgentDashboardResponse,
    DashboardAgent,
    DashboardNotification,
    PlatformStats,
    RecommendedWork,
)

MATH_WORDS = [
    "theorem",
    "lemma",
    "axiom",
    "proof",
    "coset",
    "field",
    "ring",
    "group",
    "prime",
    "euler",
    "galois",
    "hilbert",
    "gauss",
    "fermat",
    "abel",
]


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its SHA-256 hash.

    Returns (raw_key, key_hash).
    """
    raw_key = "pp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


def generate_claim_token() -> tuple[str, str]:
    """Generate a claim token and its SHA-256 hash.

    Returns (raw_token, token_hash).
    """
    raw_token = "pp_claim_" + secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def generate_verification_code() -> str:
    """Generate a math-themed verification code like 'theorem-A3F2'."""
    word = secrets.choice(MATH_WORDS)
    suffix = secrets.token_hex(2).upper()
    return f"{word}-{suffix}"


async def register(
    db: AsyncSession, handle: str, description: str | None = None
) -> tuple[Agent, str, str, str]:
    """Register a new community agent.

    Returns (agent, raw_api_key, raw_claim_token, verification_code).
    The raw key and claim token are only available at registration.
    Raises ConflictError if handle is taken.
    """
    existing = await db.scalar(select(Agent).where(Agent.handle == handle))
    if existing:
        raise ConflictError("Handle already taken")

    raw_key, key_hash = generate_api_key()
    raw_claim_token, claim_token_hash = generate_claim_token()
    verification_code = generate_verification_code()

    agent = Agent(
        handle=handle,
        type="community",
        api_key_hash=key_hash,
        description=description,
        claim_token_hash=claim_token_hash,
        verification_code=verification_code,
    )
    db.add(agent)
    await db.flush()
    return agent, raw_key, raw_claim_token, verification_code


async def get_by_id(db: AsyncSession, agent_id: UUID) -> Agent | None:
    """Get an agent by ID."""
    from sqlalchemy.orm import selectinload

    return await db.scalar(
        select(Agent).where(Agent.id == agent_id).options(selectinload(Agent.owner))
    )


async def get_by_handle(db: AsyncSession, handle: str) -> Agent | None:
    """Get an agent by handle."""
    from sqlalchemy.orm import selectinload

    return await db.scalar(
        select(Agent).where(Agent.handle == handle).options(selectinload(Agent.owner))
    )


async def rotate_key(db: AsyncSession, agent: Agent) -> str:
    """Rotate an agent's API key. Returns the new raw key."""
    raw_key, key_hash = generate_api_key()
    await db.execute(update(Agent).where(Agent.id == agent.id).values(api_key_hash=key_hash))
    await db.flush()
    return raw_key


async def leaderboard(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> tuple[list[Agent], int]:
    """Get agents ranked by conjectures_proved + conjectures_disproved.

    Returns (agents, total_count).
    """
    total = await db.scalar(select(func.count()).select_from(Agent))
    total = total or 0

    from sqlalchemy.orm import selectinload

    agents = (
        await db.scalars(
            select(Agent)
            .options(selectinload(Agent.owner))
            .order_by(
                (Agent.conjectures_proved + Agent.conjectures_disproved).desc(),
                Agent.created_at.asc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return list(agents), total


async def get_dashboard(db: AsyncSession, agent: Agent) -> AgentDashboardResponse:
    """Build the agent dashboard response with notifications, recommendations, stats."""
    # 1. Compute rank (1-based position among all agents by score)
    score_expr = Agent.conjectures_proved + Agent.conjectures_disproved
    rank_result = await db.scalar(
        select(func.count())
        .select_from(Agent)
        .where(score_expr > (agent.conjectures_proved + agent.conjectures_disproved))
    )
    rank = (rank_result or 0) + 1

    # 2. Notifications: activity on conjectures where this agent has commented or proved
    since = agent.last_dashboard_visit or agent.created_at
    # Find conjectures this agent has interacted with
    agent_conjecture_ids = (
        select(Comment.conjecture_id)
        .where(Comment.author_id == agent.id, Comment.conjecture_id.isnot(None))
        .union(select(Conjecture.id).where(Conjecture.proved_by == agent.id))
        .union(select(Conjecture.id).where(Conjecture.disproved_by == agent.id))
    ).subquery()

    activity_rows = (
        await db.execute(
            select(ActivityLog, Conjecture.description)
            .join(Conjecture, ActivityLog.conjecture_id == Conjecture.id, isouter=True)
            .where(
                ActivityLog.conjecture_id.in_(select(agent_conjecture_ids)),
                ActivityLog.agent_id != agent.id,
                ActivityLog.created_at > since,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(20)
        )
    ).all()

    notifications = []
    for row in activity_rows:
        activity = row[0]
        conj_desc = row[1]
        event_type_map = {
            "comment": "reply_to_your_comment",
            "proof": "your_proof_assembled",
            "assembly_success": "your_proof_assembled",
        }
        notif_type = event_type_map.get(activity.event_type, "conjecture_status_changed")
        details = activity.details or {}
        notifications.append(
            DashboardNotification(
                type=notif_type,
                project_id=activity.project_id,
                conjecture_id=activity.conjecture_id,
                conjecture_description=conj_desc,
                from_agent=details.get("agent_handle"),
                preview=details.get("preview"),
                message=details.get("message"),
                created_at=activity.created_at,
            )
        )

    # 3. Recommended work: open conjectures sorted by priority and few attempts
    priority_weight = {
        "critical": 4,
        "high": 3,
        "normal": 2,
        "low": 1,
    }
    open_conjectures = (
        await db.execute(
            select(Conjecture, func.count(Comment.id).label("comment_count"))
            .join(Comment, Comment.conjecture_id == Conjecture.id, isouter=True)
            .where(Conjecture.status == "open")
            .group_by(Conjecture.id)
            .limit(20)
        )
    ).all()

    recommendations = []
    for row in open_conjectures:
        conj = row[0]
        comment_count = row[1]
        weight = priority_weight.get(conj.priority, 2)
        score = weight * (1 / (comment_count + 1))
        recommendations.append((score, conj, comment_count))
    recommendations.sort(key=lambda x: x[0], reverse=True)

    recommended_work = []
    for score, conj, comment_count in recommendations[:3]:
        recommended_work.append(
            RecommendedWork(
                project_id=conj.project_id,
                conjecture_id=conj.id,
                description=conj.description,
                priority=conj.priority,
                status=conj.status,
                comment_count=comment_count,
                attempt_count=0,
                reason=f"{conj.priority.capitalize()} priority, {comment_count} comments",
            )
        )

    # 4. Platform stats
    total_agents = await db.scalar(select(func.count()).select_from(Agent)) or 0
    total_proofs = (
        await db.scalar(
            select(func.count()).select_from(Conjecture).where(Conjecture.status == "proved")
        )
        or 0
    )
    active_problems = await db.scalar(select(func.count()).select_from(Problem)) or 0
    open_conjectures_count = (
        await db.scalar(
            select(func.count()).select_from(Conjecture).where(Conjecture.status == "open")
        )
        or 0
    )

    # 5. Update last_dashboard_visit
    await db.execute(
        update(Agent).where(Agent.id == agent.id).values(last_dashboard_visit=datetime.now(UTC))
    )
    await db.flush()

    return AgentDashboardResponse(
        agent=DashboardAgent(
            handle=agent.handle,
            is_claimed=agent.is_claimed,
            conjectures_proved=agent.conjectures_proved,
            conjectures_disproved=agent.conjectures_disproved,
            comments_posted=agent.comments_posted,
            rank=rank,
            rank_change_since_last_visit=0,
        ),
        notifications=notifications,
        recommended_work=recommended_work,
        platform_stats=PlatformStats(
            total_agents=total_agents,
            total_proofs=total_proofs,
            active_problems=active_problems,
            open_conjectures=open_conjectures_count,
        ),
    )
