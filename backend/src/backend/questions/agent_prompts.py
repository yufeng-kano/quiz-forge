"""Prompt templates for the 題庫選題助手 (`backend.questions.agent`), kept in
their own module — never inlined in `agent.py` — matching this codebase's
existing convention (`backend.questions.prompts`, `backend.ingestion.prompts`).

docs/question-bank.md 題庫選題助手（對話 agent）; docs/decisions/
2026-08-17-bank-agent-semantic-selection.md D4.
"""

from dataclasses import dataclass

# docs/question-bank.md 題型與 payload schema — the six types the agent's
# `search`/`propose` steps operate over. Kept as a plain tuple (not imported
# from `backend.questions.schemas.QuestionType`) because this is prose for a
# prompt, not a validated value.
_QUESTION_TYPES_LINE = (
    "comparison（比較題）、analogy（類比題）、single_choice（單選題）、"
    "true_false（是非題）、fill_blank（填充題）、short_answer（問答題）"
)

# 難度字彙比照分類 prompt 的值（backend.ingestion.prompts.CLASSIFICATION_PROMPT_TEMPLATE
# — 「只能是「簡單」「中等」「困難」三者之一」），但 questions.difficulty 本身沒有
# CHECK constraint 限制值域，所以這裡只當作「最常見既有值」的提示，不是硬性規則。
_DIFFICULTY_VOCAB_LINE = "簡單、中等、困難"

BANK_AGENT_SYSTEM_PROMPT_TEMPLATE = """\
你是題庫選題助手，幫使用者從既有題庫中找出符合需求的題目，供組卷使用。全部使用繁體
中文回覆，且每一步都要輸出符合指定 JSON 結構的內容。

題庫裡的題型固定是這六種：{question_types}。
難度是自由文字欄位，最常見的既有值是：{difficulty_vocab}（也可能是其他使用者自訂
的難度字彙）。

你每一步只能做以下三件事之一：

- action="search"：在 search 欄位下條件查詢題庫，可用 similar_to（語意搜尋自由文
  字）、q（字面 ILIKE 搜尋）、type（六種題型之一）、difficulty、category_id、limit，
  每個欄位都可以留空（null）表示不限制那個條件。後端執行後會把命中題目的精簡摘要
  （id、題型、難度、分類路徑、題幹片段）回覆給你，你可以再下一步用新的條件繼續
  search，逐步縮小或調整範圍。search 只會查到 status=approved（已審核採用）的題
  目——這是唯一真正能被使用者拿去組卷的範圍，draft／rejected 題目不會出現，你不需
  要也不能指定 status。
- action="propose"：確定要推薦哪些題目給使用者時，把這些題目的 id 全部列進
  question_ids，並在 reply 用一段話說明你選了什麼、為什麼符合需求；這一步會結束
  整個回合，之後不會再有機會查詢或修改提案。
- action="reply"：不需要查詢或提案時（例如需要使用者先澄清需求、或找不到符合的題
  目），只用 reply 欄位回話；這一步也會結束整個回合。

每個回合最多 {max_steps} 步（含每一次 search）。如果一直 search 卻沒能在步數內
propose 或 reply，回合會被強制結束、你不會有機會再多做任何事——所以請在有把握時儘
早 propose 或 reply，不要無止盡地search 下去。

{category_tree}
使用者目前在畫面上已勾選、尚未確定採用的題目 id：{selected_question_ids}
"""

_NO_CATEGORIES_LINE = "目前題庫還沒有任何分類。\n"


def format_category_tree(subjects_with_topics: list[tuple[str, list[str]]]) -> str:
    """Render `[(subject_name, [topic_name, ...]), ...]` (from
    `backend.ingestion.classification.load_existing_categories`) as the
    system prompt's category-tree summary, so the agent knows which
    `category_id`-worthy subject/topic names actually exist before it tries
    a `category_id` filter. Distinct wording from `backend.ingestion.
    prompts.format_existing_categories` (that one asks the model to *reuse
    or create* a category during classification; this one is read-only
    context for search)."""
    if not subjects_with_topics:
        return _NO_CATEGORIES_LINE
    lines = ["題庫既有分類（科目 > 主題）："]
    for subject_name, topic_names in subjects_with_topics:
        lines.append(f"- {subject_name}")
        for topic_name in topic_names:
            lines.append(f"  - {topic_name}")
    lines.append("")
    return "\n".join(lines)


def build_system_prompt(
    *, max_steps: int, category_tree: list[tuple[str, list[str]]], selected_question_ids: list[int]
) -> str:
    """The one system message sent at the start of every step this turn."""
    return BANK_AGENT_SYSTEM_PROMPT_TEMPLATE.format(
        question_types=_QUESTION_TYPES_LINE,
        difficulty_vocab=_DIFFICULTY_VOCAB_LINE,
        max_steps=max_steps,
        category_tree=format_category_tree(category_tree),
        selected_question_ids=selected_question_ids or "（無）",
    )


@dataclass(frozen=True)
class SearchHitSummary:
    """One `action="search"` hit, trimmed down to what the agent needs to
    decide its next step (docs/question-bank.md — 命中題目的精簡摘要：id、
    題型、難度、分類路徑、題幹前 N 字)."""

    id: int
    type: str
    difficulty: str | None
    category_path: str
    stem_preview: str


def format_search_result(hits: list[SearchHitSummary], *, total_hits: int, limit: int) -> str:
    """The `user`-role message fed back after a search step. `total_hits` is
    the count actually matched (before the `limit` cap); `hits` is already
    capped to at most `limit` entries by the caller."""
    if not hits:
        return "搜尋結果：0 筆命中，這組條件在題庫裡找不到任何 approved 題目。"
    lines = [f"搜尋結果：命中 {total_hits} 筆（此處最多顯示 {limit} 筆）："]
    for hit in hits:
        difficulty_text = hit.difficulty or "未標註"
        lines.append(
            f"- id={hit.id} type={hit.type} difficulty={difficulty_text} "
            f"分類={hit.category_path} 題幹：{hit.stem_preview}"
        )
    return "\n".join(lines)


def step_cap_reply(max_steps: int) -> str:
    """The stored `reply` when the bounded loop hits `BANK_AGENT_MAX_STEPS`
    without the model ever choosing `propose`/`reply` — docs/question-bank.md
    「達步數上限則強制結束並在回覆中說明」: this must say so explicitly
    rather than silently truncating."""
    return (
        f"已經查詢了 {max_steps} 步，但還沒有找到足以推薦的明確結果，這回合先在這裡"
        "停下來。可以試著把需求說得更具體（例如指定科目、難度或關鍵字），我再重新找一次。"
    )
