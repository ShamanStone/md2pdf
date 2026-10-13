#!/usr/bin/env python3
"""Markdown -> PDF converter with switchable, file-based format templates.

Pipeline: markdown -> HTML (python-markdown) -> styled HTML -> PDF (weasyprint).

A "format" is a template: a directory under templates/ holding
  - template.toml : page geometry + fonts + metadata the script reads
  - style.css     : the visual theme (headings, tables, code, spacing, ...)

Switch formats with --template NAME. Add a new format by copying a template
folder and editing its two files; it is auto-discovered, no code change needed.

All Markdown/template/CSS logic lives in md2pdf_core (engine-independent and
weasyprint-free, so the Windows app under winapp/ can share it). This file is
the WSL command-line tool and is the only one that imports weasyprint.

Usage:
    python md2pdf.py INPUT.md [-o OUT.pdf] [-t TEMPLATE]
    python md2pdf.py --list-templates
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from weasyprint import HTML

from md2pdf_core import (
    build_html_document,
    discover_templates,
    print_template_list,
)


# --------------------------------------------------------------------------- #
# Conversion (weasyprint engine)
# --------------------------------------------------------------------------- #
def convert(
    md_path: Path,
    out_path: Path,
    template_dir: Path,
    *,
    title: str | None = None,
    extra_css: Path | None = None,
    want_toc: bool = False,
) -> None:
    html, _ = build_html_document(
        md_path, template_dir, title=title, want_toc=want_toc, extra_css=extra_css
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(out_path))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a Markdown file to PDF using a named format template."
    )
    parser.add_argument("input", nargs="?", help="input Markdown (.md) file")
    parser.add_argument("-o", "--out", help="output PDF path (default: <input>.pdf)")
    parser.add_argument(
        "-t", "--template", default="default", help="template name (default: default)"
    )
    parser.add_argument(
        "--list-templates", action="store_true", help="list templates and exit"
    )
    parser.add_argument(
        "--templates-dir",
        action="append",
        default=[],
        help="extra directory of user templates (repeatable)",
    )
    parser.add_argument("--title", help="override the document title")
    parser.add_argument("--extra-css", help="append an ad-hoc stylesheet last")
    parser.add_argument(
        "--toc", action="store_true", help="insert a generated table of contents"
    )
    args = parser.parse_args(argv)

    extra_dirs = [Path(d) for d in args.templates_dir]
    templates = discover_templates(extra_dirs)

    if args.list_templates:
        print_template_list(templates)
        return 0

    if not args.input:
        parser.error("INPUT.md is required (or use --list-templates)")

    if args.template not in templates:
        avail = ", ".join(templates) or "(none)"
        parser.error(f"unknown template '{args.template}'. Available: {avail}")

    md_path = Path(args.input)
    if not md_path.is_file():
        parser.error(f"input file not found: {md_path}")

    out_path = Path(args.out) if args.out else md_path.with_suffix(".pdf")

    convert(
        md_path,
        out_path,
        templates[args.template],
        title=args.title,
        extra_css=Path(args.extra_css) if args.extra_css else None,
        want_toc=args.toc,
    )
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
