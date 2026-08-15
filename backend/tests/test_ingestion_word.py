"""`backend.ingestion.word` — `.docx` -> Markdown extraction (mammoth + markdownify).

Builds a minimal but real, valid `.docx` (a zip of the bare-minimum OOXML
parts) by hand rather than mocking mammoth — the actual mammoth/markdownify
conversion is exercised for real, only the input file is synthetic.
"""

import io
import zipfile
from pathlib import Path

from backend.ingestion.word import extract_word_markdown

_RELS_CONTENT_TYPE = "application/vnd.openxmlformats-package.relationships+xml"
_MAIN_DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_OFFICE_DOCUMENT_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)

_CONTENT_TYPES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="{_RELS_CONTENT_TYPE}"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="{_MAIN_DOCUMENT_CONTENT_TYPE}"/>
</Types>"""

_PACKAGE_RELS = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{_OFFICE_DOCUMENT_REL_TYPE}" Target="word/document.xml"/>
</Relationships>"""

_DOCUMENT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>{body}</w:body>
</w:document>"""


def _heading_xml(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
        f"<w:r><w:t>{text}</w:t></w:r></w:p>"
    )


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _build_docx(body_xml: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("_rels/.rels", _PACKAGE_RELS)
        archive.writestr("word/document.xml", _DOCUMENT_TEMPLATE.format(body=body_xml))
    return buffer.getvalue()


def test_extract_word_markdown_preserves_heading_and_paragraph(tmp_path: Path) -> None:
    body = _heading_xml("光合作用") + _paragraph_xml("光合作用發生在葉綠體，屬於合成代謝。")
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(_build_docx(body))

    markdown = extract_word_markdown(docx_path)

    assert markdown.startswith("# 光合作用")
    assert "光合作用發生在葉綠體，屬於合成代謝。" in markdown


def test_extract_word_markdown_preserves_multiple_paragraphs_in_order(tmp_path: Path) -> None:
    body = (
        _heading_xml("第一節")
        + _paragraph_xml("第一段文字。")
        + _heading_xml("第二節")
        + _paragraph_xml("第二段文字。")
    )
    docx_path = tmp_path / "sample.docx"
    docx_path.write_bytes(_build_docx(body))

    markdown = extract_word_markdown(docx_path)

    assert markdown.index("第一節") < markdown.index("第一段文字") < markdown.index("第二節")
    assert markdown.index("第二節") < markdown.index("第二段文字")
