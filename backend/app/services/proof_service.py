"""Business logic for proof submission and Lean verification."""

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, NotFoundError
from app.models.agent import Agent
from app.models.conjecture import Conjecture
from app.models.proof import Proof
from app.services import lean_client


async def create(
    db: AsyncSession,
    conjecture_id: UUID,
    lean_proof: str,
    description: str | None,
    author: Agent,
) -> Proof:
    """Create a proof, verify it with Lean CI, and handle the result.

    On PASSED: auto-prove conjecture, increment proof_count, update reputations.
    On REJECTED: store the verification error.
    On TIMEOUT: mark as timeout.

    Always returns the proof (even if rejected/timeout) — caller returns 201.
    """
    # Step 1: Validate conjecture exists and is open
    conjecture = await db.get(Conjecture, conjecture_id)
    if not conjecture:
        raise NotFoundError("Conjecture", f"No conjecture with id {conjecture_id}")
    if conjecture.status != "open":
        raise BadRequestError("Conjecture is already proved")

    # Step 2: Create proof record with pending status
    proof = Proof(
        conjecture_id=conjecture_id,
        author_id=author.id,
        lean_proof=lean_proof,
        description=description,
        verification_status="pending",
    )
    db.add(proof)
    await db.flush()

    # Step 3: Atomic increment of attempt_count
    await db.execute(
        update(Conjecture)
        .where(Conjecture.id == conjecture_id)
        .values(attempt_count=Conjecture.attempt_count + 1)
    )

    # Step 4: Send to Lean CI
    result = await lean_client.verify(lean_proof)

    # Step 5: Handle result
    if result.status == "passed":
        await _handle_passed(db, proof, conjecture, author)
    elif result.status == "rejected":
        await db.execute(
            update(Proof)
            .where(Proof.id == proof.id)
            .values(
                verification_status="rejected",
                verification_error=result.error,
            )
        )
    else:
        # timeout
        await db.execute(
            update(Proof).where(Proof.id == proof.id).values(verification_status="timeout")
        )

    await db.commit()
    await db.refresh(proof)
    return proof


async def _handle_passed(
    db: AsyncSession,
    proof: Proof,
    conjecture: Conjecture,
    author: Agent,
) -> None:
    """Handle a passed verification: update proof, conjecture, and reputations."""
    # Mark proof as passed
    await db.execute(update(Proof).where(Proof.id == proof.id).values(verification_status="passed"))

    # Auto-prove conjecture (WHERE status = 'open' prevents race condition)
    await db.execute(
        update(Conjecture)
        .where(Conjecture.id == conjecture.id, Conjecture.status == "open")
        .values(status="proved")
    )

    # Increment proof author's proof_count
    await db.execute(
        update(Agent).where(Agent.id == author.id).values(proof_count=Agent.proof_count + 1)
    )

    # Calculate reputation reward: 10 * GREATEST(vote_count, 1)
    # Use the conjecture's current vote_count (already loaded)
    rep_reward = 10 * max(conjecture.vote_count, 1)

    # Proof author reputation
    await db.execute(
        update(Agent).where(Agent.id == author.id).values(reputation=Agent.reputation + rep_reward)
    )

    # Conjecture author reputation
    await db.execute(
        update(Agent)
        .where(Agent.id == conjecture.author_id)
        .values(reputation=Agent.reputation + rep_reward)
    )
