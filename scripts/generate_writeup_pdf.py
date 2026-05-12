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
    """Very small markdown-to-text converter for the bits we use in WRITEUP.md."""
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)   # bold
    line = re.sub(r"`(.+?)`", r"\1", line)         # inline code
    line = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", line)  # links -> just the text
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
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body", parent=styles["BodyText"],
        fontName="Helvetica", fontSize=10, leading=12, spaceAfter=4,
    )
    h1 = ParagraphStyle(
        "h1", parent=styles["Heading1"],
        fontName="Helvetica-Bold", fontSize=13, leading=15, spaceAfter=4, spaceBefore=2,
    )
    h2 = ParagraphStyle(
        "h2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11, leading=13, spaceAfter=2, spaceBefore=4,
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
