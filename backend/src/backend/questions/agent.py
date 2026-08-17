"""`bank_agent_turn` job handler — one conversation turn of the 題庫選題助手
(docs/question-bank.md 題庫選題助手（對話 agent）; docs/decisions/
2026-08-17-bank-agent-semantic-selection.md D4/D5/D6).

D4 — structured output + a backend-owned bounded loop, not tool calling: each
step is one `LLMClient.chat(response_model=BankAgentStep, ...)` call
(`response_format: json_schema`, per .rule — never parse free text), capped
at `BANK_AGENT_MAX_STEPS` iterations. `action="search"` runs a query and
feeds a compact summary back as the next chat message; `action="propose"` or
`"reply"` ends the turn. If the step cap is hit before either of those, the
loop still ends — but with an explanatory reply
(`backend.questions.agent_prompts.step_cap_reply`), never a silent
truncation.

D3 (reuse, not duplicate) — `action="search"` calls
`backend.questions.search.search_questions`, the exact function `GET
/v1/questions`'s `similar_to`/`q`/`type`/`difficulty`/`category_id` filters
already go through, so the agent's search and a human's manual filter can
never drift apart. The one addition here: every agent search is hardcoded
`status="approved"` (not exposed as a field the LLM can set) — `action=
"propose"` can only ever end up recommending questions that are actually
usable in an export (see D5 below), so there is no point letting the agent
even see draft/rejected rows it could never legitimately propose.

D5 — the agent only proposes, never mutates. This module never sets
`Question.status`, never touches `exports`, and the one write it does make
(the new `conversation_messages` row) stores the model's proposal in
`proposed_question_ids` after re-validating each id actually exists and is
still `approved` (dropped otherwise — never stored as garbage the frontend
would render a broken card for).

D6 — persistence: exactly one `conversation_messages` row is written per
turn (`role="assistant"`), carrying the final `reply` as `content`, the
validated proposal, and a `steps` jsonb log of every step this turn actually
ran (search filters + hit count, or the terminal propose/reply action) — the
「查詢過程」the frontend can expand.
"""

from typing import Literal

from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.ingestion.classification import load_existing_categories
from backend.jobs.context import JobContext
from backend.jobs.registry import register_handler
from backend.llm.client import LLMClient, get_llm_client
from backend.models.category import Category
from backend.models.chunk import Chunk
from backend.models.conversation import Conversation, ConversationMessage
from backend.models.question import Question
from backend.questions.agent_prompts import (
    SearchHitSummary,
    build_system_prompt,
    format_search_result,
    step_cap_reply,
)
from backend.questions.schemas import QuestionType
from backend.questions.search import search_questions


class BankAgentSearchParams(BaseModel):
    """`action="search"` filters (docs/question-bank.md — `similar_to`／
    `q`／`type`／`difficulty`／`category_id`／`limit`). Deliberately the same
    field set `search_questions` takes minus `status`: the agent never
    controls `status` (see module docstring — every agent search is
    hardcoded `status="approved"`)."""

    similar_to: str | None = None
    q: str | None = None
    type: QuestionType | None = None
    difficulty: str | None = None
    category_id: int | None = None
    limit: int | None = None


class BankAgentStep(BaseModel):
    """One step of the bounded loop's structured output (docs/question-bank.md
    題庫選題助手（對話 agent）; D4). `search`/`question_ids`/`reply` are all
    optional at the schema level (strict-mode json_schema still requires
    every key present, just nullable) because only one is meaningful per
    `action`; the handler reads only the field that matches `action`."""

    action: Literal["search", "propose", "reply"]
    search: BankAgentSearchParams | None = None
    question_ids: list[int] | None = None
    reply: str | None = None


def _role_message(role: str, content: str) -> ChatCompletionMessageParam:
    """Builds one chat message with `role` narrowed to a literal the
    `openai` SDK's `TypedDict`s accept — `conversation_messages.role` is a
    plain `str` at the ORM layer (CHECK-constrained, not a `Literal`), so a
    direct `{"role": role, ...}` dict literal wouldn't type-check against
    `ChatCompletionMessageParam`'s union of per-role `TypedDict`s."""
    if role == "assistant":
        assistant_message: ChatCompletionAssistantMessageParam = {
            "role": "assistant",
            "content": content,
        }
        return assistant_message
    user_message: ChatCompletionUserMessageParam = {"role": "user", "content": content}
    return user_message


def _preview_text(question_type: str, payload: dict[str, object]) -> str:
    """A short "what is this question about" string for the search-hit
    summary (docs/question-bank.md — 題幹前 N 字). Reads the stored payload
    directly rather than re-validating through `parse_question`: every row
    reaching here already passed that validation at write time (`POST
    /v1/questions`, `PATCH`, or `generate_questions`), and this is a display
    trim, not a correctness-critical path, so a query returning many hits
    doesn't pay for a full re-parse of each one just to preview it.

    `analogy` questions store no `stem` (docs/question-bank.md — 題幹由
    a/b/c 組出), so their preview is built from the three slots instead.
    """
    if question_type == "analogy":
        a = payload.get("a", "")
        b = payload.get("b", "")
        c = payload.get("c", "")
        return f"{a} 之於 {b}，猶如 {c} 之於＿＿"
    stem = payload.get("stem")
    return stem if isinstance(stem, str) else ""


