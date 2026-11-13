"""Run the judging harness.

    uv run python -m bench.run --methods running-z --split dev --out results/bench

Writes one JSON record per case, a summary JSON and a markdown table per
method. Every case is reported, including the failures. --sensitivity
reruns a method with each of its structural constants halved and
doubled (rules of evidence, rule 2).
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from bench.cases import HEALTHY_ROWS, ONSET_AGES, suite
from bench.methods import METHODS
from bench.score import render, replay, summarize


def run_method(factory, split, out_dir: Path, tag: str, **suite_kw) -> dict:
    records = []
    for case in suite(split, **suite_kw):
        work = Path(tempfile.mkdtemp(prefix="acm_bench_"))
        try:
            rec = replay(factory(), case, work)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        records.append(rec)
        print(f"  {tag:28s} {case.name:44s} false={rec['false_advisories']} "
              f"detected={rec.get('detected', '-')}", flush=True)
    summary = summarize(records)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = tag.replace("[", "_").replace("]", "")
    (out_dir / f"{safe}-{split}.json").write_text(
        json.dumps({"summary": summary, "records": records}, indent=1),
        encoding="utf-8")
    (out_dir / f"{safe}-{split}.md").write_text(
        render(tag, split, summary), encoding="utf-8")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--methods", nargs="+", default=["running-z"],
                    choices=sorted(METHODS))
    ap.add_argument("--split", choices=("dev", "judge"), default="dev")
    ap.add_argument("--out", default="results/bench")
    ap.add_argument("--stages", nargs="+", default=list(ONSET_AGES),
                    choices=list(ONSET_AGES))
    ap.add_argument("--types", nargs="+", default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=None)
    ap.add_argument("--healthy-days", type=float, default=HEALTHY_ROWS / 1440)
    ap.add_argument("--sensitivity", action="store_true")
    a = ap.parse_args()
    kw = dict(stages=tuple(a.stages), types=a.types, seeds=a.seeds,
              healthy_rows=int(a.healthy_days * 1440))
    out = Path(a.out)
    for name in a.methods:
        cls = METHODS[name]
        s = run_method(cls, a.split, out, name, **kw)
        print(render(name, a.split, s))
        if a.sensitivity:
            for const, value in cls.constants.items():
                for f in (0.5, 2.0):
                    tag = f"{name}[{const}x{f}]"
                    s2 = run_method(lambda: cls(**{const: value * f}),
                                    a.split, out, tag, **kw)
                    print(render(tag, a.split, s2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
