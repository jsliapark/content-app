from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StartRunRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    platform: Literal["linkedin", "twitter", "blog"]
    tone: str = Field(..., min_length=1)


class StartRunResponse(BaseModel):
    run_id: str


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=1)


class GuidelinesRequest(BaseModel):
    guidelines: str = ""


class DeleteSamplesRequest(BaseModel):
    """Mirror brandvoice-mcp ``delete_samples`` (JSON key ``all``; xor non-empty ``sample_ids``)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    sample_ids: list[str] | None = None
    delete_all: bool = Field(default=False, alias="all")

    @model_validator(mode="after")
    def validate_delete_mode(self) -> DeleteSamplesRequest:
        has_ids = bool(self.sample_ids)
        if self.delete_all and has_ids:
            raise ValueError("When all is true, sample_ids must be empty or omitted")
        if not self.delete_all and not has_ids:
            raise ValueError("Provide non-empty sample_ids or set all to true")
        return self
