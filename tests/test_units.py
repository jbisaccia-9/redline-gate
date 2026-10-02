import datetime as dt

from redlinegate import extract, gate, loop, rules, seed


def test_rule_packs_parse_with_status_and_priority(tmp_path):
    seed.write(tmp_path)
    pack = rules.load(tmp_path / "rules" / "deck.txt")
    assert pack["DECK-SITE-001"].verified and pack["DECK-SITE-001"].priority
    assert not pack["DECK-DOC-006"].verified


def test_strip_md_removes_what_models_copy():
    assert extract.strip_md("## Site") == "Site"
    assert extract.strip_md("**Item 1 \u2014 Deck**, 14 ft") == "Item 1 \u2014 Deck, 14 ft"
    assert extract.strip_md("`code`  and   __x__") == "code and x"


def test_items_are_parsed_from_the_document_not_from_the_model(tmp_path):
    seed.write(tmp_path)
    assert extract.items(extract.to_markdown(tmp_path / "drafts" / "deck-narrative.docx")) == [1, 2, 3]
    assert extract.items(extract.to_markdown(tmp_path / "drafts" / "sign-narrative.docx")) == [1, 2]


def test_facts_ignore_placeholders():
    assert gate._facts("set to [NEEDS INPUT: hours - SIGN-LUM-003] at 9 ft") == {"9"}


def test_backstop_only_looks_at_completed_inspections():
    md = "## Construction notes\nStart 2026-12-01.\n## Inspections completed\nPassed on 2026-11-01.\n"
    assert len(loop.backstop(md, dt.date(2026, 10, 5))) == 1
