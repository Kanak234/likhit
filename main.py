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
import sys
from pathlib import Path

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
            print(f"failed: {e}")

    out = build_document([p for p in pages if p.text], args.output,
                         include_scans=args.include_scans)
    print(f"Saved: {out}")
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
