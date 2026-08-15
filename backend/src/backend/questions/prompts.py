"""Every LLM prompt template used by question generation (docs/question-bank.md).

Kept in one dedicated module — never inlined in `generation.py` — so prompt
engineering changes are a one-file diff, matching
`backend.ingestion.prompts`'s convention.
"""

_DIFFICULTY_LINE_TEMPLATE = "難度：請出成「{difficulty}」難度的題目。\n"
_NO_DIFFICULTY_LINE = "難度：未指定，請依內容自行判斷合適難度。\n"


def _difficulty_line(difficulty: str | None) -> str:
    if difficulty:
        return _DIFFICULTY_LINE_TEMPLATE.format(difficulty=difficulty)
    return _NO_DIFFICULTY_LINE


# docs/question-bank.md 題幹自足原則 — appended into every one of the six
# per-type templates below so no type is exempt. `backend.questions.generation`
# additionally re-checks the actual generated text for the banned wording
# after the call, so this is belt (prompt) and suspenders (post-hoc check),
# not the only line of defense.
_SELF_CONTAINED_INSTRUCTION = """\
題幹自足原則（務必遵守）：這題離開教材後，沒看過原文的人也必須看得懂、答得出來：
- 題幹、選項、答案、解說都要自帶必要脈絡（主題名稱、關鍵事實、定義或情境描述），
  不能假設受測者手邊有教材。
- 禁止「根據教材內容」「根據上文／本文／課文」「文中提到」「教材指出」「依據內容」
  這類指涉來源文件的措辭，也不要用「如上所述」這種倒回去指涉前文的說法。
- 教材裡的內部編號（例如「Hands-on Lab 2」「第 5 章」「表 3」）不能直接寫進題幹，
  要換成該事物本身的內容描述，或改寫成不依賴內部編號的問法。
- 以上這些是出給你（出題者）的寫作規範，不是教材主題本身：不要出一題拿「題幹自足
  原則」「怎樣算指涉來源文件」這類規則本身當考題內容，題目考的必須是教材在教的
  知識，不是這些寫作規則。

範例（差 vs. 好）：
- 差：「根據教材內容，Hands-on Lab 2 的主要實驗目標為何？」
- 好：「在『量測本地端 API 延遲』這個實作練習中，主要的實驗目標為何？」
"""

COMPARISON_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是同一分類底下兩段內容相關但不相同的教材，請根據這兩段內容出一題
「比較題」，全部使用繁體中文：

- stem：比較題的題幹，要求學生比較兩個主體的異同。
- subject_a / subject_b：這一題要比較的兩個主體名稱（依內容判斷，通常各對應一段教材）。
- aspects：用來比較的面向清單（例如「場所」「原料與產物」），至少 1 個。
- model_answer.similarities：兩者的共同點清單。
- model_answer.differences：逐一面向列出差異，每項包含 aspect（面向名稱，必須取自
  aspects 清單）、a（該面向下主體 A 的內容）、b（該面向下主體 B 的內容）。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容 A：
---
{{content_a}}
---

教材內容 B：
---
{{content_b}}
---
"""

ANALOGY_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是一段教材內容，請從中找出一組概念類比關係，出一題「類比題」，
全部使用繁體中文。類比題的形式固定是「A 之於 B，猶如 C 之於＿＿」：

- a：類比關係中的第一個概念。
- b：a 對應的功能／性質／結果，與 a 構成第一組關係。
- c：類比關係中的第三個概念，與 a 屬於同類但不同主體。
- answer：c 之於＿＿的正確答案，必須與「a 之於 b」邏輯一致。
- options：若適合出成單選題，提供 3 到 5 個選項（含正確答案，且正確答案必須是其中之
  一）；若這組類比更適合出成純填空題，options 請回傳 null。
- explanation：簡短說明這組類比成立的理由（選填，不確定就回傳 null）。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容：
---
{{content}}
---
"""

SINGLE_CHOICE_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是一段教材內容，請根據內容出一題「單選題」，全部使用繁體中文：

- stem：題幹。
- options：4 個選項，其中恰好 1 個正確。
- answer_index：正確選項在 options 中的索引（從 0 開始）。
- explanation：簡短解釋為什麼該選項正確（選填，不確定就回傳 null）。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容：
---
{{content}}
---
"""

TRUE_FALSE_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是一段教材內容，請根據內容出一題「是非題」，全部使用繁體中文：

- stem：一句可以明確判斷對錯的敘述。
- answer：該敘述是否正確（true/false）。
- explanation：簡短解釋原因（選填，不確定就回傳 null）。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容：
---
{{content}}
---
"""

FILL_BLANK_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是一段教材內容，請根據內容出一題「填充題」，全部使用繁體中文：

- stem：題幹文字，每個要考的空格用 `____`（四個底線）標記，可以有 1 個以上空格。
- answers：依 stem 中 `____` 由左到右的順序，依序給出每個空格的正確答案；answers
  的項目數必須恰好等於 stem 中 `____` 的出現次數。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容：
---
{{content}}
---
"""

SHORT_ANSWER_PROMPT_TEMPLATE = f"""\
你是出題老師。以下是一段教材內容，請根據內容出一題「問答題」，全部使用繁體中文：

- stem：題幹，要求學生用文字說明或申論。
- model_answer：完整的參考答案。
- key_points：批改時應該檢核的得分要點清單，至少 1 項。

{_SELF_CONTAINED_INSTRUCTION}
{{difficulty_line}}
教材內容：
---
{{content}}
---
"""


def build_prompt(question_type: str, contents: list[str], difficulty: str | None) -> str:
    """The full user-message prompt for one generation call.

    `contents` is the unit's source chunk content(s), in `GenerationUnit`
    order — exactly 2 for `comparison`, exactly 1 for every other type.
    """
    difficulty_line = _difficulty_line(difficulty)
    if question_type == "comparison":
        if len(contents) != 2:
            raise ValueError(f"comparison prompt needs exactly 2 contents, got {len(contents)}")
        return COMPARISON_PROMPT_TEMPLATE.format(
            difficulty_line=difficulty_line, content_a=contents[0], content_b=contents[1]
        )

    if len(contents) != 1:
        raise ValueError(f"{question_type} prompt needs exactly 1 content, got {len(contents)}")
    content = contents[0]

    templates: dict[str, str] = {
        "analogy": ANALOGY_PROMPT_TEMPLATE,
        "single_choice": SINGLE_CHOICE_PROMPT_TEMPLATE,
        "true_false": TRUE_FALSE_PROMPT_TEMPLATE,
        "fill_blank": FILL_BLANK_PROMPT_TEMPLATE,
        "short_answer": SHORT_ANSWER_PROMPT_TEMPLATE,
    }
    try:
        template = templates[question_type]
    except KeyError:
        raise ValueError(f"unknown question type {question_type!r}") from None
    return template.format(difficulty_line=difficulty_line, content=content)
