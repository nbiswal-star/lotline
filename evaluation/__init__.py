"""Evaluation-only package for LotLine's scientific validation (docs/validation/).

This package is never imported by application code (``app.py``, ``lotline/``).
Like ``tests/``, it may read ``tests/fixtures/`` because it is evaluation, not
product. Every experiment runs on the committed snapshot or on in-memory copies;
nothing here writes to ``data/``.

Run: ``uv run python -m evaluation.run``
"""
