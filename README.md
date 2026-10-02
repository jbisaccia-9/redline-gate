# redline-gate

[![ci](https://github.com/jbisaccia-9/redline-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/jbisaccia-9/redline-gate/actions/workflows/ci.yml)

**A document review loop where a model proposes tracked changes to your own file, and a gate checks every one before a person approves.**

The pattern: someone drafting a document that a strict reviewer will judge —
a permit narrative, a grant report, a compliance filing — drops the draft into a
chat agent and names which rule set applies. They get back **their own file**,
with every proposed fix as a tracked change and a comment citing the rule, a
short to-do list, and a card to approve or decline with notes. Declines with
notes start another round on the original. Approval sends the final file.
Nothing goes outward on its own.

The model is good at the reading. Everything that makes the output
trustworthy is somewhere else: a model that copies a paraphrase as its anchor,
"helpfully" fills in a number nobody gave it, cites a rule that isn't
verified, stops checking after item two, or forgets in round three what the
person asked for in round one, produces a file that *looks* finished. This repo
is the loop plus the gate that grades every round. On the seeded jobs: **three
narratives delivered (one after three rounds of notes), every round passing —
and 8/8 counterexamples refused, each for exactly the rule in its name.** In
every round, rejecting all of the file's tracked changes gives back the
original text, tables included.

## Quickstart

```bash
pip install git+https://github.com/jbisaccia-9/redline-gate
python -m redlinegate seed data                 # rule packs, three drafts, recorded reviews and decisions
python -m redlinegate run data --out out/jobs   # every job through the loop, then graded
python -m redlinegate anchors data              # one lesson, measured
python -m redlinegate counterexamples out/cx && python -m redlinegate check-dir out/cx   # exit 1
```

No credentials, no network, no model. Open `out/jobs/deck-ashcombe/round-1/*.docx`
in Word to see what the applicant receives.

## The setting

The City of Larkmoor Building Division (fictional) reviews permit narratives
for decks, rooftop solar and commercial signs. Each category has a plain-text
rule pack; every rule has a stable ID, a source, and a status:

```
DECK-SITE-001 | verified | priority | source: Larkmoor residential code 4.2 | State the distance from the deck to the nearest property line, in feet.
DECK-DOC-006 | unverified | | source: reviewer email, spring | Attach a photo of the existing ledger location.
```

**Verified** rules may justify an edit. **Unverified** ones may raise a to-do
and nothing more. **Priority** marks rules learned from real past rejections.

## The loop

| step | who | what |
|---|---|---|
| 1 intake | AI | the chat agent works out the category (asks if it's missing) and hands over the file |
| 2 extract | code | .docx to markdown, tables included. *A "success" with no text stops the run.* |
| 3 rules | code | category → one rule pack |
| 4 review | AI | one prompt: text, category, rule pack, **today's date**, and on later rounds the notes and previous review. Returns one JSON object. |
| 5 backstop | code | re-checks what a model with no clock can't: a "completed" inspection dated in the future |
| 6 apply | code | each edit written into the **original** file as a tracked change with a rule comment; placeholders highlighted; edits it can't place come back as a list |
| 7 share | code | one file, one link, visible to the requester only |
| 8 card | person | at most five twelve-word lines, to-do counts, the link. Approve, or decline with notes |
| 9 revise | AI | notes → steps 4–6 again on the original, same file, same link; changes tagged `FEEDBACK` |
| 10 deliver | code | on approval, the final file by email to the requester, with every check, change and to-do |

**The model never** extracts text, finds text in the file, edits the file,
runs the date backstop, saves, shares, sends or approves. It reads and writes
JSON:

```json
{ "item_checks": "1. Item 1 - setback: MISSING (DECK-SITE-001) - ...",
  "edits": [{ "op": "replace | insert_after | replace_block",
              "anchor": "exact text copied from the document, 5-40 words",
              "text": "new wording, or [NEEDS INPUT: what is missing - RULE-ID]",
              "heading": "section the edit sits under",
              "rule": "DECK-SITE-001 | FEEDBACK",
              "reason": "fifteen words at most" }],
  "change_log": "...", "todo": "N. HIGH|MEDIUM - section - what to do (RULE-ID)",
  "from_feedback": "...", "summary": "five lines at most" }
```

A missing value becomes a highlighted `[NEEDS INPUT: …]`. A placeholder is
always acceptable; a guess never is.

## The gate

`gate.py` grades a finished job — every round's review, file, card and
decision, and the delivery — against the original file and the rule pack.

| rule | what it refuses |
|---|---|
| G1 source | a review that ran on empty extracted text; a round that reviewed anything but the original file; a model not given today's date |
| G2 anchored | an edit applied where its anchor doesn't occur exactly once in the original, or isn't 5–40 words; an unplaced edit the card doesn't report |
| G3 cited | an edit citing a rule that's unverified or not in the pack; `FEEDBACK` with no notes to act on; a reason over fifteen words |
| G4 no new facts | a number in an edit that neither the document nor the requester's notes contain; a replacement that silently drops a number |
| G5 complete | a work item the per-item checks skipped (items are counted from the document, not the model); a future "completed" date the backstop didn't flag |
| G6 original | a file where rejecting every tracked change doesn't reproduce the original — rebuilt instead of edited, a table lost, a change made untracked |
| G7 approval | a card over five lines or twelve words a line; a card pointing at a different file from the one produced; approval by anyone but the requester; delivery without approval, of any file but the approved one, or to anyone else |
| G8 feedback | notes with no change made from them; a later round that drops a change an earlier round's notes asked for |

## Lessons, measured

**Models copy anchors from the markdown they were shown.** The file has no
`**` or `##`, so an anchor copied as `**Item 1 — Ledger-attached deck**, 14 ft…`
matches nothing. `anchors` measures it across the recorded rounds:

```
edits across all recorded rounds          9
anchors carrying markdown from the prompt 3
unplaceable if matched as-is             4
unplaceable after stripping markdown     1   (the remaining one matches two places and is reported, not forced)
```

**Extraction can report success with no text.** The run stops before the
model sees it; `g1-empty-extraction` is the job where it didn't.

**Short card, complete email.** Long approval cards break chat apps, so the
card carries five short lines and a link; the delivery email carries
everything — counts, issues, the requester's notes, changes made from them,
every check, every change, and what to check by hand.

**Give the model the date, and back it up.** The deck draft says an inspection
"passed" two weeks after the date of the review. The model wasn't asked to catch that and
didn't; the backstop did, every round.

## The counterexamples

```
g1-empty-extraction        extraction reported success with no text, and the review ran anyway
g2-forced-anchor           an edit applied although its anchor is a paraphrase that isn't in the file
g3-unverified-rule         an edit justified by a rule the pack marks unverified
g4-invented-hours          a placeholder 'helpfully' filled with hours nobody supplied
g5-skipped-item            the per-item checks stop before the last item
g6-rebuilt-file            the file rebuilt instead of edited, and the schedule table didn't survive
g7-edited-after-approval   the delivered file was changed after the requester approved it
g8-feedback-dropped        round three quietly drops a change the requester asked for in round one
```

Each is a real seeded job changed in exactly one way — and where that change
touches the file, the card, link and delivery are restamped to match, so the
counterexample is wrong *only* in the way its name says. A parametrized test
asserts each fails on its own rule and no other.

## What's here

```
src/redlinegate/
  extract.py          .docx -> markdown, the empty-text guard, markdown stripping, item parsing
  rules.py            rule packs: ID, status, priority, source
  redline.py          tracked changes and rule comments in the user's own file; reject/accept views
  loop.py             the rounds: prompt, review, backstop, apply, share, card, decide, deliver
  gate.py             G1-G8
  anchors.py          the markdown-anchor measurement
  counterexamples.py  the eight jobs that must be refused
  seed.py             the fictional office, rule packs, drafts, recorded reviews and decisions
```

## Scope, stated honestly

- **Everything is fictional**: the office, the codes cited in the rule packs,
  every applicant, parcel, business and address.
- **Model answers are recorded.** That proves the loop and the gate, not a
  model's judgment. The reviewer is one class with one method; a live model
  sits behind the same contract, and the gate grades it the same way.
- **G4 matches numbers, not meaning.** In `g4-invented-hours` the model wrote
  "6 am to 10 pm"; only the 10 was caught, because a 6 already appears in the
  document ("6 square feet"). Words and names are not checked at all. It
  catches the common failure — a confident number in a placeholder's place —
  not every invented fact.
- G2 proves an anchor is real and unique, not that the edit belongs there; that
  judgment stays with the person approving the card.
- The edit engine works at paragraph level in body text. Edits inside table
  cells, headers and footnotes come back unplaced rather than forced.
- The chat agent, the approval card's transport and the mail service are out
  of scope; the card and email are files. The same JSON contract works behind
  any chat front end that accepts a file.

## Part of the *-gate* family

Nothing ships until it passes a gate — and the gate itself must be earned.
The others: [github.com/jbisaccia-9](https://github.com/jbisaccia-9).

MIT.
