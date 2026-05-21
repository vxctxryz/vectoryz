#!/usr/bin/env python3
"""Diagnostic script for disambig-coverage pipeline.

Tests three layers in order:
  1. fetch_disambig_alternatives() directly — does Wikipedia call work?
  2. classify_and_fetch() end-to-end — does the pipeline route correctly?
  3. Inspect the context_block — would the model receive disambig instructions?

Usage on prod:
  /opt/vectoryz_cc/venv/bin/python /opt/vectoryz_cc/tools/check_disambig.py

Outputs structured info — paste-able for debugging.
"""

import sys
import os
import time

# Path-setup: locate vectoryz package by walking up from this script +
# checking common deployment locations
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT_CANDIDATES = [
    os.path.dirname(HERE),                          # one up from tools/
    os.path.join(os.path.dirname(HERE), ".."),      # two up
    "/opt/vectoryz",                                # common deploy location
    os.path.expanduser("~/vectoryz"),               # user-home install
]
for r in ROOT_CANDIDATES:
    if os.path.exists(os.path.join(r, "wrapper_v2")) or \
       os.path.exists(os.path.join(r, "vectoryz", "pipeline")):
        sys.path.insert(0, r)
        break


def hr(title=""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "was ist echelon?"
    print(f"\n# Diagnostic: disambig-coverage pipeline")
    print(f"# Query: {query!r}")
    print(f"# Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"# Python: {sys.executable}")

    # --- Layer 1: direct fetch ---
    hr("Layer 1: fetch_disambig_alternatives()")
    try:
        from wrapper_v2.pipeline.wiki_wortwolke import fetch_disambig_alternatives
        # Extract candidate term naively for the direct test
        import re
        candidate = re.sub(
            r"^\s*(was ist|was sind|wer ist|wer war|wer sind|was bedeutet|"
            r"what is|what are|who is|tell me about|"
            r"erklär(?:e|st du)?|definier(?:e|st du)?)\s+",
            "", query.strip(), flags=re.IGNORECASE,
        ).strip().rstrip("?.!,")
        print(f"  candidate term: {candidate!r}")

        t0 = time.time()
        result = fetch_disambig_alternatives(candidate, lang="de", timeout=5.0)
        dt = (time.time() - t0) * 1000
        print(f"  fetch took: {dt:.0f}ms")
        if result is None:
            print(f"  RESULT: None (no disambig page found for variants)")
        else:
            print(f"  RESULT: title={result.get('title')!r}")
            print(f"          url={result.get('url')!r}")
            print(f"          alternatives ({len(result.get('alternatives', []))}):")
            for a in result.get("alternatives", []):
                print(f"            - {a}")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # --- Layer 2: classify_and_fetch end-to-end ---
    hr("Layer 2: classify_and_fetch() end-to-end")
    try:
        from wrapper_v2.pipeline import pre_search as ps
        t0 = time.time()
        r = ps.classify_and_fetch(query, max_snippets=2)
        dt = (time.time() - t0) * 1000
        print(f"  classify_and_fetch took: {dt:.0f}ms")
        if r is None:
            print(f"  RESULT: None")
        else:
            print(f"  needs_search: {r.get('decision', {}).get('needs_search')}")
            print(f"  no_search_needed: {r.get('no_search_needed')}")
            print(f"  disambig present: {bool(r.get('disambig'))}")
            if r.get("disambig"):
                d = r["disambig"]
                print(f"    disambig.title: {d.get('title')!r}")
                print(f"    disambig.alternatives count: {len(d.get('alternatives', []))}")
            print(f"  babel_route present: {bool(r.get('babel_route'))}")
            if r.get("babel_route"):
                br = r["babel_route"]
                print(f"    babel_route.detected_lang: {br.detected_lang}")
                print(f"    babel_route.confidence: {br.confidence:.3f}")
            print(f"  snippet count: {len(r.get('snippets', []))}")
            print(f"  source count: {len(r.get('sources', []))}")
            print(f"  context_block length: {len(r.get('context_block') or '')}")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    # --- Layer 3: context_block preview ---
    hr("Layer 3: context_block preview (first 1500 chars)")
    try:
        if r and r.get("context_block"):
            print(r["context_block"][:1500])
            if len(r["context_block"]) > 1500:
                print(f"\n  [+ {len(r['context_block']) - 1500} more chars]")
        else:
            print("  (empty or no result)")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")

    # --- Summary verdict ---
    hr("Verdict")
    try:
        if r is None:
            print("  ✗ classify_and_fetch returned None — pipeline didn't route the query")
        elif r.get("disambig"):
            print("  ✓ Disambig IS detected and present in context_block")
            print("  → If model still ignores it, that's MODEL-PRIOR-LOCK (training trumps context)")
            print("  → Stronger prompt-discipline OR model fine-tune needed")
        else:
            print("  ✗ Disambig NOT detected — wiring bug or fetch failure")
            print("  → Check Layer 1 output: if direct-fetch works but pipeline doesn't = wiring")
            print("  → If both fail = network/Wikipedia/code issue on prod")
    except Exception:
        pass

    print()


if __name__ == "__main__":
    main()
