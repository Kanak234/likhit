"""
engines.py - handwriting padhne wale teen raaste, aur unmein se sahi chunna.

Project ki requirement:
  1. User ne koi AI API key daali hai  -> cloud AI se padho
  2. Key nahi hai, par system par local LLM hai -> use khud dhoondo aur use karo
  3. Dono nahi -> bina AI ke (Tesseract OCR) se padho

Why ek hi file: teeno engines ka "shape" same hai (image do, text lo). Isse
UI ko fark hi nahi padta ki peeche kaun chal raha hai.

Flow: ui.py / main.py -> choose_engine(settings) -> engine.recognize(image)
-> saaf kiya hua text -> docx_writer.py
"""

import json
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request

from . import imaging

# ---------------------------------------------------------------------------
# AI ko diya jaane wala nirdesh (prompt).
# Why: bina saaf nirdesh ke model "Here is the text..." jaisi baatein jodta
# hai, ya galtiyaan "sudhaar" deta hai. Hum chahte hain ki jo likha hai wahi
# aaye, aur jo samajh na aaye wo [?] se mark ho jaaye taaki user check kar
# sake. Headings aur lists ke liye chhote markers maange hain, jinhe
# docx_writer.py asli Word formatting mein badalta hai.
# ---------------------------------------------------------------------------
PROMPT = """Transcribe the handwritten text in this image exactly as written.

Rules:
- Output only the transcription. No introduction, no comments, no code fences.
- Keep the writer's own words and spelling. Do not correct or summarise.
- Keep the original language and script (English, Hindi, Hinglish, anything).
- Join lines that belong to the same paragraph. Put one blank line between paragraphs.
- If a line is clearly a heading, start it with "# ".
- Bullet points start with "- ". Numbered points keep their numbers, like "1. ".
- Underlined or clearly emphasised words may be wrapped in **double stars**.
- If a word cannot be read, write your best guess followed by [?].
- If there is no readable text, output exactly: [no text found]"""

REQUEST_TIMEOUT = 180      # badi image par local model ko time lagta hai
DETECT_TIMEOUT = 1.5       # detection tez hona chahiye, warna app atka lagega

# Har cloud provider ka default model. User Settings mein badal sakta hai,
# kyunki providers naye models laate rehte hain.
DEFAULT_CLOUD_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-5",
    "gemini": "gemini-2.5-flash",
    "openai_compatible": "",
}

# Ollama ke purane versions "capabilities" nahi batate; tab naam se andaaza
VISION_NAME_HINTS = (
    "llava", "vision", "-vl", "vl:", "qwen2.5vl", "qwen3-vl", "moondream",
    "minicpm-v", "gemma3", "bakllava", "granite3.2-vision", "mistral-small3",
    "llama4", "gemma4",
)


class EngineError(Exception):
    """Aisi galti jo user ko seedhe dikhani hai (key galat, server band...)."""


