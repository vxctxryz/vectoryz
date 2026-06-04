"""sandbox — falsifiable tests for per-chat workspace.

Run via: python3 -m wrapper_v2.tests.test_sandbox
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Point to a temp dir BEFORE importing the module
_tmp = tempfile.mkdtemp(prefix="sandbox_test_")
os.environ["VECTORYZ_SANDBOX_ROOT"] = _tmp

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from wrapper_v2.infra.sandbox import (  # noqa: E402
    SANDBOX_ROOT,
    sandbox_dir,
    save_quote,
    save_step,
    list_files,
    read_file,
    delete_file,
    ensure_safe_filename,
)


_GREEN = "\033[92m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_PASS = 0
_FAIL = 0


def _check(label, cond, detail=""):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  {_GREEN}✓{_RESET} {label}")
    else:
        _FAIL += 1
        print(f"  {_RED}✗ {label}{_RESET}")
        if detail:
            print(f"      {detail}")


# ─── Tests ──────────────────────────────────────────────────────────


def test_t1_ensure_safe_filename():
    print(f"\n{_BOLD}[T1]{_RESET} ensure_safe_filename — path-traversal hygiene")
    _check("normal stays normal",
           ensure_safe_filename("quote-bahn-001.txt") == "quote-bahn-001.txt")
    _check("path traversal stripped",
           "/" not in ensure_safe_filename("../etc/passwd"))
    _check(".. stripped",
           ".." not in ensure_safe_filename("foo/../bar"))
    _check("special chars normalized",
           ensure_safe_filename("hi!@#$%") == "hi-")
    _check("empty -> 'unnamed'",
           ensure_safe_filename("") == "unnamed")


def test_t2_save_quote():
    print(f"\n{_BOLD}[T2]{_RESET} save_quote — verbatim + source-paired")
    fname = save_quote(
        chat_id="testchat_t2",
        turn_id="abc12345",
        source_url="https://www.bahn.de/deutschlandticket",
        quote_text="Das Deutschland-Ticket kostet 63 Euro pro Monat.",
        purpose="D-Ticket Preis verification",
    )
    _check(f"returned filename: {fname!r}",
           fname.startswith("quote-bahn") and "-abc12345-" in fname)
    _check("filename ends .txt", fname.endswith(".txt"))

    # Read it back
    content = read_file("testchat_t2", fname)
    _check("file is readable", content is not None)
    text = content.decode("utf-8") if content else ""
    _check("contains SOURCE header",
           "SOURCE: https://www.bahn.de/deutschlandticket" in text)
    _check("contains FETCHED iso timestamp",
           "FETCHED: " in text)
    _check("contains PURPOSE",
           "PURPOSE: D-Ticket Preis verification" in text)
    _check("contains the verbatim quote",
           "Das Deutschland-Ticket kostet 63 Euro pro Monat." in text)
    _check("QUOTE section delimited",
           "QUOTE:\n---\n" in text and text.endswith("---\n"))


def test_t3_save_quote_rejects_empty():
    print(f"\n{_BOLD}[T3]{_RESET} save_quote rejects empty / missing source")
    threw = False
    try:
        save_quote("c", "t", "https://x.com", "")
    except ValueError:
        threw = True
    _check("empty quote rejected", threw)

    threw = False
    try:
        save_quote("c", "t", "", "some text")
    except ValueError:
        threw = True
    _check("missing source rejected", threw)


def test_t4_save_step():
    print(f"\n{_BOLD}[T4]{_RESET} save_step — vectoryz artifact with naming")
    fname = save_step(
        chat_id="testchat_t4",
        turn_id="def67890",
        kind="fetched-html",
        content=b"<html><body>hi</body></html>",
        ext="html",
        purpose="Heubach official page raw",
    )
    _check(f"filename: {fname!r}", fname.startswith("step-def67890"))
    _check("filename has kind", "fetched-html" in fname)
    _check("filename has .html ext", fname.endswith(".html"))

    content = read_file("testchat_t4", fname)
    _check("readable", content is not None)
    text = content.decode("utf-8") if content else ""
    _check("text artifact has STEP header", "# STEP ARTIFACT" in text)
    _check("header has TURN", "# TURN: def67890" in text)
    _check("header has KIND", "# KIND: fetched-html" in text)
    _check("body present after header", "<html><body>hi</body></html>" in text)


def test_t5_save_step_binary():
    print(f"\n{_BOLD}[T5]{_RESET} save_step binary content — meta in sidecar")
    fname = save_step(
        chat_id="testchat_t5",
        turn_id="bin12345",
        kind="pdf-dump",
        content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,
        ext="png",
        purpose="charts from PDF",
    )
    _check("binary filename created", fname.endswith(".png"))
    raw = read_file("testchat_t5", fname)
    _check("binary content preserved", raw == b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    # Meta sidecar
    meta = read_file("testchat_t5", fname + ".meta")
    _check("meta sidecar created", meta is not None)
    if meta:
        meta_text = meta.decode("utf-8")
        _check("meta has purpose", "purpose=charts from PDF" in meta_text)


def test_t6_list_files_sorted():
    print(f"\n{_BOLD}[T6]{_RESET} list_files — newest first, excludes .meta")
    chat = "testchat_t6"
    # Create three files with small delays
    import time
    f1 = save_quote(chat, "t1", "https://a.com", "first quote")
    time.sleep(0.05)
    f2 = save_step(chat, "t1", "code", b"print('hi')", ext="py")
    time.sleep(0.05)
    f3 = save_quote(chat, "t2", "https://b.com", "second quote")

    files = list_files(chat)
    _check(f"3 files listed (got {len(files)})", len(files) == 3)
    _check("newest first (f3)", files[0]["filename"] == f3)
    _check("middle (f2)", files[1]["filename"] == f2)
    _check("oldest last (f1)", files[2]["filename"] == f1)
    _check("kinds correct",
           files[0]["kind"] == "quote" and files[1]["kind"] == "step")
    _check("size field present", all("size" in f for f in files))
    _check("created_at ISO format",
           all(f["created_at"].endswith("Z") for f in files))
    # No .meta files in main listing
    _check(".meta excluded", all(not f["filename"].endswith(".meta") for f in files))


def test_t7_read_file_path_traversal_blocked():
    print(f"\n{_BOLD}[T7]{_RESET} read_file blocks path traversal")
    chat = "testchat_t7"
    save_quote(chat, "t", "https://x.com", "real quote")
    _check("'../passwd' blocked", read_file(chat, "../passwd") is None)
    _check("'..' blocked", read_file(chat, "..") is None)
    _check("missing file -> None", read_file(chat, "nonexistent.txt") is None)


def test_t8_delete_file():
    print(f"\n{_BOLD}[T8]{_RESET} delete_file removes file + .meta sidecar")
    chat = "testchat_t8"
    fname = save_step(chat, "t", "binary", b"\x00\x01", ext="bin",
                       purpose="test binary")
    # Verify both exist
    _check("file exists pre-delete", read_file(chat, fname) is not None)
    _check("meta exists pre-delete", read_file(chat, fname + ".meta") is not None)
    # Delete
    ok = delete_file(chat, fname)
    _check("delete returns True", ok is True)
    _check("file gone", read_file(chat, fname) is None)
    _check("meta sidecar gone", read_file(chat, fname + ".meta") is None)
    _check("re-delete returns False", delete_file(chat, fname) is False)


def test_t9_chat_isolation():
    print(f"\n{_BOLD}[T9]{_RESET} chat_id isolation — sandboxes are per-chat")
    save_quote("chatA", "t", "https://x.com", "A's quote")
    save_quote("chatB", "t", "https://x.com", "B's quote")
    a_files = list_files("chatA")
    b_files = list_files("chatB")
    _check("chatA has 1 file", len(a_files) == 1)
    _check("chatB has 1 file", len(b_files) == 1)
    a_content = read_file("chatA", a_files[0]["filename"])
    _check("chatA content matches",
           a_content and b"A's quote" in a_content)


def test_t10_invalid_chat_id_rejected():
    print(f"\n{_BOLD}[T10]{_RESET} invalid chat_id rejected")
    threw = False
    try:
        sandbox_dir("../etc")
    except ValueError:
        threw = True
    _check("'../etc' raises ValueError", threw)

    threw = False
    try:
        sandbox_dir("foo/bar")
    except ValueError:
        threw = True
    _check("'foo/bar' raises ValueError", threw)


def main():
    print(f"{_BOLD}sandbox - falsifiable tests · #178{_RESET}")
    print("=" * 75)

    try:
        test_t1_ensure_safe_filename()
        test_t2_save_quote()
        test_t3_save_quote_rejects_empty()
        test_t4_save_step()
        test_t5_save_step_binary()
        test_t6_list_files_sorted()
        test_t7_read_file_path_traversal_blocked()
        test_t8_delete_file()
        test_t9_chat_isolation()
        test_t10_invalid_chat_id_rejected()
    finally:
        # cleanup test sandbox root
        try:
            shutil.rmtree(_tmp, ignore_errors=True)
        except Exception:
            pass

    print()
    print("=" * 75)
    total = _PASS + _FAIL
    color = _GREEN if _FAIL == 0 else _RED
    print(f"{color}{_BOLD}sandbox result: {_PASS}/{total} pass, {_FAIL} fail{_RESET}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
