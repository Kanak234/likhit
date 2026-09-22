"""
build_app.py - Likhit ka standalone app banana (Python ke bina chalne wala).

Kaise: python build_app.py
Result: dist/Likhit (Linux), dist/Likhit.exe (Windows), dist/Likhit.app (macOS)

Dhyaan: PyInstaller jis OS par chalta hai usi ka app banata hai. Windows ka
.exe Windows par, Mac ka .app Mac par banega. Tesseract app ke andar nahi
aata; bina-AI mode ke liye use alag install karna padta hai (README dekho).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# python-docx apni template files "docx/parts/../templates" raaste se dhoondta
# hai. Bundle ke andar docx/parts naam ka folder hi nahi hota (code zip mein
# chala jaata hai), isliye ye raasta toot jaata hai. Ek chhoti placeholder
# file se wo folder ban jaata hai aur raasta chal jaata hai.
KEEP = ROOT / "build" / "docx_parts_keep.txt"
KEEP.parent.mkdir(exist_ok=True)
KEEP.write_text("placeholder so docx/parts exists inside the bundle\n")
sep = ";" if sys.platform.startswith("win") else ":"

try:
    import PyInstaller  # noqa: F401  pehle se install hai toh dobara nahi
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller", "-q"])
cmd = [
    sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
    "--name", "Likhit", "--windowed", "--noconfirm", "--clean",
    # assets folder (logo) app ke andar saath jaata hai
    "--add-data", f"{ROOT / 'assets'}{sep}assets",
    "--icon", str(ROOT / "assets" / "logo-light-bg-256.png"),
    # python-docx apne khaali Word templates data files mein rakhta hai;
    # inke bina header/footer banate waqt app crash hota hai
    "--collect-data", "docx",
    "--add-data", f"{KEEP}{sep}docx/parts",
]
if sys.platform.startswith("linux"):
    cmd.append("--onefile")
subprocess.check_call(cmd)
print("\nDone. Look inside the dist/ folder.")
