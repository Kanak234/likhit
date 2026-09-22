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
from functools import lru_cache
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
        # v1.1 fix: pehle saare pages turant 200 DPI par render hokar RAM mein
        # rakhe jaate the. A4 ka ek page ~11 MB, toh 100 page ka PDF ~1 GB.
        # Ab sirf page count padhte hain; har page ek LazyPdfPage hai jo tab
        # render hota hai jab koi use sach mein dekhe (preview, AI, Word).
        with fitz.open(p) as doc:
            count = doc.page_count
        resolved = str(p.resolve())
        return [(f"{p.stem} - page {i + 1}", LazyPdfPage(resolved, i)) for i in range(count)]

    if ext in IMAGE_TYPES:
        img = Image.open(p)
        # Phone photos mein rotation EXIF tag mein chhupa hota hai. Ise na
        # sudhaarein toh AI ko text ulta ya tircha dikhega.
        img = ImageOps.exif_transpose(img)
        return [(p.stem, img.convert("RGB"))]

    raise ValueError(f"This file type isn't supported: {ext}")


# ---------------------------------------------------------------------------
# PDF page ko zaroorat par render karna.
# Why lru_cache(maxsize=4): user ek page dekh raha ho toh preview baar-baar
# redraw hota hai (window resize par). Har baar PDF render karna dheema hoga.
# Pichhle 4 page yaad rakhte hain: preview + reading thread dono tez, aur RAM
# 4 page tak hi seemit (~45 MB), chahe PDF kitna bhi bada ho.
# Flow: LazyPdfPage ka koi bhi attribute chhua -> _render_pdf_page().
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _render_pdf_page(path: str, index: int) -> Image.Image:
    with fitz.open(path) as doc:
        # 200 DPI: handwriting ke liye kaafi saaf, par bahut bhaari bhi nahi
        pix = doc[index].get_pixmap(dpi=200)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


class LazyPdfPage:
    """
    PIL Image jaisa dikhne wala chhota object. Iska koi bhi attribute ya
    method (size, copy(), convert()...) maango, ye page render karke asli
    Image ko de deta hai.

    Why proxy aur naya API nahi: ui.py, engines.py aur docx_writer.py sab
    page.image ko PIL Image ki tarah use karte hain. Proxy se unmein ek line
    bhi nahi badalni padi, aur photo wale pages pehle jaise hi chalte hain.
    Jo functions asli Image maangte hain (ImageTk, ImageOps) unhe
    as_pil_image() se asli milta hai.
    """

    def __init__(self, path: str, index: int):
        self.path = path
        self.index = index

    def render(self) -> Image.Image:
        return _render_pdf_page(self.path, self.index)

    def __getattr__(self, name):
        # Sirf tab chalta hai jab attribute is object par nahi mila
        return getattr(self.render(), name)


def as_pil_image(img) -> Image.Image:
    """LazyPdfPage ho toh asli Image do, warna jo mila wahi. Flow: ImageOps /
    ImageTk jaise functions se pehle, jo type check karte hain."""
    return img.render() if isinstance(img, LazyPdfPage) else img


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
    im = ImageOps.grayscale(as_pil_image(img))
    if max(im.size) < 1600:
        scale = 1600 / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    # v1.1 fix: pehle cutoff=2 tha, jo DONO taraf ke 2% pixels kaatta tha.
    # Jis page par syahi 2% se kam ho (ek-do line, sirf heading, khaali
    # jagah zyada) wahan gehre 2% mein syahi hi aa jaati thi, aur wo safed
    # ho kar mit jaati thi -> Tesseract ko khaali page, "[no text found]".
    # (0, 2): gehra (syahi) wala end bilkul nahi kaatte, sirf chamakdar
    # 2% (kaagaz ki parchhai, halka grey) kaat kar kaagaz ko safed karte hain.
    im = ImageOps.autocontrast(im, cutoff=(0, 2))
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
