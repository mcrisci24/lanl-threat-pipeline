"""
scripts/generate_writeup_pdf.py
===============================

Render docs/WRITEUP.md to a single-page PDF at the repo root.

Why this exists
---------------
The project specification requires a ONE-PAGE PDF write-up at the repo root.
Editing prose in Markdown is far easier than maintaining LaTeX or Word, so
we keep the source of truth in `docs/WRITEUP.md` and render the PDF from
that. This script tries `reportlab` (pure-Python) so it works on any laptop
without external system dependencies.

Usage
-----
    python scripts/generate_writeup_pdf.py

Output
------
    WRITEUP.pdf  at the repo root  (single page, 11pt+, ~1 inch margins)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "docs" / "WRITEUP.md"
OUT = REPO_ROOT / "WRITEUP.pdf"


def _strip_markdown(line: str) -> str:
    """Convert a tiny subset of Markdown into reportlab Paragraph HTML.

    reportlab's Paragraph supports a small HTML-like markup. We use:
      <b>...</b>                  for bold
      <font face="Courier">...</font>   for inline code

    This preserves the structure of the write-up - bold numbered step
    labels in the architecture section stand out, and inline code
    (column names, paths) renders in a monospace font. We HTML-escape
    the raw text first so any literal '<', '>', '&' in the source
    don't conflict with our injected tags.
    """
    # 1) Escape HTML-special characters so they survive intact.
    line = (
        line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    # 2) Bold (**text**) -> <b>text</b>
    line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
    # 3) Inline code (`text`) -> monospace
    line = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', line)
    # 4) Markdown links [text](url) -> just the text
    line = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", line)
    return line


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source missing: {SRC}", file=sys.stderr)
        return 1

    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer
        )
    except ImportError:
        print(
            "ERROR: reportlab is not installed. Install it with:\n"
            "  pip install reportlab\n"
            "and re-run this script.",
            file=sys.stderr,
        )
        return 1

    # --- Tight single-page layout -----------------------------------
    # Body 10pt is the minimum the spec allows. Leading is set tightly to
    # 11.5pt so the longer end-to-end description in section 3 still fits
    # without crossing the second page.
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=10, leading=11.5, spaceAfter=2,
    )
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=13, leading=15, spaceAfter=3, spaceBefore=1,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11, leading=13, spaceAfter=1, spaceBefore=4,
    )

    # --- Parse the markdown ----------------------------------------
    lines = SRC.read_text(encoding="utf-8").splitlines()
    flowables = []

    paragraph_buffer: list[str] = []

    def _flush_paragraph():
        if not paragraph_buffer:
            return
        text = " ".join(paragraph_buffer).strip()
        if text:
            flowables.append(Paragraph(_strip_markdown(text), body))
        paragraph_buffer.clear()

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("# "):
            _flush_paragraph()
            flowables.append(Paragraph(_strip_markdown(line[2:]), h1))
        elif line.startswith("## "):
            _flush_paragraph()
            flowables.append(Paragraph(_strip_markdown(line[3:]), h2))
        elif not line.strip():
            _flush_paragraph()
            flowables.append(Spacer(1, 2))
        else:
            paragraph_buffer.append(line)

    _flush_paragraph()

    # --- Render ----------------------------------------------------
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="LANL Threat Prediction - Project 2 Write-Up",
        author="LANL Threat Prediction Team",
    )
    doc.build(flowables)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
