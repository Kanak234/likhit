# Likhit: Technical Design

## Stack and why

| Part | Choice | Reason |
|---|---|---|
| Language | Python 3.10+ | Runs the same on all three systems; good image and document libraries. |
| Window | Tkinter (ttk, "clam" theme) | Comes with Python on Windows and macOS, one package on Linux. No heavy framework to install. |
| Images | Pillow | Rotation fix, resizing, contrast, JPEG/PNG encoding. |
| PDF input | PyMuPDF (optional) | Renders PDF pages to images at 200 DPI. The app still runs without it. |
| Word output | python-docx | Real styles, headers, footers, images. |
| OCR without AI | Tesseract via pytesseract | Mature, offline, free, supports Hindi. |
| HTTP | Python standard library (`urllib`) | No vendor SDKs, so fewer dependencies and one code path for every provider. |

## Structure

```
main.py                 entry: window, or terminal mode when files are given
likhit/
  ui.py                 window, background worker, settings dialog
  engines.py            CloudEngine, OllamaEngine, LMStudioEngine, TesseractEngine, choose_engine()
  imaging.py            load_pages(), to_base64_jpeg(), for_ocr(), to_png_bytes()
  docx_writer.py        Page dataclass, build_document()
  settings.py           Settings dataclass, load/save as JSON
assets/                 KP logo (SVG and PNG, light and dark background versions)
tests/                  unittest suite with fake HTTP servers
build_app.py            PyInstaller build
```

## Data flow

```
photo / PDF
  → imaging.load_pages()          → list of (name, PIL image)
  → engines.choose_engine()       → one engine object
  → engine.recognize(image)       → text with light markers (#, -, **, [?])
  → user edits in the window
  → docx_writer.build_document()  → .docx
```

Every engine has the same shape: `label`, `kind`, and `recognize(image) -> str`. The window doesn't know or care which one is running.

## Choosing an engine

`detect_all()` checks, with a 1.5 second timeout per check:

- API key in Settings, or in `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`.
- Ollama at `/api/tags`, then `/api/show` for each model. Only models whose capabilities include `vision` are kept. Older Ollama builds that don't report capabilities are matched by name (llava, qwen2.5vl, moondream, gemma3 and similar).
- LM Studio at `/v1/models`.
- Tesseract on PATH, in the path from Settings, or in the usual install folders.

In auto mode, `choose_engine()` tries cloud, then local, then offline, and collects the reason each one wasn't possible. A forced mode never falls back, so the user gets exactly what they picked.

## Provider requests

| Provider | Endpoint | Auth | Image field |
|---|---|---|---|
| OpenAI / compatible / LM Studio | `{base}/chat/completions` | `Authorization: Bearer` | `image_url` with a data URL |
| Anthropic | `/v1/messages` | `x-api-key`, `anthropic-version` | `image` block, base64 |
| Gemini | `/v1beta/models/{model}:generateContent` | `x-goog-api-key` | `inline_data` |
| Ollama | `/api/chat` | none | `images` array |

The default models are only starting points. Providers rename models often, so the model name is a plain text field in Settings.

The prompt asks for an exact transcription (no fixing spelling, no summary), paragraphs separated by blank lines, `# ` for headings, `- ` for bullets, and `[?]` after any word the model can't read. `clean_output()` removes code fences and "Here is the transcription" lines that some models add anyway.

## Image preparation

- AI engines: longest side at most 2000 px (1600 for local models, to save RAM), JPEG quality 88.
- Tesseract: grayscale, scaled up if small, auto-contrast, sharpen, page segmentation mode 4.

## Word output

- Body text is Calibri 11. The complex-script font is set to Nirmala UI so Devanagari displays properly.
- `# ` becomes Heading 1, `## ` Heading 2, `- ` List Bullet. Numbered lines keep their own numbers.
- Plain lines next to each other are joined into one paragraph.
- `**text**` becomes bold; `[?]` gets a yellow highlight.
- Header: KP logo (0.32 inch) and "Kanak Prabhakar". Footer: "Converted with Likhit · Page N" using a Word PAGE field.

## Threading

Reading runs on a daemon thread. It sends messages (`engine`, `progress`, `page`, `page_error`, `fatal`, `done`) through a `queue.Queue`. The window checks the queue every 100 ms, because Tkinter must only be touched from the main thread. Buttons are disabled while reading, so pages can't be removed mid-run.

## Settings and security

Settings are stored as JSON in:

- Windows: `%APPDATA%\Likhit\settings.json`
- macOS: `~/Library/Application Support/Likhit/settings.json`
- Linux: `~/.config/likhit/settings.json`

On Linux and macOS the file is set to owner-only (chmod 600). The key is plain text inside it, which is the same approach most desktop tools take. Anyone who shares a computer account should use the environment variable instead. Nothing is sent anywhere except to the provider the user chose, and nothing at all in local or offline mode.

## Packaging

`build_app.py` runs PyInstaller with the `assets` folder and python-docx's template files included. python-docx finds its templates through `docx/parts/../templates`, and that path doesn't exist inside a bundle, so a placeholder file is added to create the `docx/parts` folder. Builds are per system. The Linux build was tested here; the Windows and macOS builds use the same script but have to be built on those systems.

## Trade-offs

- **Tkinter instead of Qt:** smaller download and no licensing questions, but less styling freedom. The "clam" theme with custom colours gives a consistent look.
- **No vendor SDKs:** we handle each provider's JSON format ourselves (about 60 lines), but we don't pull in large dependencies.
- **Tesseract on handwriting:** weak compared to AI. It's there so the app still does something with zero AI, and the README says so plainly.

## Testing

`python -m unittest discover -s tests -v`, 16 tests:

- output clean-up;
- Word formatting, logo in header, embedded scans;
- engine choice order and error messages;
- a fake Ollama server (vision filtering and the request shape);
- a fake OpenAI-compatible server (auth header and image data URL);
- Anthropic and Gemini request shapes;
- 401 handling;
- PDF page loading;
- real Tesseract OCR;
- the terminal mode end to end.
