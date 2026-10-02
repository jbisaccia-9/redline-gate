"""Deterministic synthetic world. The City of Larkmoor Building Division, its rule packs, every
applicant, parcel, business and address below are fictional.

Three permit narratives go through review. The model's reviews are RECORDED here as the
JSON a model returned, so the loop and the gate run offline. The deck job takes three rounds:
declined with notes twice, then approved.
"""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document

RULES = {
    "deck": [
        "DECK-SITE-001 | verified | priority | source: Larkmoor residential code 4.2 | State the distance from the deck to the nearest property line, in feet.",
        "DECK-STR-002 | verified | | source: Larkmoor residential code 5.1 | Give the footing depth for each footing; the minimum is 30 inches below grade.",
        "DECK-STR-003 | verified | priority | source: Larkmoor residential code 5.4 | Describe how the ledger is fastened to the house and how it is flashed.",
        "DECK-SAFE-004 | verified | | source: Larkmoor residential code 6.0 | State guard height wherever the walking surface is more than 30 inches above grade.",
        "DECK-SCH-005 | verified | | source: division checklist, rev C | Dates in the narrative must match the schedule table.",
        "DECK-DOC-006 | unverified | | source: reviewer email, spring | Attach a photo of the existing ledger location.",
    ],
    "solar": [
        "SOL-FIRE-001 | verified | priority | source: Larkmoor fire code 12.3 | State the width of the roof access pathway, in inches.",
        "SOL-ELEC-002 | verified | | source: division checklist, rev B | Give the array size in kW and the module count.",
        "SOL-STR-003 | verified | | source: Larkmoor residential code 7.2 | State the attachment spacing and what the rails attach to.",
        "SOL-DISC-004 | verified | priority | source: Larkmoor electrical code 9.1 | State where the rapid shutdown switch is located.",
        "SOL-DOC-005 | unverified | | source: counter staff, verbal | Give the roof plan sheet number.",
    ],
    "sign": [
        "SIGN-SIZE-001 | verified | | source: Larkmoor sign code 3.1 | State the area of each sign, in square feet.",
        "SIGN-CLR-002 | verified | priority | source: Larkmoor sign code 3.4 | Projecting signs must state clearance above the sidewalk; the minimum is 8 feet.",
        "SIGN-LUM-003 | verified | | source: Larkmoor sign code 4.0 | State illumination hours and whether a timer is used.",
        "SIGN-DOC-004 | unverified | | source: reviewer email, summer | Include a photo of the facade.",
    ],
}

D = "\u2014"   # the drafts use an em dash after "Item N"


def _draft(path: Path, title: str, intro: str, items: list[tuple[str, str]], sections: list[tuple[str, list[str]]],
           schedule: list[tuple[str, str, str]]):
    doc = Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph(intro)
    doc.add_heading("Work items", level=2)
    for head, rest in items:
        p = doc.add_paragraph()
        p.add_run(head).bold = True
        p.add_run(rest)
    for heading, paras in sections:
        doc.add_heading(heading, level=2)
        for t in paras:
            doc.add_paragraph(t)
    doc.add_heading("Schedule", level=2)
    t = doc.add_table(rows=1, cols=3)
    for c, h in zip(t.rows[0].cells, ("Item", "Start", "Finish")):
        c.text = h
    for row in schedule:
        cells = t.add_row().cells
        for c, v in zip(cells, row):
            c.text = v
    doc.save(path)


JOBS = {
    "deck-ashcombe": {
        "category": "deck", "requester": "wren.ashcombe@mailbox.example", "file": "deck-narrative.docx",
        "dates": ["2026-10-05", "2026-10-06", "2026-10-07"],
    },
    "solar-valcourt": {
        "category": "solar", "requester": "idris.valcourt@mailbox.example", "file": "solar-narrative.docx",
        "dates": ["2026-10-05"],
    },
    "sign-lindqvist": {
        "category": "sign", "requester": "petra.lm@mailbox.example", "file": "sign-narrative.docx",
        "dates": ["2026-10-06"],
    },
}

DECK_SETBACK = "the setback from the rear property line is adequate"
DECK_ITEM1_MD = (f"**Item 1 {D} Ledger-attached deck**, 14 ft by 12 ft, pressure-treated framing "
                 f"on four footings 24 inches deep.")


