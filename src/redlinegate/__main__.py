from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import anchors, counterexamples, gate, loop, seed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="redlinegate")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("seed", help="write rule packs, drafts, recorded reviews and decisions")
    a.add_argument("data")
    a = sub.add_parser("run", help="run every job through the loop, then grade it")
    a.add_argument("data"); a.add_argument("--out", default="out/jobs")
    a = sub.add_parser("check-dir", help="grade every job in a directory; exit 1 if any is refused")
    a.add_argument("dir")
    a = sub.add_parser("counterexamples", help="build the jobs that must be refused")
    a.add_argument("out"); a.add_argument("--data", default="out/cx-data")
    a = sub.add_parser("anchors", help="measure markdown copied into anchors")
    a.add_argument("data")
    args = ap.parse_args(argv)

    if args.cmd == "seed":
        print(f"wrote {seed.write(Path(args.data))}")
        return 0
    if args.cmd == "run":
        lines, ok = [], True
        for job in seed.JOBS:
            m = loop.run_job(Path(args.data), job, Path(args.out))
            v = gate.grade(Path(args.out) / job)
            ok &= v.passed
            lines.append(f"{job:<16} rounds {m['rounds']}  {m['status']:<10} {v.line().split()[0]}")
        print("\n".join(lines))
        return 0 if ok else 1
    if args.cmd == "check-dir":
        vs = gate.check_dir(Path(args.dir))
        bad = sum(not v.passed for v in vs)
        print("\n".join(v.line() for v in vs) + f"\n\n{len(vs) - bad} pass, {bad} refused")
        return 1 if bad or not vs else 0
    if args.cmd == "counterexamples":
        names = counterexamples.build(Path(args.data), Path(args.out))
        print("\n".join(f"{n:<26} {counterexamples.DESCRIPTIONS[n]}" for n in names))
        return 0
    print(anchors.report(Path(args.data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
