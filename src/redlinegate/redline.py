"""The edit engine. Takes the model's edits and writes each one into the user's OWN file as a
tracked change with a comment citing the rule. It never rebuilds the document: tables,
layout and everything the model didn't touch stay exactly as they were. Edits it can't place
come back as a list instead of being dropped or forced."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run

from .extract import strip_md

AUTHOR = "redline-gate"
PLACEHOLDER = re.compile(r"(\[NEEDS INPUT:[^\]]*\])")


@dataclass
class Placement:
    index: int
    placed: bool
    reason: str = ""


class _Rev:
    def __init__(self, date: str):
        self.n, self.date = 1000, date

    def attrs(self, el):
        self.n += 1
        el.set(qn("w:id"), str(self.n))
        el.set(qn("w:author"), AUTHOR)
        el.set(qn("w:date"), self.date)
        return el


def _run(text: str, rpr, deleted=False, highlight=False):
    r = OxmlElement("w:r")
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    if highlight:
        rp = r.find(qn("w:rPr"))
        if rp is None:
            rp = OxmlElement("w:rPr")
            r.insert(0, rp)
        h = OxmlElement("w:highlight")
        h.set(qn("w:val"), "yellow")
        rp.append(h)
    t = OxmlElement("w:delText" if deleted else "w:t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    return r


def _ins_runs(text: str, rpr, rev: _Rev):
    ins = rev.attrs(OxmlElement("w:ins"))
    for seg in PLACEHOLDER.split(text):
        if seg:
            ins.append(_run(seg, rpr, highlight=bool(PLACEHOLDER.fullmatch(seg))))
    return ins


def _rpr(r_el):
    rp = r_el.find(qn("w:rPr"))
    return None if rp is None else rp


def _replace_in_paragraph(p, start: int, end: int, new: str, rev: _Rev):
    runs = [r for r in p._p if r.tag == qn("w:r")]
    out, pos, ins_done, first_del_rpr = [], 0, False, None

    def emit_ins():
        nonlocal ins_done
        if not ins_done and new:
            out.append(_ins_runs(new, first_del_rpr if first_del_rpr is not None else (_rpr(runs[0]) if runs else None), rev))
        ins_done = True

    for r in runs:
        t = "".join(x.text or "" for x in r.iter(qn("w:t")))
        s, e = pos, pos + len(t)
        rp = _rpr(r)
        for a, b, kind in ((s, min(e, start), "keep"), (max(s, start), min(e, end), "del"), (max(s, end), e, "keep")):
            if a >= b:
                continue
            seg = t[a - s:b - s]
            if kind == "del":
                first_del_rpr = rp if first_del_rpr is None else first_del_rpr
                d = rev.attrs(OxmlElement("w:del"))
                d.append(_run(seg, rp, deleted=True))
                out.append(d)
            else:
                if a >= end:
                    emit_ins()
                out.append(_run(seg, rp))
        pos = e
    emit_ins()
    for r in runs:
        p._p.remove(r)
    for el in out:
        p._p.append(el)
    return [el for el in out if el.tag == qn("w:ins")]


def _insert_paragraph_after(p, new: str, rev: _Rev):
    np_ = OxmlElement("w:p")
    ppr = OxmlElement("w:pPr")
    rpr = OxmlElement("w:rPr")
    rpr.append(rev.attrs(OxmlElement("w:ins")))      # the paragraph mark itself is new
    ppr.append(rpr)
    np_.append(ppr)
    ins = _ins_runs(new, None, rev)
    np_.append(ins)
    p._p.addnext(np_)
    return np_, [ins]


def _delete_block(paras, new: str, rev: _Rev):
    for i, p in enumerate(paras):
        for r in [r for r in p._p if r.tag == qn("w:r")]:
            t = "".join(x.text or "" for x in r.iter(qn("w:t")))
            d = rev.attrs(OxmlElement("w:del"))
            d.append(_run(t, _rpr(r), deleted=True))
            r.addprevious(d)
            p._p.remove(r)
        if i < len(paras) - 1:                       # merge into the next paragraph
            ppr = p._p.get_or_add_pPr()
            rpr = ppr.find(qn("w:rPr"))
            if rpr is None:
                rpr = OxmlElement("w:rPr")
                ppr.append(rpr)
            rpr.insert(0, rev.attrs(OxmlElement("w:del")))
    ins = _ins_runs(new, None, rev)
    paras[-1]._p.append(ins)
    return [ins]


def locate(texts: list[str], anchor: str, strip: bool = True) -> list[tuple[int, int]]:
    a = strip_md(anchor) if strip else anchor
    hits = []
    for i, t in enumerate(texts):
        start = t.find(a)
        while start != -1 and a:
            hits.append((i, start))
            start = t.find(a, start + 1)
    return hits


def apply(src, edits: list[dict], dst, date: str, strip: bool = True) -> list[Placement]:
    doc = Document(src)
    paras = doc.paragraphs
    texts = [p.text for p in paras]          # frozen: every anchor is matched against the original
    rev, results, consumed = _Rev(date), [], set()
    for k, e in enumerate(edits):
        a = strip_md(e["anchor"]) if strip else e["anchor"]
        hits = locate(texts, e["anchor"], strip)
        if len(hits) != 1:
            results.append(Placement(k, False, "anchor not found" if not hits else f"anchor matches {len(hits)} places"))
            continue
        pi, start = hits[0]
        if e["op"] == "replace":
            if pi in consumed:
                results.append(Placement(k, False, "overlaps an earlier edit"))
                continue
            ins = _replace_in_paragraph(paras[pi], start, start + len(a), e["text"], rev)
            consumed.add(pi)
        elif e["op"] == "insert_after":
            _, ins = _insert_paragraph_after(paras[pi], e["text"], rev)
        elif e["op"] == "replace_block":
            ends = locate(texts, e.get("anchor_end", ""), strip)
            if len(ends) != 1 or ends[0][0] < pi:
                results.append(Placement(k, False, "block end not found once after its start"))
                continue
            block = list(range(pi, ends[0][0] + 1))
            if consumed & set(block):
                results.append(Placement(k, False, "overlaps an earlier edit"))
                continue
            ins = _delete_block([paras[i] for i in block], e["text"], rev)
            consumed |= set(block)
        else:
            results.append(Placement(k, False, f"unknown op {e['op']!r}"))
            continue
        run_el = ins[0].find(qn("w:r"))
        doc.add_comment(Run(run_el, paras[pi]), text=f"{e['rule']}: {e['reason']}", author=AUTHOR, initials="RG")
        results.append(Placement(k, True))
    doc.save(dst)
    return results


# ---- read-backs used by the gate ----------------------------------------------------------

def _texts(body, view: str):
    """view='reject' -> the document as if every tracked change were rejected (the original);
    view='accept' -> as if every change were accepted (what the user will submit)."""
    out = []
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            mark_ins = child.find(f"{qn('w:pPr')}/{qn('w:rPr')}/{qn('w:ins')}") is not None
            if view == "reject" and mark_ins:
                continue
            parts = []
            for el in child.iter(qn("w:t"), qn("w:delText")):
                in_ins = any(a.tag == qn("w:ins") for a in el.iterancestors())
                in_del = el.tag == qn("w:delText")
                if (view == "reject" and not in_ins) or (view == "accept" and not in_del):
                    parts.append(el.text or "")
            out.append(("p", "".join(parts)))
        elif tag == "tbl":
            out.append(("tbl", "\n".join("|".join("".join(t.text or "" for t in c.iter(qn("w:t")))
                                                   for c in r.iter(qn("w:tc"))) for r in child.iter(qn("w:tr")))))
    return out


def view(path, which: str):
    return _texts(Document(path).element.body, which)


def untracked_original_view(path):
    return _texts(Document(path).element.body, "reject")
