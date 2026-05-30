"""Smoke-test: verifies the package imports cleanly."""

def test_import():
    import vectoryz
    assert vectoryz.__version__


def test_pipeline_modules():
    from vectoryz.pipeline import language_detect, pre_search
    # basic sanity
    assert hasattr(language_detect, "detect_language")
    assert hasattr(pre_search, "classify_and_fetch")
