"""Layer 5: presentation view models.

Everything in this package is a pure function of the loaded ``Snapshot`` and
engine ``ScreeningResult`` objects. Nothing here computes a score, outcome,
conflict, barrier or next check; view models only select, order and label
engine output for display. ``app.py`` renders these with Streamlit.
"""