# ---------------------------------------------------------------------------
# Chhota HTTP helper, sirf Python ki standard library se.
# Why: openai/anthropic jaise bhaari SDK install karne ki zaroorat nahi;
# app halka rehta hai aur teeno OS par bina jhanjhat chalta hai.
# Flow: har engine isi se server ko request bhejta hai.
# ---------------------------------------------------------------------------
def _http_json(url, payload=None, headers=None, timeout=REQUEST_TIMEOUT):
    data = None
    hdrs = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        # v1.1 fix: pehle json.loads seedha yahan tha, aur agar port par koi
        # aur program HTML ya kachra lautata (proxy page, dusra server), toh
        # JSONDecodeError bina pakde upar jaata aur detection/CLI crash hota.
        # Ab wo bhi EngineError hai, jise baaki code pehle se sambhalta hai.
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError as e:  # JSONDecodeError aur UnicodeDecodeError dono ValueError hain
            raise EngineError(
                f"The server at {url.split('/')[2]} didn't answer in the expected format. "
                "Another program may be using that port."
            ) from e
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise EngineError("The API key was rejected, or it has no access to this model.") from e
        if e.code == 429:
            raise EngineError("The API rate limit was hit (429). Wait a little and try again.") from e
        raise EngineError(f"The server returned an error ({e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise EngineError(f"Couldn't reach the server: {e.reason}") from e
    except TimeoutError as e:
        raise EngineError("The server took too long to answer.") from e
    # v1.1 fix: connection beech mein toot jaaye (ConnectionResetError, wifi
    # gaya) toh ye URLError nahi, seedha OSError aata hai. Isse bhi saaf
    # message banao, stack trace nahi. Flow: engine -> ChainEngine agla try karega.
    except OSError as e:
        raise EngineError(f"The connection dropped: {e}") from e


# ---------------------------------------------------------------------------
# Model ke jawab ki safai.
# Why: prompt ke baad bhi kuch models ``` fences ya "Here is..." jod dete hain.
# Ye Word file mein nahi jaana chahiye.
# ---------------------------------------------------------------------------
def clean_output(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n?", "", t)
    t = re.sub(r"\n?```\s*$", "", t)
    first, _, rest = t.partition("\n")
    if re.match(r"^(here is|here's|sure|the transcription|transcription:)", first.strip(), re.I) and rest:
        t = rest
    return t.strip()


# ===========================================================================
# Engine 1: Cloud AI
# ===========================================================================
class CloudEngine:
    """
    OpenAI, Anthropic (Claude), Google Gemini, ya koi bhi OpenAI-compatible
    server. Teeno ke request ka format alag hai, isliye har ek ka apna
    chhota function hai; baaki sab common.
    """

    kind = "cloud"

    def __init__(self, provider, api_key, model="", base_url=""):
        self.provider = provider
        self.api_key = api_key
        self.model = model or DEFAULT_CLOUD_MODELS.get(provider, "")
        self.base_url = base_url.rstrip("/")
        if provider == "openai_compatible" and not (self.base_url and self.model):
            raise EngineError("An OpenAI-compatible service needs both a Base URL and a model name.")

    @property
    def label(self):
        names = {"openai": "OpenAI", "anthropic": "Claude", "gemini": "Gemini",
                 "openai_compatible": "Custom API"}
        return f"Cloud AI - {names.get(self.provider, self.provider)} ({self.model})"

    def recognize(self, img) -> str:
        b64 = imaging.to_base64_jpeg(img)
        if self.provider == "anthropic":
            return clean_output(self._anthropic(b64))
        if self.provider == "gemini":
            return clean_output(self._gemini(b64))
        base = self.base_url if self.provider == "openai_compatible" else "https://api.openai.com/v1"
        return clean_output(openai_style_chat(base, self.model, b64,
                                              {"Authorization": f"Bearer {self.api_key}"}))

    def _anthropic(self, b64):
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                                                 "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
        }
        data = _http_json("https://api.anthropic.com/v1/messages", payload,
                          {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
        return "".join(block.get("text", "") for block in data.get("content", [])
                       if block.get("type") == "text")

    def _gemini(self, b64):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent")
        payload = {"contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
        ]}]}
        data = _http_json(url, payload, {"x-goog-api-key": self.api_key})
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as e:
            raise EngineError("Gemini returned no text (possibly blocked by its safety filter).") from e
        return "".join(p.get("text", "") for p in parts)


# ---------------------------------------------------------------------------
# OpenAI style chat request, alag isliye kyunki teen jagah kaam aata hai:
# OpenAI khud, koi bhi OpenAI-compatible cloud, aur LM Studio (local).
# ---------------------------------------------------------------------------
def openai_style_chat(base_url, model, b64, headers=None, timeout=REQUEST_TIMEOUT):
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    }
    data = _http_json(f"{base_url}/chat/completions", payload, headers, timeout)
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise EngineError("The server's reply wasn't in the expected format.") from e


