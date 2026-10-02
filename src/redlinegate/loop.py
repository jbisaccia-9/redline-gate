"""The loop, one job at a time:

  intake -> extract (guarded) -> load rule pack -> review (model, JSON only) -> deterministic
  backstop -> apply edits to the ORIGINAL file -> share with the requester only -> approval card
  -> decline with notes: revise on the original with notes + previous review, same file, same link
  -> approve: deliver by email with the final file attached.

The model reads and writes JSON. Everything else - extraction, finding text, editing the file,
the date backstop, saving, sharing, sending and approving - is code or a person."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path

from . import extract, redline, rules

ROUND_LIMIT, DAY_LIMIT = 100, 30
CONTRACT = {"item_checks", "edits", "change_log", "todo", "from_feedback", "summary"}
DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RecordedReviewer:
    """Stands in for the model call. The prompt it would receive is built and saved anyway
    (text, category, rule pack, today's date, notes, previous review) so it can be audited."""
    def __init__(self, recorded_dir: Path):
        self.dir = Path(recorded_dir)

    def review(self, prompt: dict, rnd: int) -> dict:
        return json.loads((self.dir / f"review-{rnd}.json").read_text())


def backstop(markdown: str, today: dt.date) -> list[str]:
    """What a model with no clock misses: an inspection 'passed' on a date that hasn't happened."""
    out = []
    for line in extract.section_lines(markdown, "Inspections completed"):
        for d in DATE.findall(line):
            if dt.date.fromisoformat(d) > today:
                out.append(f"HIGH - Inspections completed - {d} is after today's date; check it (BACKSTOP)")
    return out


def run_job(root: Path, job: str, out_root: Path, simulate_empty: bool = False) -> dict:
    root, out = Path(root), Path(out_root) / job
    spec = json.loads((root / "jobs.json").read_text())[job]
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    original = out / "original" / spec["file"]
    original.parent.mkdir()
    shutil.copy(root / "drafts" / spec["file"], original)
    pack_path = root / "rules" / f"{spec['category']}.txt"
    ex = extract.extract(original, simulate_empty)
    meta = {"job": job, "category": spec["category"], "requester": spec["requester"],
            "original": original.relative_to(out).as_posix(), "original_sha": sha(original),
            "extraction": {"status": ex.status, "reason": ex.reason, "chars": len(ex.markdown)},
            "rule_pack": pack_path.as_posix(), "rounds": 0, "status": "running"}
    (out / "extracted.md").write_text(ex.markdown)
    if ex.status != "succeeded":
        meta["status"] = "failed"
        (out / "job.json").write_text(json.dumps(meta, indent=1) + "\n")
        return meta

    pack = rules.load(pack_path)
    reviewer = RecordedReviewer(root / "recorded" / job)
    shared = out / "shared" / spec["file"].replace(".docx", "-reviewed.docx")   # one file, one link
    shared.parent.mkdir()
    previous, notes_so_far = None, []
    for rnd, day in enumerate(spec["dates"], 1):
        if rnd > ROUND_LIMIT or (dt.date.fromisoformat(day) - dt.date.fromisoformat(spec["dates"][0])).days > DAY_LIMIT:
            meta["status"] = "expired"
            break
        rd = out / f"round-{rnd}"
        rd.mkdir()
        prompt = {"category": spec["category"], "today": day, "text": ex.markdown,
                  "rule_pack": pack_path.read_text(), "notes": notes_so_far[-1] if notes_so_far else "",
                  "previous_review": previous}
        (rd / "prompt.json").write_text(json.dumps(prompt, indent=1) + "\n")
        review = reviewer.review(prompt, rnd)
        missing = CONTRACT - set(review)
        if missing:
            meta["status"] = f"failed: review missing {sorted(missing)}"
            break
        review["source_sha"] = meta["original_sha"]           # always the original, never last round's output
        review["today"] = day
        review["backstop"] = backstop(ex.markdown, dt.date.fromisoformat(day))
        (rd / "review.json").write_text(json.dumps(review, indent=1) + "\n")

        placements = redline.apply(original, review["edits"], rd / shared.name, f"{day}T00:00:00Z")
        shutil.copy(rd / shared.name, shared)                  # overwrite the same file at the same link
        (rd / "placements.json").write_text(json.dumps([p.__dict__ for p in placements], indent=1) + "\n")
        (out / "share.json").write_text(json.dumps({"file": shared.relative_to(out).as_posix(),
                                                    "viewers": [spec["requester"]]}, indent=1) + "\n")
        todo = [t.split(". ", 1)[-1] for t in review["todo"].splitlines() if t.strip()] + review["backstop"]
        unplaced = [review["edits"][p.index] for p in placements if not p.placed]
        card = {"job": job, "round": rnd, "summary": review["summary"].splitlines(),
                "todo_counts": {lvl: sum(t.startswith(lvl) for t in todo) for lvl in ("HIGH", "MEDIUM")},
                "check_by_hand": len(unplaced), "file": shared.relative_to(out).as_posix(),
                "file_sha": sha(rd / shared.name), "actions": ["Approve", "Decline"]}
        (rd / "card.json").write_text(json.dumps(card, indent=1) + "\n")

        decision = json.loads((root / "recorded" / job / f"decision-{rnd}.json").read_text())
        (rd / "decision.json").write_text(json.dumps(decision, indent=1) + "\n")
        meta["rounds"] = rnd
        if decision["decision"] == "approve":
            deliver(out, spec, review, card, todo, unplaced, notes_so_far, rd / shared.name)
            meta["status"] = "delivered"
            break
        if decision["notes"]:
            notes_so_far.append(decision["notes"])
        previous = review
    (out / "job.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def deliver(out: Path, spec: dict, review: dict, card: dict, todo: list[str], unplaced: list[dict],
            notes: list[str], final: Path) -> None:
    """The model wrote the words; code lays them out in the house template."""
    dd = out / "delivery"
    dd.mkdir()
    shutil.copy(final, dd / final.name)
    hi = card["todo_counts"]["HIGH"]
    body = "\n\n".join([
        f"Your reviewed narrative is attached: {len(review['edits']) - len(unplaced)} tracked changes, "
        f"{hi} high-priority to-dos, {len(unplaced)} to check by hand.",
        "Top issues:\n" + "\n".join(f"- {s}" for s in review["summary"].splitlines()),
        "Your notes:\n" + ("\n".join(f"- {n}" for n in notes) or "- none"),
        "Changes made from your notes:\n" + (review["from_feedback"] or "none"),
        "To-do:\n" + "\n".join(f"- {t}" for t in todo),
        "Item checks:\n" + review["item_checks"],
        "Every change made:\n" + review["change_log"],
        "Check by hand (could not be placed in your file):\n"
        + ("\n".join(f"- {u['heading']}: {u['text']} ({u['rule']})" for u in unplaced) or "- none"),
    ])
    (dd / "email.json").write_text(json.dumps({
        "to": [spec["requester"]], "cc": [], "subject": "Your reviewed permit narrative is ready to submit",
        "body": body, "attachments": [{"name": final.name, "sha256": sha(dd / final.name)}],
        "approved_round": card["round"]}, indent=1) + "\n")
