# Likhit: Product Requirements

**Owner:** Kanak Prabhakar · **Version:** 1.1 · **Status:** built and tested

## The problem

Students and teachers write a lot by hand: class notes, lab records, rough drafts, answers. Getting that into Word usually means typing it all again. Phone scanner apps help, but most of them need an account and internet, send your pages to someone's cloud, and don't work at all on a desktop without a phone.

## What we're building

A desktop app for Windows, Linux and macOS that takes photos or scanned PDFs of handwritten pages and produces a Word (.docx) file you can edit.

It should work with whatever the user has:

- an API key for a cloud AI service, **or**
- a local AI model on their own computer (no internet), **or**
- nothing AI-related at all (plain OCR).

## Who it's for

- Students turning notes into assignments or study material.
- Teachers digitising handwritten question papers or feedback.
- Anyone on a slow or unreliable connection who still wants the job done offline.

## Goals

- One app, same look, on all three operating systems.
- Automatic choice of reading method in this order: cloud AI → local LLM → OCR without AI.
- The user can always see and fix the text before it becomes a Word file.
- The Word file uses real headings and lists, not just plain text.
- After the first setup, it works with no internet (local LLM or OCR mode).

## Not in scope for 1.0

- Live pen input or drawing tablets.
- Recognising tables and diagrams as structured Word tables.
- Syncing to Google Drive or OneDrive.
- A phone app.

## Features

| # | Feature | Details |
|---|---|---|
| F1 | Add pages | PNG, JPG, BMP, TIFF, WEBP, GIF, and PDF (each PDF page becomes a page). Multiple at once. |
| F2 | Order pages | Move up/down, remove. |
| F3 | Preview | The selected photo is shown next to its text. |
| F4 | Read handwriting | Runs in the background; the window stays usable and shows progress. |
| F5 | Auto engine choice | Cloud if a key exists, else a local vision model, else Tesseract. |
| F6 | Manual engine choice | "Read with" menu forces one method, with no silent fallback. |
| F7 | Edit text | Text box per page. `[?]` marks unclear words and is highlighted. |
| F8 | Read one page again | Re-runs only the selected page. |
| F9 | Save as Word | Headings, bullets, paragraphs, bold; optional original photo under each page. |
| F10 | Settings | Provider, key, model, custom base URL, Ollama/LM Studio address, OCR language, Tesseract path. Saved between runs. |
| F11 | Watermark | KP logo in the app header and in every Word page header. |
| F12 | Terminal mode | `python main.py files... -o out.docx --mode ...` for batch use. |

## How it should behave

- On start, the top bar shows what's available (key, local model name, Tesseract) within about two seconds.
- "Read handwriting" only reads pages that don't have text yet. If every page already has text, it asks before overwriting edits.
- If a single page fails (network drop, timeout), the others still finish, and the user sees which page failed and why.
- In Auto mode, if a method fails while reading (for example a saved key but no internet), that page is read again with the next ready method, and the failed method is skipped for the rest of the run. The user is told once which method took over. A method chosen by hand still never falls back.
- A page that could not be read keeps its place in the Word file as a short grey note, so the page order stays correct.
- If no method is available, the message lists all three reasons and what to do about each.
- Photos are rotated using their EXIF data, so sideways phone photos read correctly.
- Save asks for a location, remembers the folder, and offers to open the file.

## Edge cases

- Blank or unreadable page: the text becomes `[no text found]` in the window; in the Word file it becomes a grey note, not body text.
- Page with very little writing (one line, just a heading): the offline OCR must still read it.
- A local server that answers with something other than JSON (another program on that port): treated as "not available", never a crash.
- Very large PDFs: pages are rendered only when needed, so memory stays flat however many pages there are.
- Terminal mode where every page fails: no Word file is written, and the exit code says so.
- Very large photos are shrunk before sending, to keep uploads quick and cheap.
- The Word file is open in Word while saving: clear message, nothing lost.
- A wrong or expired API key: clear message, not a stack trace.
- Only text-only local models installed (for example `llama3`): they are skipped, because they cannot see images. Embedding models in LM Studio are skipped too.

## Acceptance criteria

- [x] Runs on Windows, Linux and macOS from the same code.
- [x] With a key, uses cloud AI; without a key but with a local vision model, uses that; with neither, uses Tesseract.
- [x] Produces a .docx that opens in Word and LibreOffice, with headings and lists styled properly.
- [x] Every page header in the Word file carries the KP logo.
- [x] Works offline after first setup (local LLM or Tesseract).
- [x] Automated tests pass (31 in v1.1).
- [x] v1.1: saved key with no internet still reads pages in Auto mode (falls back).
- [x] v1.1: the API key is kept in the system's secure store when one is available.