# ===========================================================================
# Engine 2: Local LLM (Ollama ya LM Studio)
# ===========================================================================
def detect_ollama(url) -> list[str]:
    """
    Ollama chal raha hai toh uske vision models ki list lautao, warna [].
    Why: text-only model (jaise llama3) photo nahi dekh sakta; use chunne se
    kachra output aata. Isliye sirf wahi models jo image samajhte hain.
    """
    try:
        tags = _http_json(f"{url.rstrip('/')}/api/tags", timeout=DETECT_TIMEOUT)
    except EngineError:
        return []
    names = [m.get("name", "") for m in tags.get("models", []) if m.get("name")]

    # Ek model ki jaanch: vision hai ya nahi.
    # Why alag function: niche ThreadPoolExecutor ise har model par ek saath
    # chalata hai.
    def is_vision(name):
        try:
            info = _http_json(f"{url.rstrip('/')}/api/show", {"model": name},
                              timeout=DETECT_TIMEOUT)
            caps = info.get("capabilities")
        except EngineError:
            caps = None
        if caps is not None:
            return "vision" in caps
        # Purana Ollama capabilities nahi batata -> naam se andaaza
        return any(h in name.lower() for h in VISION_NAME_HINTS)

    # v1.1 fix: pehle har model ke liye /api/show ek-ek karke chalta tha, har
    # ek par 1.5s timeout. 10 models = 15s tak ruk sakta tha, jabki PRD 2s
    # mein status maangta hai. Ab saare ek saath (max 8 threads) chalte hain.
    # map() order bachaata hai, isliye list ka kram Ollama jaisa hi rehta hai.
    if not names:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(names))) as pool:
        flags = list(pool.map(is_vision, names))
    return [n for n, ok in zip(names, flags) if ok]


# Embedding models text ko numbers mein badalte hain; ye na photo dekh sakte
# hain na text likh sakte hain. Inhe kabhi nahi chunna.
EMBEDDING_NAME_HINTS = ("embed", "bge-", "e5-", "gte-", "minilm", "rerank")


def detect_lmstudio(url) -> list[str]:
    """
    LM Studio ke vision models ki list, sabse bharosemand pehle.

    v1.1 fix: pehle /v1/models ka har model lautate the, embedding aur
    text-only models bhi. Agar wo list mein pehle hota toh wahi chun liya
    jaata aur ya toh error aata ya bekaar text.

    Ab do raaste:
      1. Naya LM Studio /api/v0/models par har model ka "type" batata hai
         ("vlm" = vision). Ye mile toh sirf wahi lo, andaaza nahi.
      2. Purana LM Studio: /v1/models se lo, embedding models hatao, aur
         jinke naam se vision lagta hai unhe aage rakho.
    Flow: detect_all() -> choose_engine() list ka pehla model chunta hai.
    """
    base = url.rstrip("/")
    try:
        rich = _http_json(f"{base}/api/v0/models", timeout=DETECT_TIMEOUT)
        models = rich.get("data", [])
        if models and all("type" in m for m in models):
            return [m["id"] for m in models if m.get("type") == "vlm" and m.get("id")]
    except EngineError:
        pass  # purana version, raasta 2 par chalo

    try:
        data = _http_json(f"{base}/v1/models", timeout=DETECT_TIMEOUT)
    except EngineError:
        return []
    ids = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    ids = [i for i in ids if not any(h in i.lower() for h in EMBEDDING_NAME_HINTS)]
    # sorted() stable hai: vision-naam wale aage, baaki apne kram mein peeche
    return sorted(ids, key=lambda i: not any(h in i.lower() for h in VISION_NAME_HINTS))


class OllamaEngine:
    kind = "local"

    def __init__(self, url, model):
        self.url = url.rstrip("/")
        self.model = model

    @property
    def label(self):
        return f"Local LLM - Ollama ({self.model})"

    def recognize(self, img) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": PROMPT,
                          "images": [imaging.to_base64_jpeg(img, max_side=1600)]}],
        }
        data = _http_json(f"{self.url}/api/chat", payload)
        return clean_output(data.get("message", {}).get("content", ""))


