#!/usr/bin/env python3
"""Tkinter GUI for md2pdf: pick a Markdown file, choose a template, convert to PDF.

Rendering runs on a worker thread (tkinter is not thread-safe); all UI updates
are marshalled back to the main thread with root.after(). PDF generation uses the
system Chromium browser (see chromium_pdf), so no Python or GTK is needed on the
machine running the built .exe.
"""
from __future__ import annotations

import os
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, ttk

from md2pdf_core import app_dirs, build_html_document, discover_templates
from winapp.chromium_pdf import find_browser, html_to_pdf

APP_TITLE = "md2pdf — Markdown to PDF"
DEFAULT_TEMPLATE = "default"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.minsize(560, 300)

        self.templates = discover_templates([app_dirs()[1]])
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.template_var = tk.StringVar(
            value=DEFAULT_TEMPLATE if DEFAULT_TEMPLATE in self.templates
            else (next(iter(self.templates), ""))
        )
        self.toc_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Choose a Markdown file to begin.")
        self._last_out: Path | None = None

        self._build_ui()

    # ---- layout --------------------------------------------------------- #
    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 6}
        frm = ttk.Frame(self.root, padding=12)
        frm.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Markdown file:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.input_var).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Browse…", command=self._pick_input).grid(row=0, column=2, **pad)

        ttk.Label(frm, text="Template:").grid(row=1, column=0, sticky="w", **pad)
        self.template_box = ttk.Combobox(
            frm, textvariable=self.template_var, state="readonly",
            values=list(self.templates.keys()),
        )
        self.template_box.grid(row=1, column=1, sticky="ew", **pad)

        ttk.Label(frm, text="Output PDF:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.output_var).grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Save as…", command=self._pick_output).grid(row=2, column=2, **pad)

        ttk.Checkbutton(
            frm, text="Insert table of contents", variable=self.toc_var
        ).grid(row=3, column=1, sticky="w", **pad)

        self.convert_btn = ttk.Button(frm, text="Convert", command=self._on_convert)
        self.convert_btn.grid(row=4, column=1, sticky="e", **pad)

        self.status_lbl = ttk.Label(frm, textvariable=self.status_var, wraplength=520)
        self.status_lbl.grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        self.open_btn = ttk.Button(frm, text="Open output folder", command=self._open_folder)
        self.open_btn.grid(row=6, column=1, sticky="e", **pad)
        self.open_btn.grid_remove()

        if not self.templates:
            self._set_status("No templates found next to the app.")
            self.convert_btn.state(["disabled"])

    # ---- actions -------------------------------------------------------- #
    def _pick_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose a Markdown file",
            filetypes=[("Markdown", "*.md *.markdown"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)
            self.output_var.set(str(Path(path).with_suffix(".pdf")))

    def _pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save PDF as", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if path:
            self.output_var.set(path)

    def _on_convert(self) -> None:
        md = self.input_var.get().strip()
        out = self.output_var.get().strip()
        name = self.template_var.get().strip()
        if not md or not Path(md).is_file():
            self._set_status("Please choose a valid Markdown file.")
            return
        if not out:
            out = str(Path(md).with_suffix(".pdf"))
            self.output_var.set(out)
        if name not in self.templates:
            self._set_status("Please choose a template.")
            return

        self.convert_btn.state(["disabled"])
        self.open_btn.grid_remove()
        self._set_status("Converting…")
        threading.Thread(
            target=self._worker,
            args=(Path(md), Path(out), self.templates[name], self.toc_var.get()),
            daemon=True,
        ).start()

    def _worker(self, md_path: Path, out_path: Path, template_dir: Path, want_toc: bool) -> None:
        try:
            browser = find_browser()
            if not browser:
                raise RuntimeError(
                    "Microsoft Edge or Google Chrome is required to create PDFs. "
                    "Edge ships with Windows 10/11 — please ensure it is installed."
                )
            html, manifest = build_html_document(md_path, template_dir, want_toc=want_toc)
            html_to_pdf(html, out_path, md_path.parent, manifest, browser)
            self._done(out_path)
        except Exception:
            self._fail(traceback.format_exc())

    # ---- thread-safe UI updates ---------------------------------------- #
    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _done(self, out_path: Path) -> None:
        def apply() -> None:
            self._last_out = out_path
            self._set_status(f"Done — wrote {out_path}")
            self.convert_btn.state(["!disabled"])
            self.open_btn.grid()
        self.root.after(0, apply)

    def _fail(self, detail: str) -> None:
        def apply() -> None:
            first = detail.strip().splitlines()[-1] if detail.strip() else "Conversion failed."
            self._set_status(f"Failed: {first}")
            self.convert_btn.state(["!disabled"])
        self.root.after(0, apply)

    def _open_folder(self) -> None:
        if self._last_out:
            folder = self._last_out.parent
            try:
                os.startfile(str(folder))  # Windows
            except AttributeError:
                self._set_status(f"Output folder: {folder}")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
