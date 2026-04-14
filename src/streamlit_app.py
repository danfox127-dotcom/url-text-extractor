"""Compatibility wrapper so Streamlit can run the app via src/streamlit_app.py.

This imports the top-level `streamlit_app.py` in the repo root so the
Space/legacy entrypoint `src/streamlit_app.py` continues to work even
after we removed the duplicate source file.
"""
import sys
import os

# Ensure project root is on sys.path so we can import the root-level module
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Importing `streamlit_app` executes the Streamlit app (it defines UI at import)
from streamlit_app import *  # noqa: F401,F403