class LMStudioEngine:
    kind = "local"

    def __init__(self, url, model):
        self.url = url.rstrip("/")
        self.model = model

    @property
    def label(self):
        return f"Local LLM - LM Studio ({self.model})"

    def recognize(self, img) -> str:
        b64 = imaging.to_base64_jpeg(img, max_side=1600)
        return clean_output(openai_style_chat(f"{self.url}/v1", self.model, b64))


# ===========================================================================
# Engine 3: Offline OCR, bina AI ke (Tesseract)
# ===========================================================================
def find_tesseract(custom_path="") -> str:
    """Tesseract ka exe dhoondo: pehle user ka diya path, phir PATH, phir
    Windows ki common install jagah."""
    if custom_path and shutil.which(custom_path):
        return shutil.which(custom_path)
    found = shutil.which("tesseract")
    if found:
        return found
    for guess in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                  "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if shutil.which(guess):
            return guess
    return ""


class TesseractEngine:
    kind = "offline"

    def __init__(self, exe, lang="eng"):
        import pytesseract  # yahin import taaki bina pytesseract ke bhi app khule
        self._pt = pytesseract
        self._pt.pytesseract.tesseract_cmd = exe
        self.lang = lang or "eng"

    @property
    def label(self):
        return f"Offline OCR - Tesseract ({self.lang})"

    def recognize(self, img) -> str:
        # psm 4 = "ek column ka text, alag-alag size ki lines". Notebook ke
        # page ke liye ye default (psm 3) se behtar chalta hai.
        # v1.1 fix: galat language (jaise "hin" ka data install nahi) ya toota
        # Tesseract pytesseract.TesseractError deta tha. GUI use pakad leta tha,
        # par terminal mode crash hota tha. Ab ye EngineError hai, sab jagah
        # ek jaisa saaf message.
        try:
            raw = self._pt.image_to_string(imaging.for_ocr(img), lang=self.lang,
                                           config="--psm 4")
        except (self._pt.TesseractError, OSError) as e:
            hint = ""
            if "language" in str(e).lower() or "traineddata" in str(e).lower():
                hint = (f" The language data for '{self.lang}' may be missing; "
                        "install it or change the OCR language in Settings.")
            raise EngineError(f"Tesseract couldn't read this page.{hint} ({e})") from e
        # Tesseract har line alag deta hai; paragraph ke andar ki lines ko
        # jod dete hain, khaali line ko paragraph ka ant maante hain.
        paragraphs, current = [], []
        for line in raw.splitlines():
            if line.strip():
                current.append(line.strip())
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        if current:
            paragraphs.append(" ".join(current))
        return "\n\n".join(paragraphs) or "[no text found]"


# ===========================================================================
# Sahi engine chunna
# ===========================================================================
def detect_all(settings) -> dict:
    """
    Kya-kya available hai, ek baar mein check karo.
    Flow: ui.py startup par ise background thread mein chalata hai aur top
    bar mein status dikhata hai; choose_engine() bhi isi ka use karta hai.
    """
    # v1.1: Ollama, LM Studio aur Tesseract ki jaanch ek doosre par nirbhar
    # nahi, isliye teeno ek saath. Kul samay = sabse dheemi jaanch, jod nahi.
    with ThreadPoolExecutor(max_workers=3) as pool:
        ollama = pool.submit(detect_ollama, settings.ollama_url)
        lms = pool.submit(detect_lmstudio, settings.lmstudio_url)
        tess = pool.submit(find_tesseract, settings.tesseract_path)
        return {
            "cloud": bool(settings.effective_api_key()),
            "ollama": ollama.result(),
            "lmstudio": lms.result(),
            "tesseract": tess.result(),
        }


