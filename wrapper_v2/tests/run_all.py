"""run_all — unified test-suite runner for wrapper_v2.

Runs every test_*.py sub-suite, aggregates pass/fail per suite, returns
exit-code 0 iff EVERY suite passes. Use as CI-anchor and pre-commit
sanity-check.

Why a runner instead of pytest?
  Our test files are stand-alone Python modules (each defines its own
  ANSI-colored runner + main()). This consolidates without forcing
  pytest dependency or test-file refactor. Per
  [[basetouch_verified_then_dollschon_overclock]]: solid-now beats
  perfect-later.

Run:    .venv/bin/python3 -m wrapper_v2.tests.run_all
Filter: .venv/bin/python3 -m wrapper_v2.tests.run_all m5 m6  (substring match)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


_REPO = Path(__file__).parent.parent.parent
_VENV = _REPO / ".venv" / "bin" / "python3"
_PY = str(_VENV) if _VENV.exists() else sys.executable

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


# Test suites in run-order. Listed with the schiri-task they close.
SUITES = [
    ("test_m3",                "M3 branch_balancer"),
    ("test_m4",                "M4 hover_legend"),
    ("test_m5",                "M5 factfact_cache"),
    ("test_m6_m7",             "M6 re-labrador + M7 WEISS-override"),
    ("test_m8",                "M8 9-fixture canonical_evals"),
    ("test_r08_n7_n8",         "R0.8 gray-out + N7/N8/N5 wire-verify"),
    ("test_r05_l0_firing_order","R0.5 L0 architectural firing-order"),
    ("test_n6_n9_n10_n14",     "N6 emergency + N9 compliance + N10 age-gate + N14 google-classic"),
    ("test_d1_routes",         "D1.a Handler god-class split — routes + handlers scaffold"),
    ("test_dir_moves",         "R2-target dir re-exports (l0 / classifier / verify / factampel)"),
    ("test_store",             "store/ DB + sessions + chats + deploy_stamp"),
    ("test_sse_generation",    "sse/ events+emit + generation/ stream+bare_greeting+style_mirror"),
    ("test_d7_register",       "D7 register-dedup — consolidated tone + irony classifier"),
    ("test_witness_routing",   "Phase-2 #3 witness-class routing (MATH detection)"),
    ("test_chrome_filter",     "factampel chrome-filter (greetings + Q-restate + closings)"),
    ("test_m9_basetouch",      "M9 BASETOUCH VERIFIED schiri-arbitration"),
]


def run_suite(name: str) -> tuple[bool, int, str]:
    """Returns (passed, elapsed_seconds, last_summary_line)."""
    start = time.time()
    try:
        result = subprocess.run(
            [_PY, "-m", f"wrapper_v2.tests.{name}"],
            cwd=str(_REPO),
            capture_output=True,
            timeout=120,
            text=True,
        )
        elapsed = time.time() - start
        # Pull the last non-empty line that looks like a summary
        lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
        summary = lines[-1] if lines else "(no output)"
        # Strip ANSI for clean display
        import re
        summary_clean = re.sub(r"\033\[[0-9;]*m", "", summary)
        return (result.returncode == 0, elapsed, summary_clean)
    except subprocess.TimeoutExpired:
        return (False, time.time() - start, "TIMEOUT (>120s)")
    except Exception as exc:
        return (False, time.time() - start, f"ERROR: {exc!r}")


def main(argv: list[str]) -> int:
    filters = [a.lower() for a in argv[1:]]
    suites = [s for s in SUITES if not filters or any(f in s[0].lower() for f in filters)]

    print(f"{_BOLD}wrapper_v2 — unified test-suite runner{_RESET}")
    print(f"  python:  {_PY}")
    print(f"  suites:  {len(suites)} of {len(SUITES)}")
    if filters:
        print(f"  filter:  {filters}")
    print("=" * 75)

    total_pass = 0
    total_fail = 0
    total_elapsed = 0.0
    results = []

    for name, desc in suites:
        sys.stdout.write(f"  {_DIM}running{_RESET}  {name:<32} ")
        sys.stdout.flush()
        ok, elapsed, summary = run_suite(name)
        total_elapsed += elapsed
        if ok:
            total_pass += 1
            marker = f"{_GREEN}✓{_RESET}"
        else:
            total_fail += 1
            marker = f"{_RED}✗{_RESET}"
        sys.stdout.write(f"\r  {marker} {name:<32} {elapsed:5.2f}s  {summary}\n")
        results.append((name, desc, ok, elapsed, summary))

    print("=" * 75)
    print()
    if total_fail == 0:
        print(f"{_GREEN}{_BOLD}✓ ALL {total_pass} SUITES PASS{_RESET}  ({total_elapsed:.2f}s total)")
        print()
        for name, desc, ok, elapsed, _ in results:
            print(f"  {_GREEN}✓{_RESET}  {name:<32}  {desc}")
        return 0
    else:
        print(f"{_RED}{_BOLD}✗ {total_fail} of {len(suites)} suites FAILED{_RESET}  ({total_elapsed:.2f}s total)")
        print()
        for name, desc, ok, elapsed, summary in results:
            marker = f"{_GREEN}✓{_RESET}" if ok else f"{_RED}✗{_RESET}"
            print(f"  {marker}  {name:<32}  {desc}")
            if not ok:
                print(f"       {summary}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
