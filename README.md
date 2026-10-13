# md2pdf — Markdown to PDF with switchable format templates

Convert a Markdown file to PDF, choosing the output **format** from a set of
named templates. Pipeline: Markdown → HTML (`python-markdown`) → PDF
(`weasyprint`).

## Usage

```bash
PY="/mnt/c/Coding/Python/print/venv-wsl/bin/python"
MD="/mnt/c/Coding/Python/print/Public code/md2pdf/md2pdf.py"

# list available formats
"$PY" "$MD" --list-templates

# convert with a chosen format (default output is <input>.pdf next to the input)
"$PY" "$MD" notes.md -t report -o notes.pdf
```

### Options

| Flag | Meaning |
|------|---------|
| `input` | Markdown file to convert (positional) |
| `-o, --out` | Output PDF path (default: `<input>.pdf`) |
| `-t, --template` | Format name (default: `default`) |
| `--list-templates` | Print available formats and exit |
| `--templates-dir DIR` | Add a directory of your own templates (repeatable) |
| `--title` | Override the document title |
| `--extra-css FILE` | Append an extra stylesheet last |
| `--toc` | Insert a generated table of contents |

## Built-in formats

- **default** — clean A4, sans-serif, striped tables. Good for most notes.
- **report** — A4 serif, justified, numbered headings, page numbers. Formal write-ups.
- **compact** — small font, tight margins. Dense cheat-sheets.

## Add your own format

A template is just a folder with two files:

```
templates/<your-name>/
├── template.toml   # page size, margins, fonts, page numbers, code style
└── style.css       # the visual theme
```

1. Copy an existing folder, e.g. `templates/default` → `templates/mytheme`.
2. Edit `template.toml` (set `name`, `description`, `[page]`, `[font]`, `[code]`).
3. Edit `style.css` to taste.
4. Run with `-t mytheme`. It is auto-discovered — no code changes.

`template.toml` keys:

```toml
name = "mytheme"
description = "one-line summary shown by --list-templates"

[page]
size = "A4"            # or "Letter", "A5", "210mm 297mm"
margin = "2cm"         # any CSS margin shorthand
page_numbers = true    # add a centered page number footer

[font]
family = "'DejaVu Serif', Georgia, serif"
size = "11pt"
line_height = "1.6"

[code]
style = "friendly"     # any Pygments style name
```

The `[page]` and `[font]` values are emitted into a generated `@page` / `html`
rule so page geometry stays in sync; everything else lives in `style.css`.

## Dependencies

In the shared venv (`venv-wsl`): `weasyprint`, `markdown`, `pygments`.
`tomllib` is in the Python 3.12 standard library.
