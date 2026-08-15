"""pg-as-queue background job framework (docs/architecture.md).

Public surface:
    - `register_handler` / `get_handler`: kind -> async handler registry.
    - `JobContext`: what a handler receives (claimed job + progress reporting).
    - `JobWorkerPool`: what the FastAPI lifespan starts/stops.
"""

from backend.jobs.context import JobContext
from backend.jobs.registry import get_handler, register_handler, registered_kinds
from backend.jobs.service import JobWorkerPool

__all__ = [
    "JobContext",
    "JobWorkerPool",
    "get_handler",
    "register_handler",
    "registered_kinds",
]
