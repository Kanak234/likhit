# Changelog

## 1.1.0 (2026-09-23)

Fixes from the code review. Nothing in how you use the app changed.

**Reading**
- Auto mode now falls back per page. A saved API key with no internet used to fail every page; now the local model or Tesseract takes over, and you're told once.
- Offline OCR no longer erases pages with little writing. Auto-contrast used to clip the darkest 2% of pixels, which on a sparse page was the ink itself.
- A server answering with something other than JSON (another program on the Ollama or LM Studio port) is treated as "not available" instead of crashing.
- A dropped connection gives a clear message instead of a traceback.
- LM Studio: embedding and text-only models are no longer picked. Newer LM Studio reports which models are vision models, and Likhit now uses that.
- Tesseract errors (for example missing Hindi data) give a clear message in terminal mode too.
- Detecting local models is much faster when many are installed (checks run in parallel).

**Files**
- Large PDFs no longer load every page into memory at once.
- `###` and deeper headings become real Word headings.
- Empty pages and pages that failed show a small grey note in the Word file instead of `[no text found]` or disappearing.
- Terminal mode doesn't write an empty Word file when every page fails.

**Setup and security**
- The API key is stored in the system's password store when available (new dependency: `keyring`). Existing keys move there automatically on the next start, and only after they have been checked.
- `run.sh` / `run.bat` no longer get stuck if the first setup was interrupted.

## 1.0.0 (2026-09-22)

First release.
