# Results

Generated 2026-10-02 by `scripts/make_results.py` — every block below is captured command output, not prose.

## Unit tests

`python -m pytest -q` — exit 0, OK

```
......................                                                   [100%]
22 passed in 6.13s
```

## Seed

`python -m redlinegate seed data` — exit 0, OK

```
wrote data
```

## Every job through the loop, then graded

`python -m redlinegate run data --out out/jobs` — exit 0, OK

```
deck-ashcombe    rounds 3  delivered  PASS
solar-valcourt   rounds 1  delivered  PASS
sign-lindqvist   rounds 1  delivered  PASS
```

## Markdown copied into anchors

`python -m redlinegate anchors data` — exit 0, OK

```
edits across all recorded rounds          9
anchors carrying markdown from the prompt 3
unplaceable if matched as-is             4
unplaceable after stripping markdown     1   (the remaining one matches two places and is reported, not forced)
```

## Build the counterexamples

`python -m redlinegate counterexamples out/cx --data out/cx-data` — exit 0, OK

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

## Gate refuses every counterexample, each for its own rule

`python -m redlinegate check-dir out/cx` — expected non-zero exit, OK

```
REFUSED  g1-empty-extraction        G1  extraction produced no text, but the review ran anyway
REFUSED  g2-forced-anchor           G2  round 1 edit 1: applied, but its anchor occurs 0 times in the original
REFUSED  g3-unverified-rule         G3  round 1 edit 2: cites 'DECK-DOC-006', unverified - it may raise a to-do, not justify an edit
REFUSED  g4-invented-hours          G4  round 1 edit 1: introduces ['10'], which neither the document nor the requester's notes contain
REFUSED  g5-skipped-item            G5  round 3: items [3] were never checked
REFUSED  g6-rebuilt-file            G6  round 1: rejecting every tracked change does not give back the original
REFUSED  g7-edited-after-approval   G7  the delivered file is not the file that was approved
REFUSED  g8-feedback-dropped        G8  round 3: 1 change(s) made from earlier notes were dropped

0 pass, 8 refused
```
