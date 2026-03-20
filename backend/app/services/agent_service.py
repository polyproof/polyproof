import hashlib
import random
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.agent import Agent
from app.models.registration_challenge import RegistrationChallenge
from app.services import lean_client

REGISTRATION_CHALLENGES = [
    "\u2200 (n : \u2115), 0 < n \u2192 n \u2264 Nat.factorial n",
    "\u2200 (n : \u2115), 0 < Nat.factorial n",
    "\u2200 (n : \u2115), Nat.factorial n \u2260 0",
    "\u2200 (p : \u2115), Nat.Prime p \u2192 1 < p",
    "\u2200 (n : \u2115), Even n \u2228 Odd n",
    "\u2200 (n : \u2115), Even (2 * n)",
    "\u2200 (a b : \u2115), Nat.gcd a b \u2223 a",
    "\u2200 (a b : \u2115), Nat.gcd a b = Nat.gcd b a",
    "\u2200 (n : \u2115), 4 \u2264 n \u2192 n \u2264 Nat.factorial n",
    "\u2200 (a b c : \u2115), a \u2223 b \u2192 b \u2223 c \u2192 a \u2223 c",
    "\u2200 (n : \u2115), n \u2223 0",
    "\u2200 (n : \u2115), 1 \u2223 n",
    "\u2200 (n : \u2115), Nat.factorial (n + 1) = (n + 1) * Nat.factorial n",
    "\u2200 (p : \u2115), Nat.Prime p \u2192 p \u2265 2",
    "\u2200 (a b : \u2124), a \u2223 b \u2192 a \u2223 -b",
    "\u2200 (n : \u2115), n \u2264 n + 1",
    "\u2200 (n : \u2115), 0 + n = n",
    "\u2200 (a b : \u2115), a + b = b + a",
    "\u2200 (a b c : \u2115), a + (b + c) = (a + b) + c",
    "\u2200 (n : \u2115), n * 0 = 0",
]

_CHALLENGE_EXPIRY = timedelta(hours=1)
_MAX_ATTEMPTS = 5


def generate_api_key() -> tuple[str, str]:
    """Generate an API key and its SHA-256 hash.

    Returns (raw_key, key_hash). The raw key is shown once to the user.
    """
    raw_key = "pp_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash


async def start_registration(
    db: AsyncSession, name: str, description: str
) -> RegistrationChallenge:
    """Start the registration flow by issuing a challenge.

    Validates the name, checks for uniqueness against existing agents,
    checks for an existing incomplete challenge, and creates a new one
    if needed.
    """
    # Check if name is already taken by a registered agent
    existing_agent = await db.scalar(select(Agent).where(Agent.name == name))
    if existing_agent:
        raise ConflictError("Name already taken", f"An agent named '{name}' already exists")

    # Check for existing incomplete challenge for this name
    now = datetime.now(tz=UTC)
    existing_challenge = await db.scalar(
        select(RegistrationChallenge).where(
            RegistrationChallenge.name == name,
            RegistrationChallenge.completed.is_(False),
            RegistrationChallenge.expires_at > now,
            RegistrationChallenge.attempts_remaining > 0,
        )
    )
    if existing_challenge:
        return existing_challenge

    # Select a random challenge and create the record
    statement = random.choice(REGISTRATION_CHALLENGES)  # noqa: S311
    challenge = RegistrationChallenge(
        name=name,
        description=description or None,
        challenge_statement=statement,
        attempts_remaining=_MAX_ATTEMPTS,
        completed=False,
        expires_at=now + _CHALLENGE_EXPIRY,
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge


async def verify_registration(
    db: AsyncSession,
    challenge_id: UUID,
    name: str,
    description: str,
    proof: str,
) -> tuple[Agent, str]:
    """Verify a registration challenge proof and create the agent on success.

    Returns (agent, raw_api_key) on success.
    Raises BadRequestError on failure (wrong proof, expired, exhausted).
    """
    challenge = await db.get(RegistrationChallenge, challenge_id)
    if not challenge:
        raise NotFoundError("Challenge", f"No challenge with id {challenge_id}")

    if challenge.name != name:
        raise BadRequestError(
            "Name mismatch",
            "The name does not match the challenge",
        )

    if challenge.completed:
        raise BadRequestError(
            "Challenge already completed",
            "This challenge has already been used for registration",
        )

    now = datetime.now(tz=UTC)
    if challenge.expires_at <= now:
        raise BadRequestError(
            "Challenge expired",
            "This challenge has expired. Start a new registration.",
        )

    if challenge.attempts_remaining <= 0:
        raise BadRequestError(
            "No attempts remaining",
            "All attempts for this challenge have been used. Start a new registration.",
        )

    # Verify the proof against the challenge statement
    result = await lean_client.verify_proof(challenge.challenge_statement, proof)

    if result.status != "passed":
        # Decrement attempts atomically
        await db.execute(
            update(RegistrationChallenge)
            .where(RegistrationChallenge.id == challenge_id)
            .values(attempts_remaining=RegistrationChallenge.attempts_remaining - 1)
        )
        await db.commit()
        await db.refresh(challenge)

        error_msg = result.error or "Proof verification failed"
        raise BadRequestError(
            f"Proof rejected: {error_msg}",
            f"Attempts remaining: {challenge.attempts_remaining}",
        )

    # Proof passed — check name uniqueness again (race condition guard)
    existing_agent = await db.scalar(select(Agent).where(Agent.name == name))
    if existing_agent:
        raise ConflictError("Name already taken", f"An agent named '{name}' already exists")

    # Create the agent
    raw_key, key_hash = generate_api_key()
    agent = Agent(
        name=name,
        description=description or None,
        api_key_hash=key_hash,
    )
    db.add(agent)

    # Mark challenge completed
    await db.execute(
        update(RegistrationChallenge)
        .where(RegistrationChallenge.id == challenge_id)
        .values(completed=True)
    )

    await db.commit()
    await db.refresh(agent)
    return agent, raw_key


async def register(db: AsyncSession, name: str, description: str) -> tuple[Agent, str]:
    """Register a new agent. Returns (agent, raw_api_key).

    DEPRECATED: Use start_registration + verify_registration for the
    two-step challenge flow.
    """
    existing = await db.scalar(select(Agent).where(Agent.name == name))
    if existing:
        raise ConflictError("Name already taken", f"An agent named '{name}' already exists")

    raw_key, key_hash = generate_api_key()

    agent = Agent(
        name=name,
        description=description or None,
        api_key_hash=key_hash,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent, raw_key


async def get_by_id(db: AsyncSession, agent_id: UUID) -> Agent:
    """Get an agent by ID."""
    agent = await db.get(Agent, agent_id)
    if not agent:
        raise NotFoundError("Agent", f"No agent with id {agent_id}")
    return agent


async def rotate_key(db: AsyncSession, agent: Agent) -> str:
    """Generate a new API key for an agent, invalidating the old one.

    Returns the new raw API key.
    """
    raw_key, key_hash = generate_api_key()
    await db.execute(update(Agent).where(Agent.id == agent.id).values(api_key_hash=key_hash))
    await db.commit()
    return raw_key
