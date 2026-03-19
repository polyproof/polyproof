from pydantic import BaseModel, Field


class VoteRequest(BaseModel):
    direction: str = Field(..., pattern=r"^(up|down)$")


class VoteResponse(BaseModel):
    vote_count: int
    user_vote: int | None
