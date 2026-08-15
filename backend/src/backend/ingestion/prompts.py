"""Every LLM prompt template used by the ingestion pipeline (docs/ingestion.md).

Kept in one dedicated module — never inlined in `pipeline.py`/`vision.py` —
so prompt engineering changes are a one-file diff and never scattered across
the business logic that calls them.
"""

VISION_PAGE_PROMPT = """\
你是文件數位化助手。這是一份掃描文件或圖片的其中一頁，內容多為繁體中文。

請把這一頁的內容完整轉錄成 Markdown：
- 依原始版面保留標題階層（# / ## / ###）、清單、表格與段落結構。
- 忠實轉錄文字內容，不得摘要、不得省略、不得改寫語意。
- 若頁面中有圖表、圖片、圖示或示意圖，不要嘗試描述其視覺內容，改在該位置插入
  佔位符 `![fig-1]`、`![fig-2]`……（依出現順序編號），並在 `figures` 陣列中回報
  對應的 bounding box 與簡短說明文字（caption，用繁體中文，說明圖表主題）。
- 純文字裝飾線、頁碼、頁首頁尾等版面雜訊不視為圖表，不需要建立佔位符。
- 若整頁沒有任何圖表，`figures` 回傳空陣列即可。

bbox 座標規則（務必遵守）：
- 陣列格式固定為 `[ymin, xmin, ymax, xmax]`（先 y 後 x，先 min 後 max）。
- 每個數值為 0-1000 的整數，代表在整張圖片高度／寬度上的正規化位置
  （0 = 最上/最左，1000 = 最下/最右），與圖片實際像素大小無關。
"""

SUMMARY_PROMPT_TEMPLATE = """\
以下是從網頁擷取的正文 Markdown 內容。請用繁體中文寫一段簡短摘要（三到五句話），
只用於文件列表與分類顯示，不需要涵蓋所有細節。

正文內容：
---
{content}
---
"""

CLASSIFICATION_PROMPT_TEMPLATE = """\
以下是一段文件內容（chunk）。請判斷它的分類資訊，全部使用繁體中文：

- subject：科目（例如「生物」「物理」「歷史」），取最適合的單一上層科目名稱。
- topic：主題（例如「光合作用」「牛頓運動定律」），科目底下更具體的子分類。
- difficulty：難度，只能是「簡單」「中等」「困難」三者之一。
- tags：3 到 6 個簡短關鍵字標籤，用於之後出題時的檢索。

{existing_categories}
內容：
---
{content}
---
"""

_NO_EXISTING_CATEGORIES_NOTE = "目前尚無既有分類，subject／topic 可自由命名。\n"


def format_existing_categories(subjects_with_topics: list[tuple[str, list[str]]]) -> str:
    """Render `[(subject_name, [existing_topic_name, ...]), ...]` as the
    classification prompt's "既有分類清單" block (docs/ingestion.md — 分類
    prompt 必須帶入既有科目清單，與該科目下既有主題，引導模型優先重用既有分類、
    避免同義科目碎裂，如「資訊工程／資訊科技」並存；只有真的不合適才建新分類).

    An empty list (a brand-new instance with no categories yet) renders a
    short "nothing exists yet" note instead of an empty bullet list, so the
    "reuse an existing name" instruction never dangles with nothing to
    reuse.
    """
    if not subjects_with_topics:
        return _NO_EXISTING_CATEGORIES_NOTE
    lines = [
        "既有科目與主題清單（若語意相符，請直接重用清單中的既有名稱，不要為同一"
        "個科目/主題另外新造同義詞；只有真的沒有合適分類時才建立新名稱）：",
    ]
    for subject_name, topic_names in subjects_with_topics:
        lines.append(f"- {subject_name}")
        for topic_name in topic_names:
            lines.append(f"  - {topic_name}")
    lines.append("")
    return "\n".join(lines)


def build_classification_prompt(
    content: str, subjects_with_topics: list[tuple[str, list[str]]]
) -> str:
    """The full `classify_chunk` prompt: `CLASSIFICATION_PROMPT_TEMPLATE`
    with the existing-categories block and the chunk content filled in."""
    return CLASSIFICATION_PROMPT_TEMPLATE.format(
        existing_categories=format_existing_categories(subjects_with_topics),
        content=content,
    )