def _deck_review(rnd: int) -> dict:
    checks = (f"1. Item 1 - setback: MISSING (DECK-SITE-001) - footing depth: BELOW MINIMUM, 24 in (DECK-STR-002) - "
              f"ledger: {'MISSING' if rnd == 1 else 'FROM FEEDBACK'} (DECK-STR-003)\n"
              "2. Item 2 - risers: OK - dates: MISMATCH, narrative vs table (DECK-SCH-005)\n"
              "3. Item 3 - guard height: OK (DECK-SAFE-004)")
    todo = ["1. HIGH - Work items - footing depth 24 in is under the 30 in minimum; revise or explain (DECK-STR-002)",
            "2. MEDIUM - Schedule - framing start in the narrative differs from the table (DECK-SCH-005)",
            "3. MEDIUM - Attachments - add a photo of the ledger location (DECK-DOC-006)"]
    if rnd == 1:
        edits = [
            {"op": "replace", "anchor": DECK_SETBACK,
             "text": "the setback from the rear property line is [NEEDS INPUT: distance in feet - DECK-SITE-001]",
             "heading": "Site", "rule": "DECK-SITE-001", "reason": "Setback must be stated in feet"},
            {"op": "insert_after", "anchor": DECK_ITEM1_MD,
             "text": "The ledger is fastened with [NEEDS INPUT: fastener and spacing - DECK-STR-003] and flashed with "
                     "[NEEDS INPUT: flashing detail - DECK-STR-003].",
             "heading": "Work items", "rule": "DECK-STR-003", "reason": "Ledger fastening and flashing not described"},
        ]
        fb, summary = "", ["Setback and ledger details are missing", "Footing depth is under the minimum",
                           "Narrative and schedule dates disagree", "One future inspection date flagged"]
    elif rnd == 2:
        edits = [
            {"op": "replace", "anchor": DECK_SETBACK, "text": "the setback from the rear property line is 7 feet",
             "heading": "Site", "rule": "FEEDBACK", "reason": "Setback supplied by the applicant"},
            {"op": "insert_after", "anchor": DECK_ITEM1_MD,
             "text": "The ledger is fastened with half-inch lag screws at 16 inches on center and flashed with "
                     "[NEEDS INPUT: flashing detail - DECK-STR-003].",
             "heading": "Work items", "rule": "FEEDBACK", "reason": "Fastening supplied by the applicant"},
        ]
        fb = "Setback set to 7 feet; ledger fastening added from your notes."
        summary = ["Setback and fastening added from your notes", "Flashing detail still needed",
                   "Footing depth is still under the minimum"]
    else:
        edits = [
            {"op": "replace", "anchor": DECK_SETBACK, "text": "the setback from the rear property line is 7 feet",
             "heading": "Site", "rule": "FEEDBACK", "reason": "Setback supplied by the applicant"},
            {"op": "insert_after", "anchor": DECK_ITEM1_MD,
             "text": "The ledger is fastened with half-inch lag screws at 16 inches on center and flashed with "
                     "self-adhered membrane under a Z-flashing.",
             "heading": "Work items", "rule": "FEEDBACK", "reason": "Flashing supplied by the applicant"},
        ]
        fb = "Kept setback and fastening; added flashing; schedule left as you asked."
        summary = ["All requested details are now in", "Footing depth is still under the minimum",
                   "Schedule left unchanged at your request"]
        todo = [t for t in todo if "DECK-SCH-005" not in t] + [
            "3. MEDIUM - Schedule - left as is at the applicant's request (DECK-SCH-005)"]
    log = [f"{i + 1}. {e['heading']} - was: \"{e['anchor'][:40]}\" - now: \"{e['text'][:40]}\" ({e['rule']})"
           for i, e in enumerate(edits)]
    return {"item_checks": checks, "edits": edits, "change_log": "\n".join(log), "todo": "\n".join(todo),
            "from_feedback": fb, "summary": "\n".join(summary)}


def _solar_review() -> dict:
    return {
        "item_checks": "1. Item 1 - size and count: OK (SOL-ELEC-002)\n2. Item 2 - attachment: OK (SOL-STR-003)\n"
                       "3. Item 3 - disconnect: location given, rapid shutdown MISSING (SOL-DISC-004)",
        "edits": [
            {"op": "replace", "anchor": "A pathway is provided along the ridge.",
             "text": "A [NEEDS INPUT: width in inches - SOL-FIRE-001] pathway is provided along the ridge.",
             "heading": "Fire access", "rule": "SOL-FIRE-001", "reason": "Pathway width must be stated"},
            {"op": "insert_after", "anchor": "See the attached roof plan for module layout.",
             "text": "Rapid shutdown switch: [NEEDS INPUT: location - SOL-DISC-004].",
             "heading": "Work items", "rule": "SOL-DISC-004", "reason": "Rapid shutdown location missing"},
        ],
        "change_log": "1. Fire access - pathway width placeholder added (SOL-FIRE-001)\n"
                      "2. Work items - rapid shutdown placeholder (SOL-DISC-004)",
        "todo": "1. MEDIUM - Attachments - give the roof plan sheet number (SOL-DOC-005)",
        "from_feedback": "",
        "summary": "Pathway width is missing\nRapid shutdown location is missing\nEverything else matches the checklist",
    }


