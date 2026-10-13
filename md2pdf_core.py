#!/usr/bin/env python3
"""Engine-independent core for the md2pdf converter.

This module holds all the Markdown/template/CSS logic shared by:
  - the WSL command-line tool (md2pdf.py), which renders with weasyprint, and
  - the standalone Windows GUI app (winapp/), which renders with headless Chromium.

IMPORTANT: this module must NOT import weasyprint (the Windows app has no GTK and
must never pull it in). It produces a fully self-contained HTML string with the
CSS inlined into <head><style>; each engine turns that HTML into PDF its own way.
"""
from __future__ import annotations

import sys
import tomllib
from html import escape as html_escape
from pathlib import Path

import markdown

# Markdown extensions: tables/fenced code/footnotes (extra), code highlighting,
# table of contents, nicer lists, and typographic quotes.
MD_EXTENSIONS = ["extra", "codehilite", "toc", "sane_lists", "smarty"]
MD_EXTENSION_CONFIGS = {"codehilite": {"guess_lang": False}}


# --------------------------------------------------------------------------- #
# Resource locations (works both from source and when frozen by PyInstaller)
# --------------------------------------------------------------------------- #
def app_dirs() -> tuple[Path, Path]:
    """Return (builtin_templates_dir, user_templates_dir).

    - Frozen (PyInstaller): built-ins live beside the bundled code (sys._MEIPASS);
      user templates live in a `templates/` folder next to the .exe, so end users
      can add formats without rebuilding.
    - From source: both resolve to this package's own templates/ directory.
    """
    if getattr(sys, "frozen", False):
        builtin = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "templates"
        user = Path(sys.executable).parent / "templates"
    else:
        builtin = Path(__file__).resolve().parent / "templates"
        user = builtin
    return builtin, user


# --------------------------------------------------------------------------- #
# Template discovery / loading
# --------------------------------------------------------------------------- #
def discover_templates(extra_dirs: list[Path] | None = None) -> dict[str, Path]:
    """Return {template_name: template_dir}. A dir is a template iff it holds
    template.toml. Later dirs (user-supplied) override built-ins by name."""
    templates: dict[str, Path] = {}
    search_dirs = [app_dirs()[0]] + list(extra_dirs or [])
    for base in search_dirs:
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if (child / "template.toml").is_file():
                templates[child.name] = child
    return templates


def load_template(template_dir: Path) -> tuple[dict, str]:
    """Load (manifest dict, style.css text) for a template directory."""
    with (template_dir / "template.toml").open("rb") as fh:
        manifest = tomllib.load(fh)
    css_path = template_dir / "style.css"
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    return manifest, css


def build_page_css(manifest: dict) -> str:
    """Generate the @page rule and base html/body font rules from the manifest,
    so page geometry stays in sync with the TOML.

    Note: the @bottom-center page-number box is honored by weasyprint. Chromium
    ignores CSS paged-media margin boxes and renders page numbers via its own
    print footer instead (see winapp/chromium_pdf.py); leaving the box here is
    harmless to Chromium and keeps the CSS identical for both engines.
    """
    page = manifest.get("page", {})
    font = manifest.get("font", {})

    size = page.get("size", "A4")
    margin = page.get("margin", "2cm")
    page_numbers = bool(page.get("page_numbers", False))

    page_boxes = ""
    if page_numbers:
        page_boxes = (
            "\n  @bottom-center {\n"
            "    content: counter(page);\n"
            "    font-size: 9pt;\n"
            "    color: #666;\n"
            "  }"
        )

    family = font.get("family", "'DejaVu Sans', Helvetica, Arial, sans-serif")
    size_pt = font.get("size", "11pt")
    line_height = font.get("line_height", "1.5")

    return (
        f"@page {{\n  size: {size};\n  margin: {margin};{page_boxes}\n}}\n"
        f"html {{\n  font-family: {family};\n  font-size: {size_pt};\n"
        f"  line-height: {line_height};\n}}\n"
    )


def code_highlight_css(manifest: dict) -> str:
    """Pygments CSS for highlighted fenced code. Degrades to '' if pygments is
    unavailable so the converter still runs (code just renders unstyled)."""
    style = manifest.get("code", {}).get("style", "default")
    try:
        from pygments.formatters import HtmlFormatter

        return HtmlFormatter(style=style).get_style_defs(".codehilite")
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Markdown -> HTML
# --------------------------------------------------------------------------- #
def md_to_html_body(text: str, want_toc: bool) -> tuple[str, str]:
    """Convert markdown text to an HTML body fragment. Returns (body, title)
    where title is the first H1 if present else ''."""
    md = markdown.Markdown(
        extensions=MD_EXTENSIONS, extension_configs=MD_EXTENSION_CONFIGS
    )
    if want_toc:
        text = "[TOC]\n\n" + text
    body = md.convert(text)
    # python-markdown's toc extension records the first heading tree; grab H1.
    title = ""
    toc_tokens = getattr(md, "toc_tokens", [])
    if toc_tokens:
        title = toc_tokens[0].get("name", "")
    return body, title


def build_html_document(
    md_path: Path,
    template_dir: Path,
    *,
    title: str | None = None,
    want_toc: bool = False,
    extra_css: Path | None = None,
    lang: str = "en",
) -> tuple[str, dict]:
    """Engine-independent. Build a full, self-contained HTML document with the
    template CSS inlined into <head><style>. Returns (html, manifest).

    The CSS is inlined (rather than passed to the renderer separately) so the
    same HTML string works for Chromium, which loads a file:// URL and has no
    out-of-band stylesheet channel. weasyprint honors the inline <style> too.
    """
    manifest, theme_css = load_template(template_dir)
    text = md_path.read_text(encoding="utf-8")
    body, h1_title = md_to_html_body(text, want_toc)

    doc_title = title or h1_title or md_path.stem

    css_parts = [build_page_css(manifest), theme_css, code_highlight_css(manifest)]
    if extra_css and extra_css.is_file():
        css_parts.append(extra_css.read_text(encoding="utf-8"))
    css_text = "\n\n".join(p for p in css_parts if p.strip())

    html = (
        "<!DOCTYPE html>\n"
        f'<html lang="{html_escape(lang, quote=True)}">\n<head>\n'
        '<meta charset="utf-8">\n'
        f"<title>{html_escape(doc_title)}</title>\n"
        f"<style>\n{css_text}\n</style>\n</head>\n"
        f"<body>\n{body}\n</body>\n</html>"
    )
    return html, manifest


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def print_template_list(templates: dict[str, Path]) -> None:
    if not templates:
        print("No templates found.")
        return
    print("Available templates:")
    for name, path in templates.items():
        manifest, _ = load_template(path)
        desc = manifest.get("description", "")
        size = manifest.get("page", {}).get("size", "?")
        print(f"  {name:12s} [{size}]  {desc}")
