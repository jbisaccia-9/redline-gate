"""The gate. It grades a finished job directory - every round's review, file, card and
decision, and the delivery - against the original file and the rule pack. It re-derives
everything it can rather than reading the loop's account of it.

  G1 source      extraction produced text; every round reviewed the ORIGINAL with today's date
  G2 anchored    every edit is either placed where its anchor occurs exactly once, or reported
  G3 cited       every edit cites a verified rule, or FEEDBACK when there were notes to act on
  G4 no new facts no number the document or the requester's notes didn't supply; none dropped
  G5 complete    every work item checked; every future 'completed' date caught by the backstop
  G6 original    reject every tracked change and you get the original back, tables and all
  G7 approval    short card; approved, shared and delivered file are one file; requester only
  G8 feedback    notes are acted on, and what earlier notes changed survives later rounds
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import extract, loop, redline, rules

RULES = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")
NAMES = {"G1": "source", "G2": "anchored", "G3": "cited", "G4": "no new facts", "G5": "complete",
         "G6": "original", "G7": "approval", "G8": "feedback"}
NUM = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class Verdict:
    job: str
    failures: dict[str, list[str]] = field(default_factory=dict)

    def fail(self, rule, why):
        self.failures.setdefault(rule, []).append(why)

    @property
    def passed(self):
        return not self.failures

    @property
    def rules_failed(self):
        return [r for r in RULES if r in self.failures]

    def to_json(self):
        return {"job": self.job, "passed": self.passed,
                "rules": {r: {"name": NAMES[r], "passed": r not in self.failures,
                              "failures": self.failures.get(r, [])} for r in RULES}}

    def line(self):
        if self.passed:
            return f"PASS     {self.job}"
        r = self.rules_failed[0]
        more = len(self.failures[r]) - 1
        return (f"REFUSED  {self.job:<26} {','.join(self.rules_failed)}  {self.failures[r][0]}"
                + (f" (+{more} more)" if more > 0 else ""))


def _facts(text: str) -> set[str]:
    return set(NUM.findall(redline.PLACEHOLDER.sub("", text)))


def _j(p: Path):
    return json.loads(p.read_text())


def grade(job_dir: Path) -> Verdict:
    job_dir = Path(job_dir)
    v = Verdict(job_dir.name)
    meta = _j(job_dir / "job.json")
    original = job_dir / meta["original"]
    md = (job_dir / "extracted.md").read_text()
    rounds = sorted(job_dir.glob("round-*"), key=lambda p: int(p.name.split("-")[1]))

    # G1 -------------------------------------------------------------------------------------
    if not md.strip():
        if rounds or (job_dir / "delivery").exists():
            v.fail("G1", "extraction produced no text, but the review ran anyway")
        return v
    if loop.sha(original) != meta["original_sha"]:
        v.fail("G1", "the stored original no longer matches its recorded hash")
    real_md = extract.to_markdown(original)
    if md != real_md:
        v.fail("G1", "the text the model reviewed is not the text of the original file")

    pack = rules.load(meta["rule_pack"])
    verified = {k for k, r in pack.items() if r.verified}
    texts = [t for kind, t in redline.view(original, "reject") if kind == "p"]
    item_numbers = extract.items(md)
    doc_facts = _facts(md)
    notes_so_far: list[str] = []
    prev_feedback_anchors: set[str] = set()
    last = None

    for rd in rounds:
        n = int(rd.name.split("-")[1])
        review, card, decision = _j(rd / "review.json"), _j(rd / "card.json"), _j(rd / "decision.json")
        placements = _j(rd / "placements.json")
        prompt = _j(rd / "prompt.json")
        edits = review["edits"]
        out_file = rd / Path(card["file"]).name

        if review.get("source_sha") != meta["original_sha"]:
            v.fail("G1", f"round {n}: reviewed something other than the original file")
        if prompt.get("today") != review.get("today") or not prompt.get("today"):
            v.fail("G1", f"round {n}: the model was not given today's date")

        # G2 ---------------------------------------------------------------------------------
        if sorted(p["index"] for p in placements) != list(range(len(edits))):
            v.fail("G2", f"round {n}: {len(edits)} edits but {len(placements)} placement results")
        for p in placements:
            if p["index"] >= len(edits):
                continue
            e = edits[p["index"]]
            hits = redline.locate(texts, e["anchor"])
            words = len(extract.strip_md(e["anchor"]).split())
            if p["placed"] and len(hits) != 1:
                v.fail("G2", f"round {n} edit {p['index'] + 1}: applied, but its anchor occurs "
                             f"{len(hits)} times in the original")
            if p["placed"] and not 5 <= words <= 40:
                v.fail("G2", f"round {n} edit {p['index'] + 1}: anchor is {words} words (5-40)")
        unplaced = sum(not p["placed"] for p in placements)
        if card["check_by_hand"] != unplaced:
            v.fail("G2", f"round {n}: {unplaced} unplaced edits but the card reports {card['check_by_hand']}")

        # G3 ---------------------------------------------------------------------------------
        for k, e in enumerate(edits, 1):
            if e["rule"] == "FEEDBACK":
                if not notes_so_far:
                    v.fail("G3", f"round {n} edit {k}: tagged FEEDBACK with no notes to act on")
            elif e["rule"] not in verified:
                why = "unverified - it may raise a to-do, not justify an edit" if e["rule"] in pack else "not in the rule pack"
                v.fail("G3", f"round {n} edit {k}: cites {e['rule']!r}, {why}")
            if len(e.get("reason", "").split()) > 15:
                v.fail("G3", f"round {n} edit {k}: reason longer than fifteen words")

        # G4 ---------------------------------------------------------------------------------
        allowed = doc_facts | set().union(*(_facts(x) for x in notes_so_far)) if notes_so_far else doc_facts
        for k, e in enumerate(edits, 1):
            new = _facts(e["text"]) - allowed
            if new:
                v.fail("G4", f"round {n} edit {k}: introduces {sorted(new)}, which neither the document "
                             f"nor the requester's notes contain")
            if e["op"] in ("replace", "replace_block") and not redline.PLACEHOLDER.search(e["text"]):
                dropped = _facts(extract.strip_md(e["anchor"])) - _facts(e["text"])
                if dropped:
                    v.fail("G4", f"round {n} edit {k}: removes {sorted(dropped)} without a placeholder")

        # G5 ---------------------------------------------------------------------------------
        checked = {int(m[1]) for m in re.finditer(r"^\d+\. Item (\d+)\b", review["item_checks"], re.M)}
        missing = [i for i in item_numbers if i not in checked]
        if missing:
            v.fail("G5", f"round {n}: items {missing} were never checked")
        for want in loop.backstop(md, dt.date.fromisoformat(prompt["today"])):
            if want not in review.get("backstop", []):
                v.fail("G5", f"round {n}: backstop missed: {want}")

        # G6 ---------------------------------------------------------------------------------
        if redline.view(out_file, "reject") != redline.view(original, "reject"):
            v.fail("G6", f"round {n}: rejecting every tracked change does not give back the original")

        # G7 ---------------------------------------------------------------------------------
        if len(card["summary"]) > 5 or any(len(s.split()) > 12 for s in card["summary"]):
            v.fail("G7", f"round {n}: card summary over five lines or twelve words a line")
        if card["file_sha"] != loop.sha(out_file):
            v.fail("G7", f"round {n}: the card's file is not the file this round produced")
        if decision.get("by") != meta["requester"]:
            v.fail("G7", f"round {n}: decided by {decision.get('by')!r}, not the requester")

        # G8 ---------------------------------------------------------------------------------
        fb = {extract.strip_md(e["anchor"]) for e in edits if e["rule"] == "FEEDBACK"}
        if notes_so_far and n > 1:
            if not review.get("from_feedback") or not fb:
                v.fail("G8", f"round {n}: there were notes, but no change was made from them")
            lost = prev_feedback_anchors - fb
            if lost:
                v.fail("G8", f"round {n}: {len(lost)} change(s) made from earlier notes were dropped")
        prev_feedback_anchors = fb or prev_feedback_anchors
        if decision.get("notes"):
            notes_so_far.append(decision["notes"])
        last = (n, card, decision, out_file)

    # G7: delivery ---------------------------------------------------------------------------
    share = _j(job_dir / "share.json") if (job_dir / "share.json").exists() else {"viewers": []}
    if share["viewers"] != [meta["requester"]]:
        v.fail("G7", "the reviewed file is shared with someone other than the requester")
    dl = job_dir / "delivery" / "email.json"
    if dl.exists():
        email = _j(dl)
        if last is None or last[2]["decision"] != "approve":
            v.fail("G7", "delivered without an approval")
        else:
            n, card, _, out_file = last
            att = email["attachments"][0]["sha256"] if email["attachments"] else None
            if not (att == card["file_sha"] == loop.sha(out_file) == loop.sha(job_dir / card["file"])):
                v.fail("G7", "the delivered file is not the file that was approved")
            if email["approved_round"] != n:
                v.fail("G7", "delivery names a different round from the approval")
        if email["to"] != [meta["requester"]] or email.get("cc"):
            v.fail("G7", "delivery addressed to someone other than the requester")
    return v


def check_dir(root: Path) -> list[Verdict]:
    out = []
    for meta in sorted(Path(root).glob("*/job.json")):
        verdict = grade(meta.parent)
        (meta.parent / "grading.json").write_text(json.dumps(verdict.to_json(), indent=1) + "\n")
        out.append(verdict)
    return out
