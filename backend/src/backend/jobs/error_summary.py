"""Teacher-facing Traditional Chinese summaries for `jobs.error`.

`jobs.error` is shown in the job center as-is (docs/question-bank.md,
docs/architecture.md, docs/decisions/2026-08-17-compact-headers-and-job-errors.md).
It must be a short sentence a teacher can read: counts, question-type names,
reason classes. It must not contain exception class names, Python repr,
payload dumps, or chunk-id lists. Full exceptions stay in backend logs.
"""

from collections.abc import Sequence

JOB_FAILED = "任務失敗"
UNKNOWN_JOB_KIND = "任務種類不存在"

GENERATION_SOURCE_REFERENTIAL = "題幹引用教材"
EMBED_MISSING = "題目不存在"
EMBED_UNPARSABLE = "題目內容無法向量化"

_QUESTION_TYPE_LABELS: dict[str, str] = {
    "single_choice": "單選題",
    "true_false": "是非題",
    "fill_blank": "填充題",
    "short_answer": "問答題",
    "comparison": "比較題",
    "analogy": "類比題",
}


class JobFailed(Exception):
    """Handler-raised total failure whose message is already a human summary.

    Worker writes `summary` to `jobs.error` as-is. Other uncaught exceptions
    become `JOB_FAILED`; the original exception is still logged.
    """

    def __init__(self, summary: str) -> None:
        self.summary = summary
        super().__init__(summary)


def join_summaries(parts: Sequence[str]) -> str:
    return "；".join(part for part in parts if part)


def question_type_label(question_type: str) -> str:
    return _QUESTION_TYPE_LABELS.get(question_type, "未知題型")


def generation_unknown_type() -> str:
    return "未知題型"


def generation_no_material(question_type: str) -> str:
    return f"{question_type_label(question_type)}找不到可用素材"


def generation_short_material(requested: int, found: int) -> str:
    return f"要求 {requested} 題，可用素材只有 {found} 題"


def summarize_counted_failures(
    count: int, verb: str, reasons: Sequence[str | None]
) -> str:
    """`N 題{verb}失敗` , with a parenthetical reason when every failure
    shares one non-empty reason class."""
    if count <= 0:
        return ""
    head = f"{count} 題{verb}失敗"
    unique = {reason for reason in reasons if reason}
    if unique and all(reason for reason in reasons) and len(unique) == 1:
        return f"{head}（{next(iter(unique))}）"
    return head


def summarize_generation_failures(reasons: Sequence[str | None]) -> str:
    return summarize_counted_failures(len(reasons), "出題", reasons)


def summarize_embedding_failures(reasons: Sequence[str | None]) -> str:
    return summarize_counted_failures(len(reasons), "向量化", reasons)


def error_for_uncaught(exc: BaseException) -> str:
    """Map an uncaught handler exception to a `jobs.error` string."""
    if isinstance(exc, JobFailed) and exc.summary:
        return exc.summary
    return JOB_FAILED
