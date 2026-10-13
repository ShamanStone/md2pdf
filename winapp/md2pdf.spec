# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the md2pdf Windows GUI app (one-folder build).
# Run from the md2pdf\ project folder:  python -m PyInstaller --noconfirm winapp\md2pdf.spec
#
# Paths in a .spec are resolved relative to the spec file's own directory, so we
# anchor everything to SPECPATH (= ...\md2pdf\winapp) and its parent (the project
# root, = ...\md2pdf) to stay correct regardless of the current directory.
import os
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = SPECPATH                        # ...\md2pdf\winapp
ROOT = os.path.dirname(SPEC_DIR)           # ...\md2pdf
APP = os.path.join(SPEC_DIR, "app.py")
TEMPLATES = os.path.join(ROOT, "templates")

# markdown extensions and pygments styles/lexers are imported by *name* at
# runtime, so PyInstaller can't see them statically — collect them explicitly.
hiddenimports = collect_submodules("markdown")
hiddenimports += collect_submodules("pygments")
hiddenimports += ["websocket"]

a = Analysis(
    [APP],
    pathex=[ROOT],                         # make md2pdf_core and the winapp package importable
    binaries=[],
    datas=[(TEMPLATES, "templates")],      # bundle the built-in templates
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # The app never uses weasyprint or its native stack — exclude to stay small.
    excludes=["weasyprint", "cffi", "cairocffi", "cairosvg", "pydyf", "tinycss2", "cssselect2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="md2pdf",
    debug=False,
    strip=False,
    upx=False,
    console=False,            # windowed GUI (no console window)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="md2pdf",
)
