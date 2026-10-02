"""Text extraction: the user's .docx -> markdown, tables included. This stands in for a
layout-aware extraction service. Its one hard-won guard: a 'succeeded' with no text is a
failure, and the run stops before any model sees it."""
from __future__ import annotations

import re
from dataclasses import dataclass

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

ITEM = re.compile(r"^Item (\d+) \u2014 ")
MD = re.compile(r"(\*\*|__|`|^#+\s*)")


@dataclass
class Extraction:
    status: str          # succeeded | failed
    markdown: str
    reason: str = ""


def _para_md(p: Paragraph) -> str:
    style = (p.style.name or "") if p.style is not None else ""
    text = "".join(f"**{r.text}**" if r.bold and r.text.strip() else r.text for r in p.runs)
    if style.startswith("Heading"):
        level = int(style.split()[-1]) if style.split()[-1].isdigit() else 1
        return "#" * level + " " + p.text
    return text


def to_markdown(path) -> str:
    doc = Document(path)
    out = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            out.append(_para_md(Paragraph(block, doc)))
        elif tag == "tbl":
            t = Table(block, doc)
            rows = [" | ".join(c.text for c in r.cells) for r in t.rows]
            out += [f"| {rows[0]} |", "|" + "---|" * len(t.rows[0].cells)] + [f"| {r} |" for r in rows[1:]]
    return "\n".join(out).strip() + "\n"


def extract(path, simulate_empty: bool = False) -> Extraction:
    md = "" if simulate_empty else to_markdown(path)
    if not md.strip():
        return Extraction("failed", "", "extraction reported success with no text")
    return Extraction("succeeded", md)


def strip_md(s: str) -> str:
    """Models copy anchors from the markdown they were shown ('## Heading', '**bold**').
    The file has no such characters, so strip them before matching."""
    return " ".join(MD.sub("", s).split())


def items(markdown: str) -> list[int]:
    return [int(m[1]) for line in markdown.splitlines() if (m := ITEM.match(strip_md(line)))]


def section_lines(markdown: str, heading: str) -> list[str]:
    out, inside = [], False
    for line in markdown.splitlines():
        if line.startswith("#"):
            inside = strip_md(line) == heading
            continue
        if inside and line.strip():
            out.append(line)
    return out
