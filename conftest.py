"""
pytest automatically loads this file before running tests.
It adds the backend folder to Python's import path, so `from main import app`
works correctly even though test_main.py lives inside the tests/ subfolder.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))