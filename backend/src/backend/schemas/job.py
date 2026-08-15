"""Response schema for `GET /v1/jobs/{id}` and `POST /v1/jobs/{id}/retry`."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    progress: str
    error: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class JobSummaryOut(BaseModel):
    """Minimal job info embedded in another resource (e.g. a document's
    `latest_job`) — just enough for the UI to show status/error inline and
    call `POST /v1/jobs/{id}/retry` without a separate lookup."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    error: str | None