def _sign_review() -> dict:
    return {
        "item_checks": "1. Item 1 - area: OK (SIGN-SIZE-001)\n2. Item 2 - area: OK - clearance: OK, 9 ft (SIGN-CLR-002)",
        "edits": [
            {"op": "replace", "anchor": "The wall sign is internally lit.",
             "text": "The wall sign is internally lit, on a timer set to [NEEDS INPUT: hours of operation - SIGN-LUM-003].",
             "heading": "Illumination", "rule": "SIGN-LUM-003", "reason": "Illumination hours and timer not stated"},
        ],
        "change_log": "1. Illumination - timer and hours placeholder (SIGN-LUM-003)",
        "todo": "1. MEDIUM - Attachments - include a facade photo (SIGN-DOC-004)",
        "from_feedback": "",
        "summary": "Illumination hours are missing\nSizes and clearance meet the code",
    }


DECISIONS = {
    "deck-ashcombe": [
        {"decision": "decline", "notes": "Rear setback is 7 feet, I measured it. The ledger is fastened with "
                                         "half-inch lag screws at 16 inches on center."},
        {"decision": "decline", "notes": "Flashing is self-adhered membrane under a Z-flashing. Leave the schedule as it is."},
        {"decision": "approve", "notes": ""},
    ],
    "solar-valcourt": [{"decision": "approve", "notes": ""}],
    "sign-lindqvist": [{"decision": "approve", "notes": ""}],
}


def write(root: Path) -> Path:
    root = Path(root)
    (root / "rules").mkdir(parents=True, exist_ok=True)
    (root / "drafts").mkdir(exist_ok=True)
    (root / "recorded").mkdir(exist_ok=True)
    for cat, lines in RULES.items():
        (root / "rules" / f"{cat}.txt").write_text(f"# Larkmoor permit review rules: {cat}\n" + "\n".join(lines) + "\n")

    _draft(root / "drafts" / "deck-narrative.docx", "Deck addition permit narrative",
           "Applicant: Wren Ashcombe. Parcel: Lot 17, Fallowmere subdivision. Category: deck.",
           [(f"Item 1 {D} Ledger-attached deck", ", 14 ft by 12 ft, pressure-treated framing on four footings 24 inches deep."),
            (f"Item 2 {D} Stair and landing", ", four risers to grade on the north side."),
            (f"Item 3 {D} Guard", ", 36 inches high on all open sides.")],
           [("Site", [f"The deck sits behind the house and {DECK_SETBACK}."]),
            ("Construction notes", ["Framing will begin on 2026-11-09 once footings are inspected."]),
            ("Inspections completed", ["Footing excavation inspection passed on 2026-10-19.",
                                       "Ledger location inspection passed on 2026-09-28."])],
           [("1", "2026-11-02", "2026-11-20"), ("2", "2026-11-16", "2026-11-24"), ("3", "2026-11-23", "2026-11-27")])
    _draft(root / "drafts" / "solar-narrative.docx", "Rooftop solar permit narrative",
           "Applicant: Idris Valcourt. Parcel: Lot 4, Brackenridge Court. Category: solar.",
           [(f"Item 1 {D} Array", ", 18 modules on the south roof plane, 7.2 kW total."),
            (f"Item 2 {D} Racking", ", flush rails attached to rafters at 48 inches on center."),
            (f"Item 3 {D} Inverter and disconnect", ", on the east wall beside the meter.")],
           [("Layout", ["See the attached roof plan for module layout."]),
            ("Fire access", ["A pathway is provided along the ridge.", "See the attached roof plan for module layout."]),
            ("Inspections completed", ["Rough electrical inspection passed on 2026-09-30."])],
           [("1", "2026-10-19", "2026-10-21"), ("2", "2026-10-19", "2026-10-20"), ("3", "2026-10-22", "2026-10-22")])
    _draft(root / "drafts" / "sign-narrative.docx", "Commercial sign permit narrative",
           "Applicant: Petra Lindqvist-Mora for Saltglass Bakery. Parcel: Unit 3, Corbel Row. Category: sign.",
           [(f"Item 1 {D} Wall sign", ", 32 square feet, channel letters on the north facade."),
            (f"Item 2 {D} Blade sign", ", 6 square feet, projecting 3 feet over the sidewalk at 9 feet clearance.")],
           [("Illumination", ["The wall sign is internally lit."]),
            ("Inspections completed", ["None yet."])],
           [("1", "2026-11-03", "2026-11-04"), ("2", "2026-11-03", "2026-11-03")])

    recorded = {"deck-ashcombe": [_deck_review(n) for n in (1, 2, 3)],
                "solar-valcourt": [_solar_review()], "sign-lindqvist": [_sign_review()]}
    for job, reviews in recorded.items():
        d = root / "recorded" / job
        d.mkdir(exist_ok=True)
        for n, r in enumerate(reviews, 1):
            (d / f"review-{n}.json").write_text(json.dumps(r, indent=1) + "\n")
            dec = dict(DECISIONS[job][n - 1], by=JOBS[job]["requester"])
            (d / f"decision-{n}.json").write_text(json.dumps(dec, indent=1) + "\n")
    (root / "jobs.json").write_text(json.dumps(JOBS, indent=1) + "\n")
    return root
