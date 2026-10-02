"""Measure one lesson: models copy anchors out of the markdown they were shown."""
from __future__ import annotations

import json
from pathlib import Path

from . import redline


def report(data: Path) -> str:
    data = Path(data)
    jobs = json.loads((data / "jobs.json").read_text())
    total = marked = raw_fail = stripped_fail = 0
    for job, spec in jobs.items():
        texts = [p for _, p in redline.view(data / "drafts" / spec["file"], "reject")]
        for f in sorted((data / "recorded" / job).glob("review-*.json")):
            for e in json.loads(f.read_text())["edits"]:
                total += 1
                marked += any(m in e["anchor"] for m in ("**", "__", "`", "# "))
                raw_fail += len(redline.locate(texts, e["anchor"], strip=False)) != 1
                stripped_fail += len(redline.locate(texts, e["anchor"], strip=True)) != 1
    return (f"edits across all recorded rounds          {total}\n"
            f"anchors carrying markdown from the prompt {marked}\n"
            f"unplaceable if matched as-is             {raw_fail}\n"
            f"unplaceable after stripping markdown     {stripped_fail}   "
            f"(the remaining one matches two places and is reported, not forced)")