# ===========================================================================
# Auto mode ka fallback engine
# ===========================================================================
class ChainEngine:
    """
    Kai engines ki line, requirement wale kram mein (cloud -> local -> offline).

    v1.1 fix: pehle Auto mode sirf dekhta tha ki API key saved hai ya nahi.
    Key saved ho aur internet band ho, toh har page fail hota, jabki local
    LLM ya Tesseract taiyaar baitha tha. Ab ek page par cloud fail ho toh
    usi page ko agle engine se padhte hain.

    "Sticky" kyun: agar cloud ek baar fail hua (net band / key galat), toh
    baaki pages par use dobara try karke har page par timeout ka intezaar
    nahi karwaate. Is run ke liye wo engine band.

    Flow: choose_engine("auto") ise lautata hai; ui.py aur main.py ke liye
    ye bilkul ek normal engine jaisa hai (label, kind, recognize).
    """

    def __init__(self, engines_in_order):
        self._engines = list(engines_in_order)
        self._dead = set()          # is run mein fail ho chuke engines ke index
        self._used = self._engines[0]
        self.notes = []             # kis engine ko kyun chhoda, user ko dikhane ke liye

    @property
    def kind(self):
        return self._used.kind

    @property
    def label(self):
        # Jis engine ne pichhla page padha, wahi dikhao
        return self._used.label

    def recognize(self, img) -> str:
        errors = []
        for i, engine in enumerate(self._engines):
            if i in self._dead:
                continue
            try:
                text = engine.recognize(img)
                self._used = engine
                return text
            except EngineError as e:
                self._dead.add(i)
                note = f"{engine.label} failed ({e}); trying the next method."
                self.notes.append(note)
                errors.append(f"{engine.label}: {e}")
        raise EngineError("Every reading method failed for this page.\n- "
                          + "\n- ".join(errors or ["no method left to try"]))


def choose_engine(settings, mode=None, found=None):
    """
    mode: "auto" | "cloud" | "local" | "offline"
    Lautata hai: engine object. Kuch na mile toh EngineError, aisi message ke
    saath jo batata hai ki user ko kya karna hai.
    """
    mode = mode or settings.mode
    found = found if found is not None else detect_all(settings)

    def make_cloud():
        key = settings.effective_api_key()
        if not key:
            raise EngineError("Cloud AI needs an API key. Add one in Settings.")
        return CloudEngine(settings.cloud_provider, key, settings.cloud_model,
                           settings.custom_base_url)

    def make_local():
        wanted = settings.local_model.strip()
        # User ne model chuna hai toh wahi, jis server par wo mila
        if wanted:
            if wanted in found["ollama"]:
                return OllamaEngine(settings.ollama_url, wanted)
            if wanted in found["lmstudio"]:
                return LMStudioEngine(settings.lmstudio_url, wanted)
        if found["ollama"]:
            return OllamaEngine(settings.ollama_url, found["ollama"][0])
        if found["lmstudio"]:
            return LMStudioEngine(settings.lmstudio_url, found["lmstudio"][0])
        raise EngineError(
            "No local vision model found. Install Ollama and run: "
            "ollama pull qwen2.5vl:3b"
        )

    def make_offline():
        if not found["tesseract"]:
            raise EngineError(
                "Tesseract OCR isn't installed. The README shows how for each system."
            )
        try:
            return TesseractEngine(found["tesseract"], settings.ocr_lang)
        except ImportError as e:
            raise EngineError("The pytesseract package is missing: pip install pytesseract") from e

    if mode == "cloud":
        return make_cloud()
    if mode == "local":
        return make_local()
    if mode == "offline":
        return make_offline()

    # Auto: requirement wala order. Jo-jo taiyaar hai sab line mein lagao;
    # ChainEngine page padhte waqt fail hone par agla chalayega (v1.1).
    ready, reasons = [], []
    for maker in (make_cloud, make_local, make_offline):
        try:
            ready.append(maker())
        except EngineError as e:
            reasons.append(str(e))
    if not ready:
        raise EngineError("No reading method is ready yet.\n- " + "\n- ".join(reasons))
    return ready[0] if len(ready) == 1 else ChainEngine(ready)
