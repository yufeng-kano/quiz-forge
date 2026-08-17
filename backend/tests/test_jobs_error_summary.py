"""Teacher-facing `jobs.error` wording (`backend.jobs.error_summary`)."""

from backend.jobs.error_summary import (
    GENERATION_SOURCE_REFERENTIAL,
    JOB_FAILED,
    JobFailed,
    error_for_uncaught,
    generation_no_material,
    generation_short_material,
    generation_unknown_type,
    join_summaries,
    summarize_embedding_failures,
    summarize_generation_failures,
)


def test_generation_summaries_use_type_and_counts_not_repr() -> None:
    assert generation_unknown_type() == "未知題型"
    assert generation_no_material("single_choice") == "單選題找不到可用素材"
    assert generation_no_material("essay") == "未知題型找不到可用素材"
    assert generation_short_material(5, 3) == "要求 5 題，可用素材只有 3 題"


def test_generation_failures_share_reason_only_when_every_failure_matches() -> None:
    assert summarize_generation_failures([]) == ""
    assert summarize_generation_failures([None]) == "1 題出題失敗"
    assert (
        summarize_generation_failures([GENERATION_SOURCE_REFERENTIAL])
        == "1 題出題失敗（題幹引用教材）"
    )
    assert (
        summarize_generation_failures(
            [GENERATION_SOURCE_REFERENTIAL, GENERATION_SOURCE_REFERENTIAL]
        )
        == "2 題出題失敗（題幹引用教材）"
    )
    assert (
        summarize_generation_failures([GENERATION_SOURCE_REFERENTIAL, None])
        == "2 題出題失敗"
    )


def test_embedding_failures_do_not_list_ids() -> None:
    assert summarize_embedding_failures(["題目不存在"]) == "1 題向量化失敗（題目不存在）"
    assert summarize_embedding_failures(["題目不存在", None]) == "2 題向量化失敗"


def test_join_summaries_uses_ideographic_semicolon() -> None:
    assert join_summaries(["單選題找不到可用素材", "1 題出題失敗"]) == (
        "單選題找不到可用素材；1 題出題失敗"
    )


def test_uncaught_exception_is_generic_unless_already_human() -> None:
    assert error_for_uncaught(ValueError("payload={!r}")) == JOB_FAILED
    assert error_for_uncaught(JobFailed("1 題出題失敗（題幹引用教材）")) == (
        "1 題出題失敗（題幹引用教材）"
    )
