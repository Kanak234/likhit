# AUDIT: Likhit Project

| Line | Description | Verified/GUESS |
|------|-------------|----------------|
| 1 | Language: Python (3.10+) | VERIFIED - main.py, requirements.txt, all source files are Python |
| 2 | GUI library: Tkinter (built-in Python GUI) | VERIFIED - ui.py line 22: `import tkinter as tk`, main.py line 91: `from likhit.ui import run_app` |
| 3 | Entry point: main.py | VERIFIED - main.py `if __name__ == "__main__": main()` |
| 4 | How to run it today: `python main.py` opens GUI; `python main.py files -o out.docx` runs CLI; `./run.sh` (Linux/macOS) or `run.bat` (Windows) | VERIFIED - README.md lines 19-20, main.py |
| 5 | Dependencies: python-docx>=1.1, Pillow>=10.0, pytesseract>=0.3.10, pymupdf>=1.24, keyring>=24.0 | VERIFIED - requirements.txt |
| 6 | Assets folder contains logo images and SVGs | VERIFIED - assets/ directory has logo files including logo-mark.svg |
| 7 | build_app.py uses PyInstaller to build standalone apps | VERIFIED - build_app.py uses PyInstaller |
| 8 | Engines: cloud AI, local LLM (Ollama/LMStudio), Tesseract OCR | VERIFIED - likhit/engines.py |
| 9 | Settings stored in JSON file for API key, provider, local model config | VERIFIED - likhit/settings.py |
| 10 | UI layout: pages list + photo preview + text area + footer controls | VERIFIED - likhit/ui.py _build_body, _build_footer |
| 11 | Background threading for handwriting recognition so UI doesn't freeze | VERIFIED - ui.py uses threading.Thread, queue.Queue for thread-safe UI updates |
| 12 | First-run setup creates Python env and installs 5 packages | GUESS - README says "first run creates private Python environment and installs five packages" |
| 13 | On Linux, python3-tk may be needed: `sudo apt install python3-tk` | VERIFIED - README.md line 24 |
| 14 | Can also run as CLI: `python main.py page1.jpg page2.jpg -o notes.docx` | VERIFIED - README.md lines 61-62, main.py |
| 15 | Tests exist in tests/ folder using fake servers | VERIFIED - README.md lines 85-89 |
| 16 | Standalone app build: `python build_app.py` creates dist/ folder | VERIFIED - README.md lines 77-81, build_app.py |