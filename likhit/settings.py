"""
settings.py - Likhit ki saari user settings yahan save aur load hoti hain.

Why: user ko har baar API key, model ya local server ka address dobara na
daalna pade. App band karke kholne par bhi sab yaad rahe.

Flow: ui.py app start hote hi load_settings() call karta hai, aur Settings
window mein "Save" dabane par save_settings(). engines.py in values ko padh
kar decide karta hai ki kaunsa engine chalega.
"""

import json
import os
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Config folder ka path, har OS ke apne tareeke se.
# Why: Windows, macOS aur Linux teeno app data alag jagah rakhte hain.
# Galat jagah file likhne se permission error aa sakta hai.
# Flow: niche settings_path() isi folder ke andar settings.json banata hai.
# ---------------------------------------------------------------------------
def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Likhit"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Likhit"
    # Linux aur baaki Unix: XDG standard follow karte hain
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "likhit"


def settings_path() -> Path:
    return config_dir() / "settings.json"


# ---------------------------------------------------------------------------
# Settings ka poora dhaancha ek dataclass mein.
# Why: har field ka default value ek hi jagah dikh jaata hai, aur code mein
# settings.api_key jaisa saaf naam use hota hai, dict["api_key"] nahi.
# Flow: engines.choose_engine() aur ui.SettingsDialog dono isi object se kaam
# karte hain.
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    # "auto" = pehle cloud AI, phir local LLM, phir offline OCR (wahi order
    # jo project ki requirement mein tha)
    mode: str = "auto"

    # --- Cloud AI (API key wala raasta) ---
    # openai | anthropic | gemini | openai_compatible
    cloud_provider: str = "openai"
    api_key: str = ""
    # Khaali chhoda toh har provider ka default model use hoga (engines.py)
    cloud_model: str = ""
    # Sirf "openai_compatible" ke liye: Groq, OpenRouter, Together jaise
    # kisi bhi OpenAI-style server ka base URL
    custom_base_url: str = ""

    # --- Local LLM (internet ke bina) ---
    ollama_url: str = "http://localhost:11434"
    lmstudio_url: str = "http://localhost:1234"
    # Khaali = jo pehla vision model mile wahi use karo
    local_model: str = ""

    # --- Offline OCR (bina AI ke) ---
    # Tesseract language code; "eng", "hin", ya "eng+hin"
    ocr_lang: str = "eng"
    # Agar tesseract PATH mein nahi hai (Windows mein aksar), yahan poora
    # path daal sakte hain, jaise C:\Program Files\Tesseract-OCR\tesseract.exe
    tesseract_path: str = ""

    # --- Word file ke options ---
    include_scans: bool = False   # har page ke niche original photo bhi daalo
    page_breaks: bool = True      # har photo ka text naye page par

    # Last folder yaad rakhte hain taaki file dialog wahin khule
    last_folder: str = field(default_factory=lambda: str(Path.home()))

    def effective_api_key(self) -> str:
        """
        Settings mein key na ho toh environment variable se utha lo.
        Why: developers aksar key ko OPENAI_API_KEY jaise env var mein rakhte
        hain; unhe app mein dobara paste na karna pade.
        """
        if self.api_key.strip():
            return self.api_key.strip()
        env_names = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openai_compatible": "OPENAI_API_KEY",
        }
        return os.environ.get(env_names.get(self.cloud_provider, ""), "").strip()


# ---------------------------------------------------------------------------
# File se settings padhna.
# Why: file na mile, kharab JSON ho, ya purane version ki field ho, teeno
# haalat mein app crash nahi hona chahiye; seedha defaults par chal jaao.
# Flow: ui.LikhitApp.__init__ yahi call karta hai.
# ---------------------------------------------------------------------------
def load_settings() -> Settings:
    path = settings_path()
    s = Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return s
    # Sirf wahi keys lo jo Settings mein hain; anjaan keys chupchaap ignore
    for key, value in data.items():
        if hasattr(s, key) and isinstance(value, type(getattr(s, key))):
            setattr(s, key, value)
    return s


# ---------------------------------------------------------------------------
# File mein settings likhna.
# Why: API key ek secret hai, isliye Linux/macOS par file ko sirf owner ke
# liye readable (chmod 600) banate hain.
# Flow: SettingsDialog ka Save button, aur file dialog ke baad last_folder.
# ---------------------------------------------------------------------------
def save_settings(s: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")
    # Pehle tmp file, phir rename: beech mein app band ho jaaye toh bhi
    # purani settings file adhoori nahi rehti
    os.replace(tmp, path)
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