async def _category_paths(session: AsyncSession, questions: list[Question]) -> dict[int, str]:
    """`{question.id: "科目 > 主題"}` for every question in `questions`, built
    from each question's `source_chunk_ids` -> `chunks.category_id` ->
    `categories` parent chain. A question can trace back to chunks in more
    than one category (rare, but possible after edits); those are joined
    with `、`. `categories` is small in this single-user system (see
    `backend.ingestion.classification.load_existing_categories`'s same
    assumption), so this loads the whole table once and walks `parent_id`
    chains in Python instead of a recursive CTE.
    """
    chunk_ids = {chunk_id for question in questions for chunk_id in question.source_chunk_ids}
    if not chunk_ids:
        return {question.id: "未分類" for question in questions}

    chunk_rows = (
        await session.execute(select(Chunk.id, Chunk.category_id).where(Chunk.id.in_(chunk_ids)))
    ).all()
    category_id_by_chunk: dict[int, int | None] = {
        chunk_id: category_id for chunk_id, category_id in chunk_rows
    }

    all_categories = (await session.execute(select(Category))).scalars().all()
    categories_by_id = {category.id: category for category in all_categories}

    def path_for(category_id: int) -> str:
        names: list[str] = []
        current = categories_by_id.get(category_id)
        while current is not None:
            names.append(current.name)
            current = (
                categories_by_id.get(current.parent_id) if current.parent_id is not None else None
            )
        return " > ".join(reversed(names))

    paths: dict[int, str] = {}
    for question in questions:
        category_ids: set[int] = set()
        for chunk_id in question.source_chunk_ids:
            category_id = category_id_by_chunk.get(chunk_id)
            if category_id is not None:
                category_ids.add(category_id)
        paths[question.id] = (
            "、".join(sorted(path_for(category_id) for category_id in category_ids))
            if category_ids
            else "未分類"
        )
    return paths


async def _run_search(
    session: AsyncSession,
    settings: Settings,
    llm: LLMClient,
    params: BankAgentSearchParams | None,
) -> tuple[list[SearchHitSummary], dict[str, object], int]:
    """Runs one `action="search"` step through the shared `search_questions`
    query path (D3), hardcoding `status="approved"` (see module docstring).
    Returns the capped, display-ready hit summaries, the jsonb-ready filters
    log entry, and the total hit count (pre-cap) for the "命中 N 筆" message.
    """
    effective = params or BankAgentSearchParams()
    max_hits = settings.bank_agent_search_limit
    requested_limit = effective.limit if effective.limit and effective.limit > 0 else max_hits
    limit = min(requested_limit, max_hits)

    result = await search_questions(
        session,
        settings,
        llm,
        status="approved",
        type=effective.type,
        difficulty=effective.difficulty,
        category_id=effective.category_id,
        q=effective.q,
        similar_to=effective.similar_to,
        limit=limit,
    )
    category_paths = await _category_paths(session, result.items)
    hits = [
        SearchHitSummary(
            id=question.id,
            type=question.type,
            difficulty=question.difficulty,
            category_path=category_paths.get(question.id, "未分類"),
            stem_preview=_preview_text(question.type, question.payload)[
                : settings.bank_agent_stem_preview_chars
            ],
        )
        for question in result.items
    ]
    filters_log: dict[str, object] = {
        "similar_to": effective.similar_to,
        "q": effective.q,
        "type": effective.type,
        "difficulty": effective.difficulty,
        "category_id": effective.category_id,
        "limit": limit,
    }
    return hits, filters_log, result.total


async def _validate_proposed_ids(session: AsyncSession, question_ids: list[int]) -> list[int]:
    """De-duplicated, order-preserving subset of `question_ids` that both
    exist and are currently `approved` (docs/question-bank.md — 只有
    approved 題目出現在...匯出範圍). An unknown or non-approved id is simply
    dropped, never stored — the frontend must never be asked to render a
    "加入選取" card for a question it can't actually export."""
    if not question_ids:
        return []
    valid_ids = set(
        (
            await session.execute(
                select(Question.id).where(
                    Question.id.in_(question_ids), Question.status == "approved"
                )
            )
        )
        .scalars()
        .all()
    )
    seen: set[int] = set()
    ordered: list[int] = []
    for question_id in question_ids:
        if question_id in valid_ids and question_id not in seen:
            seen.add(question_id)
            ordered.append(question_id)
    return ordered


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"job payload missing integer {key!r}: {payload!r}")
    return value


