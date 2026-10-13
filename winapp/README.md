# md2pdf — standalone Windows GUI app

A double-click Windows app that converts a Markdown file to a styled PDF using
the same templates as the command-line tool. It is **self-contained**: the people
you share it with need **no Python, no WSL, and no extra installs**.

## How it works (why it's small and portable)

- Markdown → HTML + CSS is done in pure Python (shared with the CLI, in
  `../md2pdf_core.py`).
- HTML → PDF is rendered by the **Microsoft Edge** browser that already ships with
  Windows 10/11 (or Google Chrome if present), driven headlessly via the Chrome
  DevTools Protocol. No browser is bundled, so the app stays small and there is no
  fragile GTK/native dependency.

## Build the app (one time, on Windows)

Requirements on the *build* machine only: Python 3 (the `py` launcher) and an
internet connection for `pip`.

1. Open **Command Prompt** or **PowerShell**.
2. `cd` into the project folder (quote the path — it contains a space):
   ```
   cd "C:\Coding\Python\print\Public code\md2pdf"
   ```
3. Run the build script:
   ```
   winapp\build.bat
   ```

This creates a build virtualenv, installs `markdown pygments websocket-client
pyinstaller`, and runs PyInstaller. Output:

```
dist\md2pdf\md2pdf.exe      <- the app
dist\md2pdf\templates\      <- the bundled formats
dist\md2pdf\ ...            <- supporting files
```

## Use it

Double-click **`dist\md2pdf\md2pdf.exe`**:

1. **Browse…** to a `.md` file (the output path auto-fills next to it).
2. Pick a **Template** (default / report / compact / resume / cv).
3. (Optional) tick **Insert table of contents**.
4. **Convert** → the PDF is written; **Open output folder** reveals it.

## Share it

Zip the whole **`dist\md2pdf\`** folder and send it. Recipients unzip and run
`md2pdf.exe` — nothing to install. (The `.exe` is unsigned, so Windows SmartScreen
may show a "More info → Run anyway" prompt the first time.)

## Add your own formats (no rebuild)

Create a `templates\` folder **next to `md2pdf.exe`** and drop a template folder in
it (same two files as the built-ins — `template.toml` + `style.css`). It appears in
the dropdown automatically. A folder with the same name as a built-in overrides it.

## Notes / limitations

- **Edge/Chrome required at run time.** Edge ships with Windows 10/11, so this is
  normally already satisfied. If neither is found the app shows a clear message.
- **Fonts:** the templates reference DejaVu with web-safe fallbacks (Helvetica/
  Arial/Georgia/Times/Courier New). On machines without DejaVu, Chromium uses the
  fallback, so line breaks may shift slightly versus the WSL/weasyprint output.
- **Page numbers** (report, cv) are drawn by Chromium's print footer (centered,
  9 pt, grey) rather than the CSS page box — visually equivalent.
