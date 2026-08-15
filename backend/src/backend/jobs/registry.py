"""Job-kind to handler registry.

Business-logic modules (a future `parse_document`, `generate_questions`,
`export_docx`, ...) register their async handler with `@register_handler
("kind")`; `backend.jobs.worker` looks kinds up here at dispatch time and
never hardcodes them, so new job kinds are purely additive.
"""

from collections.abc import Awaitable, Callable

from backend.jobs.context import JobContext

JobHandler = Callable[[JobContext], Awaitable[None]]

_HANDLERS: dict[str, JobHandler] = {}


def register_handler(kind: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator registering `handler` as the runner for jobs of `kind`.

    Raises `ValueError` if `kind` already has a handler — two handlers
    silently racing for the same kind is a programming error, not something
    to paper over.
    """

    def _decorate(handler: JobHandler) -> JobHandler:
        if kind in _HANDLERS:
            raise ValueError(f"job kind {kind!r} already has a registered handler")
        _HANDLERS[kind] = handler
        return handler

    return _decorate


def get_handler(kind: str) -> JobHandler | None:
    """Look up the handler registered for `kind`, or None if unregistered."""
    return _HANDLERS.get(kind)


def registered_kinds() -> list[str]:
    """All currently registered job kinds, sorted — mainly for introspection/tests."""
    return sorted(_HANDLERS)
