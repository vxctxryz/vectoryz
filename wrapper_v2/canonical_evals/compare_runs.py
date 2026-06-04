"""compare_runs — diff two doctrine-eval result dirs side-by-side.

Usage:
  python3 compare_runs.py <baseline_run_dir> <candidate_run_dir>

Reads summary.json from both, plus per-fixture case_*.json, and prints:
  - Overall pass/fail delta
  - Per-rule pass/fail delta
  - Per-fixture pass-flip table (regressions highlighted)
  - Decision recommendation per the swap protocol
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load_run(d: Path) -> dict:
    summary = json.loads((d / "summary.json").read_text())
    metadata = json.loads((d / "metadata.json").read_text())
    cases = {}
    for f in sorted(d.glob("case_*.json")):
        c = json.loads(f.read_text())
        cases[c["id"]] = c
    return {"dir": str(d), "summary": summary, "metadata": metadata, "cases": cases}


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    base = load_run(Path(sys.argv[1]))
    cand = load_run(Path(sys.argv[2]))

    print(f"BASELINE: {base['dir']}")
    print(f"          model={base['metadata']['model']}  "
          f"modelfile={Path(base['metadata']['modelfile_path']).name}")
    print(f"CANDIDATE: {cand['dir']}")
    print(f"          model={cand['metadata']['model']}  "
          f"modelfile={Path(cand['metadata']['modelfile_path']).name}")
    print("=" * 78)

    bs, cs = base["summary"], cand["summary"]
    print(f"\nOVERALL:  baseline {bs['pass']}/{bs['total']}    "
          f"candidate {cs['pass']}/{cs['total']}    "
          f"Δ {cs['pass']-bs['pass']:+d}")
    print(f"  hard:   baseline {bs['hard_pass']}/{bs['hard_total']}    "
          f"candidate {cs['hard_pass']}/{cs['hard_total']}    "
          f"Δ {cs['hard_pass']-bs['hard_pass']:+d}")

    # Per-rule delta
    all_rules = sorted(set(bs["by_rule"]) | set(cs["by_rule"]))
    print(f"\n{'rule':<32}  {'baseline':<10}  {'candidate':<10}  Δ")
    print("-" * 78)
    for r in all_rules:
        b = bs["by_rule"].get(r, {"pass": 0, "fail": 0})
        c = cs["by_rule"].get(r, {"pass": 0, "fail": 0})
        bt = b["pass"] + b["fail"]
        ct = c["pass"] + c["fail"]
        delta = c["pass"] - b["pass"]
        marker = "  " if delta == 0 else (" +" if delta > 0 else " -")
        print(f"{r:<32}  {b['pass']}/{bt:<8}  {c['pass']}/{ct:<8}  {delta:+d}{marker}")

    # Per-fixture flip table
    print(f"\n{'fixture':<36}  {'base':<5}  {'cand':<5}  flip")
    print("-" * 78)
    regressions = []
    improvements = []
    for fid in sorted(set(base["cases"]) | set(cand["cases"])):
        b = base["cases"].get(fid, {"pass": None, "priority": "?"})
        c = cand["cases"].get(fid, {"pass": None, "priority": "?"})
        bp = "PASS" if b.get("pass") else "fail"
        cp = "PASS" if c.get("pass") else "fail"
        flip = ""
        if b.get("pass") and not c.get("pass"):
            flip = "REGRESSION"
            regressions.append((fid, b.get("priority", "?")))
        elif not b.get("pass") and c.get("pass"):
            flip = "improved"
            improvements.append(fid)
        prio = b.get("priority") or c.get("priority") or "?"
        prio_mark = "[H]" if prio == "hard" else "[s]"
        print(f"{prio_mark} {fid:<32}  {bp:<5}  {cp:<5}  {flip}")

    # Decision rule
    print()
    print("=" * 78)
    print("DECISION:")
    hard_delta = cs["hard_pass"] - bs["hard_pass"]
    soft_delta = (cs["pass"] - cs["hard_pass"]) - (bs["pass"] - bs["hard_pass"])
    hard_regressions = [r for r in regressions if r[1] == "hard"]

    if hard_regressions:
        print(f"  REJECT v2 — hard regression on {len(hard_regressions)} ship-gate rules:")
        for fid, _ in hard_regressions:
            print(f"    - {fid}")
    elif hard_delta >= 0 and soft_delta >= 0:
        print(f"  PROMOTE v2 — hard {hard_delta:+d}, soft {soft_delta:+d}")
        print(f"  Deploy command (on production host):")
        print(f"    cp $CANDIDATE_MODELFILE $LIVE_MODELFILE")
        print(f"    ollama create $MODEL_NAME -f $LIVE_MODELFILE")
    elif hard_delta >= 0 and soft_delta < 0:
        print(f"  CONDITIONAL — hard {hard_delta:+d} (ok), soft {soft_delta:+d} (regression)")
        print(f"  Investigate soft regressions before deploying:")
        for fid in sorted(set(r[0] for r in regressions if r[1] != "hard")):
            print(f"    - {fid}")
    else:
        print(f"  REJECT v2 — hard {hard_delta:+d}, soft {soft_delta:+d}")

    if improvements:
        print(f"\n  Improvements: {', '.join(improvements)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
