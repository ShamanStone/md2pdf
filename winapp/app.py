#!/usr/bin/env python3
"""Entry point for the md2pdf Windows GUI app.

Adds the project root (the folder containing md2pdf_core.py) to sys.path so the
shared core imports cleanly whether run from source or frozen by PyInstaller,
then launches the tkinter GUI.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from winapp.gui import main

if __name__ == "__main__":
    main()
