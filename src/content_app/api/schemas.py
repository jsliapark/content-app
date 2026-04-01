from typing import Literal

from pydantic import BaseModel, Field


class StartRunRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    platform: Literal["linkedin", "twitter", "blog"]
    tone: str = Field(..., min_length=1)


class StartRunResponse(BaseModel):
    run_id: str
