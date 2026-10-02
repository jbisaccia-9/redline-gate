"""Rule packs: one plain-text file per category. Every rule has a stable ID, a source and a
status. Verified rules may justify an edit. Unverified rules may only raise a to-do.
Priority rules are the ones learned from real past rejections."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    rule_id: str
    verified: bool
    priority: bool
    source: str
    text: str


def load(path: Path) -> dict[str, Rule]:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        rid, status, prio, source, text = [x.strip() for x in line.split("|", 4)]
        out[rid] = Rule(rid, status == "verified", prio == "priority", source.removeprefix("source: "), text)
    return out
