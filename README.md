<p align="center"><img src="assets/logo-light-bg-128.png" width="72" alt="KP logo"></p>

# Likhit

Likhit turns photos of handwritten pages into an editable Word document. It runs on Windows, Linux and macOS.

It can read handwriting in three ways and picks the best one you have:

1. **Cloud AI.** If you paste an API key (OpenAI, Claude, Gemini, or any OpenAI-compatible service), Likhit uses it. This gives the best accuracy.
2. **Local LLM.** No key? Likhit looks for a vision model running on your own computer through Ollama or LM Studio. Nothing leaves your machine and no internet is needed.
3. **Without AI.** If neither is available, it falls back to Tesseract OCR. Tesseract is fast and fully offline, but it was built for printed text, so messy handwriting will need more correcting.

You can also pick one of these by hand from the "Read with" menu.

## Getting started

You need Python 3.10 or newer.

**Windows:** double-click `run.bat`.
**Linux / macOS:** open a terminal in this folder and run `./run.sh`.

The first run creates a private Python environment and installs five packages, so it needs internet once. After that the app starts straight away, even offline. If that first setup gets cut off, just run it again; it picks up where it failed.

On Linux you may also need Tkinter: `sudo apt install python3-tk` (Debian/Ubuntu) or `sudo dnf install python3-tkinter` (Fedora).

### Setting up a reading method

You only need one of these, but you can have all three.

**Cloud AI:** open Settings, choose a provider, paste your key. Leave "Model" empty to use the default, or type a model name if you want a specific one. The key is saved only on your computer, in the system's password store (Credential Manager, Keychain, or Secret Service on Linux) when one is available. In Auto mode, if the key doesn't work at the moment (for example no internet), Likhit reads the pages with your local model or Tesseract instead and tells you.

**Local LLM (Ollama):** install Ollama from ollama.com, then pull a model that can see images:

```
ollama pull qwen2.5vl:3b
```

Likhit finds it on its own. Bigger models (for example `qwen2.5vl:7b`) read better but need more RAM. LM Studio also works: load a vision model and start its local server.

**Without AI (Tesseract):**

- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki. If Likhit can't find it, put the path to `tesseract.exe` in Settings.
- macOS: `brew install tesseract`
- Linux: `sudo apt install tesseract-ocr`

For Hindi, also install the Hindi language data (`tesseract-ocr-hin` on Linux) and set the OCR language to `hin` or `eng+hin`.

## Using it

1. Click **+ Add photos** and choose one or more photos (or PDFs of scanned pages).
2. Put the pages in the right order with the arrow buttons.
3. Click **Read handwriting**.
4. Check the text on the right. Anything the AI wasn't sure about is marked `[?]` and highlighted. Fix it directly in the box.
5. Click **Save as Word**. Tick "Include original photos" if you want each photo under its text.

Shortcuts: Ctrl+O add photos, Ctrl+R read, Ctrl+S save (Cmd on a Mac).

### From the terminal

```
python main.py page1.jpg page2.jpg -o notes.docx
python main.py scan.pdf -o scan.docx --mode local --include-scans
```

`--mode` can be `auto`, `cloud`, `local` or `offline`.

## What ends up in the Word file

- Headings become real Word headings, so you can add a table of contents.
- Bullet points become a real bulleted list.
- Lines that belong to one paragraph are joined back together.
- Unclear words stay highlighted in yellow so you can find them later.
- Each page starts on a new page in Word. The header carries the KP logo and the footer has page numbers.

## Making a standalone app

```
python build_app.py
```

This builds an app in `dist/` that runs without Python installed. It builds for the system you run it on, so build the Windows version on Windows and the Mac version on a Mac. Tesseract is not bundled inside; install it separately if you want the no-AI mode.

## Running the tests

```
python -m unittest discover -s tests -v
```

The tests use small fake servers in place of OpenAI and Ollama, so they don't need a key or a model.

## Common problems

| What you see | What to do |
| --- | --- |
| "No reading method is ready yet" | None of the three methods is set up. Add a key, start Ollama, or install Tesseract. |
| "The API key was rejected" | The key is wrong, expired, or doesn't have access to that model. |
| "No local model" in the top bar | Ollama isn't running, or you only have text models. Pull a vision model. |
| Can't save the Word file | It's open in Word. Close it and save again. |
| PDFs don't show up in the file picker | Install PyMuPDF: `pip install pymupdf` |
| "Switched reading method" message | The first method failed (often no internet). The pages were read with the next one. |
| Tesseract says language data may be missing | Install the language pack (for example `tesseract-ocr-hin`) or change the OCR language in Settings. |

## Project layout

```
main.py              start here (window or terminal)
likhit/ui.py         the window
likhit/engines.py    cloud AI, local LLM and Tesseract, plus choosing between them
likhit/imaging.py    loading photos/PDFs and preparing them for each engine
likhit/docx_writer.py  building the Word file
likhit/settings.py   saving your settings
docs/                PRD, technical design, UI brief
tests/               automated tests
```

---

## Verified

- **Test command:** `python -m pytest tests -q` (or `python -m unittest discover -s tests -v`)
- **Result:** 31 tests pass (needs `tesseract-ocr` for the offline OCR tests)
- **Install Tesseract on Debian/Ubuntu:** `sudo apt install tesseract-ocr`

---

## License

GPL-3.0-or-later — see [LICENSE](LICENSE). Copyright (c) 2026 Kanak Prabhakar.

---

Made by **Kanak Prabhakar** · [kanakprabhakar.online](https://kanakprabhakar.online) · GitHub [@Kanak234](https://github.com/Kanak234)
