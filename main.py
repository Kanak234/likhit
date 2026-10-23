"""
main.py - Likhit shuru karne ki jagah.

Do tareeke:
  python main.py                              -> window (GUI) khulti hai
  python main.py notes1.jpg notes2.jpg -o out.docx [--mode auto|cloud|local|offline]
                                              -> bina window ke, terminal se

Why CLI bhi: bahut saare pages ek saath convert karne ke liye, aur testing ke
liye (tests/ folder isi raaste se poora pipeline check karta hai).

Flow: GUI -> likhit/ui.py.  CLI -> imaging.load_pages -> engines.choose_engine
-> engine.recognize -> docx_writer.build_document.
"""

import argparse
import os
import sys
from pathlib import Path

# WHY: a PyInstaller --windowed build (Windows Likhit.exe) has NO console, so
#      sys.stdout / sys.stderr are None and the first print() in CLI mode crashes.
#      Point them at a log file next to the user's data instead, so CLI mode
#      (used by the MSIX smoke test and batch conversions) works from the GUI exe.
if sys.stdout is None or sys.stderr is None:
    _log = open(os.path.join(os.path.expanduser("~"), "likhit-cli.log"), "a", encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

# Chahe kisi bhi folder se chalao, likhit package mil jaaye
sys.path.insert(0, str(Path(__file__).resolve().parent))


def run_cli(args):
    from likhit import engines, imaging
    from likhit.docx_writer import Page, build_document
    from likhit.settings import load_settings

    settings = load_settings()
    pages = []
    for path in args.files:
        for name, img in imaging.load_pages(path):
            pages.append(Page(name=name, image=img))
    if not pages:
        print("No pages found.")
        return 1

    try:
        engine = engines.choose_engine(settings, args.mode)
    except engines.EngineError as e:
        print(f"Can't start reading:\n{e}")
        return 2
    print(f"Using {engine.label}")

    failed = 0
    for n, page in enumerate(pages, start=1):
        print(f"  [{n}/{len(pages)}] {page.name} ...", end=" ", flush=True)
        try:
            page.text = engine.recognize(page.image)
            print("ok")
        except engines.EngineError as e:
            failed += 1
            page.error = str(e)
            print(f"failed: {e}")
        # v1.1 fix: pehle sirf EngineError pakadte the; koi aur galti (toota
        # PDF page, anjaan bug) poora batch crash kar deti thi. Ab wo page
        # fail maana jaata hai aur baaki chalte rehte hain, jaise GUI mein.
        except Exception as e:  # noqa: BLE001
            failed += 1
            page.error = f"Unexpected problem: {e}"
            print(f"failed: {page.error}")

    # v1.1 fix: saare pages fail hue toh khaali Word file banane ka koi matlab
    # nahi; pehle ye chupchaap ban jaati thi aur user sochta ki kaam ho gaya.
    if failed == len(pages):
        print("Nothing could be read, so no Word file was saved.")
        return 3

    # v1.1 fix: fail hue pages ab gayab nahi hote. build_document() unki jagah
    # ek note likhta hai (docx_writer ka Page.error), taaki page kram bana rahe.
    out = build_document(pages, args.output, include_scans=args.include_scans)
    print(f"Saved: {out}")
    if failed:
        print(f"{failed} of {len(pages)} pages could not be read; they are marked in the file.")
    return 0 if not failed else 3


def main():
    parser = argparse.ArgumentParser(prog="likhit",
                                     description="Handwriting photos to a Word document.")
    parser.add_argument("files", nargs="*", help="photos or PDFs (skip to open the window)")
    parser.add_argument("-o", "--output", default="handwriting.docx")
    parser.add_argument("--mode", choices=["auto", "cloud", "local", "offline"], default=None)
    parser.add_argument("--include-scans", action="store_true",
                        help="put the original photo under each page's text")
    args = parser.parse_args()

    if args.files:
        sys.exit(run_cli(args))

    from likhit.ui import run_app
    run_app()


if __name__ == "__main__":
    main()
