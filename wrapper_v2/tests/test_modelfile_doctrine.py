"""test_modelfile_doctrine — R1-R8 conformance suite for a wrapper-model.

Two modes:
  bare    — direct ollama /api/chat hit (no wrapper integration).
            Phase-3 model-swap audit surface. Catches what the model
            ALONE delivers.
  wrapper — through the wrapper /api/chat (full pipeline + factampel
            + tribunal + url_witness + cite_witness). Catches the
            user-visible end-to-end quality.

Bare mode is the canonical comparison surface for any FROM-swap or
SYSTEM-block edit. Wrapper mode is for "did the combined system
regress" checks.

Usage:
  python3 -m wrapper_v2.tests.test_modelfile_doctrine bare \\
      --modelfile wrapper_v2/canonical_evals/wrapper_model_trimmed_v2.Modelfile \\
      --model $MODEL_NAME
  python3 -m wrapper_v2.tests.test_modelfile_doctrine bare --limit 5
  python3 -m wrapper_v2.tests.test_modelfile_doctrine bare --rule r1_draft_refusal

Env:
  OLLAMA_HOST   default http://localhost:11434
  WRAPPER_HOST  default $WRAPPER_HOST or http://localhost

Results written to wrapper_v2/canonical_evals/results/{run_id}/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_DIR = THIS_DIR.parent
# Two import paths: wrapper_v2 tree (development) or sibling-file (single-dir deploy)
try:
    sys.path.insert(0, str(REPO_DIR.parent))
    from wrapper_v2.canonical_evals.modelfile_doctrine_v1 import CASES, SUITE_META  # noqa: E402
except ImportError:
    sys.path.insert(0, str(THIS_DIR))
    from modelfile_doctrine_v1 import CASES, SUITE_META  # noqa: E402

DEFAULT_RESULTS_DIR = REPO_DIR / "canonical_evals" / "results"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
WRAPPER_HOST = os.environ.get("WRAPPER_HOST", "http://localhost")

DEFAULT_TIMEOUT_S = 180

# ─── HTTP backends ──────────────────────────────────────────────────


def _post_json(url: str, body: dict, timeout: int) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def call_bare_ollama(model: str, system: str, user: str, timeout: int) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 1024, "top_p": 0.9},
    }
    resp = _post_json(f"{OLLAMA_HOST}/api/chat", body, timeout)
    return resp.get("message", {}).get("content", "")


def call_wrapper(prompt: str, timeout: int) -> str:
    """Hit the wrapper /api/chat (SSE → collect → return final assistant text).

    Stub: wrapper-mode requires SSE collection, auth cookie, and chat-id
    creation. Implement when bare-mode baseline is established and we
    actually want the combined-system regression sweep.
    """
    raise NotImplementedError(
        "wrapper-mode requires SSE collection + auth — implement after "
        "bare-mode baseline is green"
    )


# ─── Modelfile parsing ──────────────────────────────────────────────


def extract_system_from_modelfile(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8")
    m = re.search(r'SYSTEM\s+"""(.*?)"""', text, flags=re.DOTALL)
    return m.group(1).strip() if m else text.strip()


# ─── Scoring ────────────────────────────────────────────────────────


def _has(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def _re_search(text: str, pattern: str) -> bool:
    try:
        return re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) is not None
    except re.error:
        return False


def score(fixture: dict, response: str) -> dict:
    fails = []
    checks = 0

    for p in fixture.get("must_contain") or []:
        checks += 1
        if not _has(response, p):
            fails.append(f"must_contain missing: {p!r}")

    for key in ("must_contain_one", "must_match_one"):
        opts = fixture.get(key) or []
        if opts:
            checks += 1
            if not any(_has(response, p) for p in opts):
                fails.append(f"{key} — none present: {opts!r}")

    for key in ("must_not_contain", "must_not_contain_phrase"):
        for p in fixture.get(key) or []:
            checks += 1
            if _has(response, p):
                fails.append(f"{key} present: {p!r}")

    pat = fixture.get("must_match")
    if pat:
        checks += 1
        if not _re_search(response, pat):
            fails.append(f"must_match regex did not match: {pat!r}")

    pat = fixture.get("must_not_match")
    if pat:
        checks += 1
        if _re_search(response, pat):
            fails.append(f"must_not_match regex matched: {pat!r}")

    return {
        "pass": len(fails) == 0,
        "checks": checks,
        "fails": fails,
        "response_len": len(response),
        "response_sample": response[:400] + ("..." if len(response) > 400 else ""),
    }


# ─── Runner ─────────────────────────────────────────────────────────


def build_system_prompt(modelfile_path: str | None, system_extra: str | None) -> str:
    if modelfile_path:
        base = extract_system_from_modelfile(modelfile_path)
    else:
        # default — trimmed v2 in canonical_evals/
        default = REPO_DIR / SUITE_META["default_modelfile_path"]
        base = extract_system_from_modelfile(str(default)) if default.exists() else ""
    if system_extra:
        return base + "\n\n" + system_extra
    return base


def run_one_bare(fixture: dict, model: str, modelfile_path: str | None,
                 timeout: int) -> dict:
    system = build_system_prompt(modelfile_path, fixture.get("system_extra"))
    started = time.time()
    try:
        response = call_bare_ollama(model, system, fixture["prompt"], timeout)
        elapsed = time.time() - started
        s = score(fixture, response)
        return {
            "id": fixture["id"],
            "rule": fixture.get("rule"),
            "priority": fixture.get("priority", "soft"),
            "elapsed_s": round(elapsed, 2),
            **s,
            "response": response,
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        return {
            "id": fixture["id"],
            "rule": fixture.get("rule"),
            "priority": fixture.get("priority", "soft"),
            "pass": False,
            "fails": [f"runtime: {type(e).__name__}: {e!r}"],
            "elapsed_s": round(time.time() - started, 2),
            "response": "",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["bare", "wrapper"], default="bare", nargs="?")
    parser.add_argument("--model", default=SUITE_META["default_model"])
    parser.add_argument("--modelfile", default=None,
                        help="Path to .Modelfile; SYSTEM block extracted")
    parser.add_argument("--limit", type=int, default=0,
                        help="Run only first N fixtures")
    parser.add_argument("--rule", default=None,
                        help="Only fixtures matching this rule slug")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR),
                        help="where to write per-run results (default: wrapper_v2/canonical_evals/results)")
    parser.add_argument("--no-write", action="store_true",
                        help="Don't write results/ dir (smoke-test only)")
    args = parser.parse_args()

    cases = CASES
    if args.rule:
        cases = [c for c in cases if (c.get("rule") or "").startswith(args.rule)]
    if args.limit > 0:
        cases = cases[:args.limit]

    if not cases:
        print("no fixtures match selection", file=sys.stderr)
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"_{args.mode}"
    out_dir = Path(args.results_dir) / run_id
    if not args.no_write:
        out_dir.mkdir(parents=True, exist_ok=True)

    modelfile_used = args.modelfile or str(REPO_DIR / SUITE_META["default_modelfile_path"])
    sys_prompt_preview = build_system_prompt(modelfile_used, None)[:300]

    metadata = {
        "run_id": run_id,
        "mode": args.mode,
        "model": args.model,
        "modelfile_path": modelfile_used,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "suite_id": SUITE_META["id"],
        "n_fixtures": len(cases),
        "system_prompt_first_300": sys_prompt_preview,
    }

    print(f"Modelfile-doctrine eval · {run_id}")
    print(f"  mode={args.mode} model={args.model}")
    print(f"  modelfile={modelfile_used}")
    print(f"  fixtures={len(cases)}")
    print("=" * 72)

    if not args.no_write:
        (out_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    results = []
    for i, fx in enumerate(cases, 1):
        label = f"[{i:>2}/{len(cases)}] {fx['id']:<36}"
        print(f"{label} ", end="", flush=True)

        if args.mode == "bare":
            r = run_one_bare(fx, args.model, modelfile_used, args.timeout)
        else:
            print("wrapper-mode not implemented yet")
            return 1
        results.append(r)

        marker = "PASS" if r["pass"] else "FAIL"
        print(f"{marker} ({r['elapsed_s']}s)")
        if not r["pass"]:
            for fail in r.get("fails", []):
                print(f"        - {fail}")

        if not args.no_write:
            (out_dir / f"case_{i:03d}_{fx['id']}.json").write_text(
                json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    hard = [r for r in results if r.get("priority") == "hard"]
    hard_passed = sum(1 for r in hard if r["pass"])

    by_rule: dict[str, dict[str, int]] = {}
    for r in results:
        rule = r.get("rule") or "?"
        by_rule.setdefault(rule, {"pass": 0, "fail": 0})
        by_rule[rule]["pass" if r["pass"] else "fail"] += 1

    summary = {
        "total": total,
        "pass": passed,
        "fail": total - passed,
        "hard_total": len(hard),
        "hard_pass": hard_passed,
        "hard_fail": len(hard) - hard_passed,
        "by_rule": by_rule,
    }

    if not args.no_write:
        (out_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    print()
    print("=" * 72)
    print(f"summary:  {passed}/{total} pass    "
          f"(hard: {hard_passed}/{len(hard)})")
    print(f"by-rule:  {json.dumps(by_rule, ensure_ascii=False)}")
    if not args.no_write:
        print(f"results:  {out_dir}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
