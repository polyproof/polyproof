"""Business logic for proof submission and Lean verification."""

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.agent import Agent
from app.models.conjecture import Conjecture
from app.models.proof import Proof
from app.services import lean_client


async def create(
    db: AsyncSession,
    conjecture_id: UUID,
    lean_proof: str,
    description: str,
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
    if conjecture.review_status != "approved":
        raise BadRequestError("Proofs can only be submitted on approved conjectures")
    if conjecture.status != "open":
        raise BadRequestError("Conjecture is already proved")

    # Step 2: Platform-wide dedup — same conjecture, same normalized tactics
    # Normalize by collapsing all whitespace to single spaces and trimming
    normalized_tactics = " ".join(lean_proof.split())
    existing = await db.scalar(
        select(Proof.id)
        .where(Proof.conjecture_id == conjecture.id)
        .where(
            func.btrim(func.regexp_replace(Proof.lean_proof, r"\s+", " ", "g"))
            == normalized_tactics
        )
        .limit(1)
    )
    if existing:
        raise ConflictError("This exact proof has already been submitted for this conjecture")

    # Step 3: Create proof record with pending status
    proof = Proof(
        conjecture_id=conjecture_id,
        author_id=author.id,
        lean_proof=lean_proof,
        description=description,
        verification_status="pending",
    )
    db.add(proof)
    await db.flush()

    # Step 4: Atomic increment of attempt_count
    await db.execute(
        update(Conjecture)
        .where(Conjecture.id == conjecture_id)
        .values(attempt_count=Conjecture.attempt_count + 1)
    )

    # Step 5: Send to Lean CI using locked signature
    result = await lean_client.verify_proof(
        lean_statement=conjecture.lean_statement,
        agent_tactics=lean_proof,
    )

    # Step 6: Handle result
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

    # Lock the conjecture row and update status atomically
    locked_conjecture = await db.scalar(
        select(Conjecture).where(Conjecture.id == conjecture.id).with_for_update()
    )
    if locked_conjecture and locked_conjecture.status == "open":
        await db.execute(
            update(Conjecture).where(Conjecture.id == conjecture.id).values(status="proved")
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
