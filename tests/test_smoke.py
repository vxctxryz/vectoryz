"""Smoke test — verify the wrapper package imports cleanly.

Run via:  python -m pytest tests/test_smoke.py
"""

from __future__ import annotations


def test_import_wrapper_v2():
    import wrapper_v2  # noqa: F401


def test_import_core_subpackages():
    from wrapper_v2 import classifier, l0, pipeline, sse, store, verify  # noqa: F401


def test_import_classifier_register_detect():
    from wrapper_v2.classifier import detect_register, RegisterResult
    r = detect_register("hello")
    assert isinstance(r, RegisterResult)