def _optional_int_list(payload: dict[str, object], key: str) -> list[int]:
    value = payload.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"job payload field {key!r} must be a list of integers: {payload!r}")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise ValueError(f"job payload field {key!r} must be a list of integers: {payload!r}")
        result.append(item)
    return result


@register_handler("bank_agent_turn")
async def bank_agent_turn(ctx: JobContext) -> None:
    """One `bank_agent_turn` job = one conversation turn (docs/question-bank.md
    — 一個回合＝一個 job；`POST /v1/conversations/{id}/messages` enqueues
    exactly one of these per user message).

    Payload: `{"conversation_id": int, "message_id": int,
    "selected_question_ids": [int]}` — `message_id` is the just-inserted
    `conversation_messages` row for the user's new message; the prompt's
    「最近 N 則歷史訊息」excludes it (queried as `id < message_id`) and the
    new message's own content is appended separately as this turn's latest
    user message, matching docs/question-bank.md's phrasing (「最近
    `BANK_AGENT_HISTORY_LIMIT` 則訊息...以及使用者這次的輸入」).

    A malformed payload (missing/wrong-typed keys, an unknown conversation
    or message id) raises straight out of the handler — a programming/data
    error, not a per-step failure, so it fails the whole job like
    `generate_questions`'s `_require_items` does for its own malformed
    payload case.
    """
    settings = get_settings()
    llm = get_llm_client()
    session = ctx.session
    payload = ctx.payload

    conversation_id = _require_int(payload, "conversation_id")
    message_id = _require_int(payload, "message_id")
    selected_question_ids = _optional_int_list(payload, "selected_question_ids")

    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        raise ValueError(f"conversation {conversation_id} not found")
    user_message = await session.get(ConversationMessage, message_id)
    if user_message is None or user_message.conversation_id != conversation_id:
        raise ValueError(f"message {message_id} not found in conversation {conversation_id}")

    history_rows = (
        (
            await session.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation_id,
                    ConversationMessage.id < message_id,
                )
                .order_by(ConversationMessage.id.desc())
                .limit(settings.bank_agent_history_limit)
            )
        )
        .scalars()
        .all()
    )
    history = list(reversed(history_rows))

    category_tree = await load_existing_categories(
        session,
        subjects_limit=settings.classification_existing_subjects_limit,
        topics_per_subject_limit=settings.classification_existing_topics_per_subject_limit,
    )
    system_prompt = build_system_prompt(
        max_steps=settings.bank_agent_max_steps,
        category_tree=category_tree,
        selected_question_ids=selected_question_ids,
    )
    system_message: ChatCompletionSystemMessageParam = {"role": "system", "content": system_prompt}
    messages: list[ChatCompletionMessageParam] = [system_message]
    for past_message in history:
        messages.append(_role_message(past_message.role, past_message.content))
    messages.append(_role_message("user", user_message.content))

    max_steps = settings.bank_agent_max_steps
    steps_log: list[dict[str, object]] = []
    final_reply: str | None = None
    proposed_ids: list[int] = []

    for step_index in range(1, max_steps + 1):
        step = await llm.chat(
            messages=messages, response_model=BankAgentStep, purpose="bank_agent_step"
        )
        messages.append(_role_message("assistant", step.model_dump_json()))
        await ctx.set_progress(f"{step_index}/{max_steps}")

        if step.action == "search":
            hits, filters_log, total_hits = await _run_search(session, settings, llm, step.search)
            steps_log.append(
                {
                    "step": step_index,
                    "action": "search",
                    "filters": filters_log,
                    "hit_count": total_hits,
                }
            )
            messages.append(
                _role_message(
                    "user",
                    format_search_result(
                        hits, total_hits=total_hits, limit=settings.bank_agent_search_limit
                    ),
                )
            )
            continue

        if step.action == "propose":
            proposed_ids = await _validate_proposed_ids(session, step.question_ids or [])
            steps_log.append(
                {"step": step_index, "action": "propose", "question_ids": step.question_ids or []}
            )
            final_reply = step.reply or ""
            break

        # step.action == "reply" -- the only remaining member of the Literal.
        steps_log.append({"step": step_index, "action": "reply"})
        final_reply = step.reply or ""
        break

    if final_reply is None:
        # The loop ran out of steps without the model ever choosing
        # propose/reply (docs/question-bank.md — 達步數上限則強制結束並在
        # 回覆中說明): end the turn anyway, with an explanation, never a
        # silent truncation.
        final_reply = step_cap_reply(max_steps)

    session.add(
        ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=final_reply,
            proposed_question_ids=proposed_ids,
            steps=steps_log,
        )
    )
    # Explicit touch: no other column on `conversation` changed this turn,
    # so without this assignment no UPDATE would be emitted and `onupdate=
    # func.now()` would never fire -- `GET /v1/conversations`'s "newest
    # first" ordering is meant to reflect the latest activity, not just
    # title/creation changes.
    conversation.updated_at = func.now()
    await session.commit()
