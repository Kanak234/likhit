"""
imaging.py - photos aur PDF ko padhna, aur har engine ke liye taiyaar karna.

Why: phone ki photo aksar ghoomi hui hoti hai, bahut badi hoti hai, ya halki
roshni mein li gayi hoti hai. AI ko chhoti par saaf JPEG chahiye, aur
Tesseract ko black-and-white jaisi high-contrast image. Ye sab ek jagah
rakha hai taaki engines.py sirf "padhne" ka kaam kare.

Flow: ui.py / main.py file select karte hain -> load_pages() -> har page ek
PIL Image -> engines.py mein to_base64_jpeg() ya for_ocr() se jaata hai.
"""

import base64
import io
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# Kaunsi files hum le sakte hain. PDF tabhi chalega jab PyMuPDF install ho.
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"}

try:
    import pymupdf as fitz  # PyMuPDF; optional hai, na ho toh PDF support band
    PDF_SUPPORTED = True
except ImportError:  # pragma: no cover - depends on install
    try:
        import fitz  # purane PyMuPDF versions isi naam se aate the
        PDF_SUPPORTED = True
    except ImportError:
        fitz = None
        PDF_SUPPORTED = False


# ---------------------------------------------------------------------------
# Ek file ko ek ya zyada pages mein todna.
# Why: ek photo = ek page, lekin ek PDF mein kai pages ho sakte hain. UI ko
# dono ek jaise dikhne chahiye: bas (naam, image) ki list.
# Flow: result seedha ui.py ke page list mein jaata hai.
# ---------------------------------------------------------------------------
def load_pages(path: str) -> list[tuple[str, Image.Image]]:
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".pdf":
        if not PDF_SUPPORTED:
            raise ValueError(
                "Opening PDFs needs PyMuPDF. Run: pip install pymupdf"
            )
        pages = []
        with fitz.open(p) as doc:
            for i, page in enumerate(doc, start=1):
                # 200 DPI: handwriting ke liye kaafi saaf, par file bahut
                # bhari bhi nahi
                pix = page.get_pixmap(dpi=200)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                pages.append((f"{p.stem} - page {i}", img.convert("RGB")))
        return pages

    if ext in IMAGE_TYPES:
        img = Image.open(p)
        # Phone photos mein rotation EXIF tag mein chhupa hota hai. Ise na
        # sudhaarein toh AI ko text ulta ya tircha dikhega.
        img = ImageOps.exif_transpose(img)
        return [(p.stem, img.convert("RGB"))]

    raise ValueError(f"This file type isn't supported: {ext}")


# ---------------------------------------------------------------------------
# AI (cloud ya local) ke liye image.
# Why: 12 MP ki photo bhejne se upload dheema aur API mehenga hota hai, jabki
# 2000px lambi side handwriting padhne ke liye kaafi hai. JPEG quality 88
# par akshar saaf rehte hain aur size chhota.
# Flow: engines.py ke CloudEngine / OllamaEngine / LMStudioEngine.
# ---------------------------------------------------------------------------
def to_base64_jpeg(img: Image.Image, max_side: int = 2000) -> str:
    im = img.copy()
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# Tesseract (bina AI) ke liye image.
# Why: Tesseract rang aur parchhaai se confuse hota hai. Grayscale +
# auto-contrast + halka sharpen se kaagaz safed aur syahi gaadhi ho jaati
# hai. Chhoti photo ko bada karte hain kyunki Tesseract ~30px oonche
# aksharon par sabse achha chalta hai.
# Flow: engines.TesseractEngine.
# ---------------------------------------------------------------------------
def for_ocr(img: Image.Image) -> Image.Image:
    im = ImageOps.grayscale(img)
    if max(im.size) < 1600:
        scale = 1600 / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=2)
    im = im.filter(ImageFilter.SHARPEN)
    return im


# ---------------------------------------------------------------------------
# Word file mein original scan daalne ke liye PNG bytes.
# Flow: docx_writer.build_document() jab include_scans ON ho.
# ---------------------------------------------------------------------------
def to_png_bytes(img: Image.Image, max_side: int = 1600) -> bytes:
    im = img.copy()
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
