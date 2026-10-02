import json
import zipfile

import pytest

from redlinegate import counterexamples, gate, loop, redline, seed


def _j(p):
    return json.loads(p.read_text())


def test_every_seeded_job_is_delivered_and_passes(jobs):
    for job in seed.JOBS:
        assert _j(jobs / "jobs" / job / "job.json")["status"] == "delivered"
        assert gate.grade(jobs / "jobs" / job).passed


@pytest.mark.parametrize("name", sorted(counterexamples.DESCRIPTIONS))
def test_counterexample_is_refused_for_exactly_its_own_rule(tmp_path, name):
    counterexamples.build(tmp_path / "data", tmp_path / "cx")
    v = gate.grade(tmp_path / "cx" / name)
    assert v.rules_failed == [name[:2].upper()], v.failures


def test_rejecting_every_change_gives_back_the_original_and_accepting_gives_the_edits(jobs):
    job = jobs / "jobs" / "deck-ashcombe"
    orig = job / _j(job / "job.json")["original"]
    out = job / "round-3" / "deck-narrative-reviewed.docx"
    assert redline.view(out, "reject") == redline.view(orig, "reject")
    accepted = "\n".join(t for _, t in redline.view(out, "accept"))
    assert "rear property line is 7 feet" in accepted and "Z-flashing" in accepted
    assert "adequate" not in accepted


def test_every_placed_edit_carries_a_comment_citing_its_rule(jobs):
    out = jobs / "jobs" / "deck-ashcombe" / "round-1" / "deck-narrative-reviewed.docx"
    xml = zipfile.ZipFile(out).read("word/comments.xml").decode()
    assert "DECK-SITE-001" in xml and "DECK-STR-003" in xml


def test_empty_extraction_stops_before_the_model(tmp_path):
    seed.write(tmp_path / "d")
    m = loop.run_job(tmp_path / "d", "sign-lindqvist", tmp_path / "jobs", simulate_empty=True)
    assert m["status"] == "failed" and m["rounds"] == 0
    assert not list((tmp_path / "jobs" / "sign-lindqvist").glob("round-*"))
    assert gate.grade(tmp_path / "jobs" / "sign-lindqvist").passed      # stopping is the correct outcome


def test_revisions_review_the_original_with_notes_and_overwrite_one_link(jobs):
    job = jobs / "jobs" / "deck-ashcombe"
    p2 = _j(job / "round-2" / "prompt.json")
    assert "7 feet" in p2["notes"] and p2["previous_review"]["edits"]
    shas = {_j(job / f"round-{n}" / "review.json")["source_sha"] for n in (1, 2, 3)}
    assert shas == {_j(job / "job.json")["original_sha"]}
    assert {_j(job / f"round-{n}" / "card.json")["file"] for n in (1, 2, 3)} == {"shared/deck-narrative-reviewed.docx"}


def test_backstop_catches_a_completed_inspection_dated_in_the_future(jobs):
    r = _j(jobs / "jobs" / "deck-ashcombe" / "round-1" / "review.json")
    assert any("2026-10-19" in b and "BACKSTOP" in b for b in r["backstop"])
    assert _j(jobs / "jobs" / "sign-lindqvist" / "round-1" / "review.json")["backstop"] == []


def test_an_ambiguous_anchor_is_reported_for_a_human_not_forced(jobs):
    job = jobs / "jobs" / "solar-valcourt"
    pl = _j(job / "round-1" / "placements.json")
    assert [p["placed"] for p in pl] == [True, False] and "2 places" in pl[1]["reason"]
    assert _j(job / "round-1" / "card.json")["check_by_hand"] == 1
    assert "Rapid shutdown switch" in _j(job / "delivery" / "email.json")["body"].split("Check by hand")[1]


def test_lesson_strip_markdown_before_matching(jobs):
    data = jobs / "data"
    r = _j(data / "recorded" / "deck-ashcombe" / "review-1.json")
    assert "**" in r["edits"][1]["anchor"]
    raw = redline.apply(data / "drafts" / "deck-narrative.docx", r["edits"], jobs / "raw.docx", "2026-10-05T00:00:00Z", strip=False)
    fixed = redline.apply(data / "drafts" / "deck-narrative.docx", r["edits"], jobs / "fixed.docx", "2026-10-05T00:00:00Z")
    assert [p.placed for p in raw] == [True, False] and all(p.placed for p in fixed)


def test_delivery_goes_to_the_requester_alone(jobs):
    for job, spec in seed.JOBS.items():
        e = _j(jobs / "jobs" / job / "delivery" / "email.json")
        assert e["to"] == [spec["requester"]] and not e["cc"]
        assert _j(jobs / "jobs" / job / "share.json")["viewers"] == [spec["requester"]]
