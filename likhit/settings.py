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

    # v1.1: True = API key settings.json mein nahi, OS ke secure store
    # (keyring) mein hai. load_settings() isi flag se wahan se laata hai.
    key_in_keyring: bool = False

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
# API key ke liye OS ka secure store (v1.1).
# Why: pehle key settings.json mein saada text thi. Linux/macOS par chmod 600
# tha, par Windows par file koi bhi program ya user padh sakta tha. keyring
# library har OS ka apna tijori istemaal karti hai:
#   Windows -> Credential Manager, macOS -> Keychain, Linux -> Secret Service.
# Fallback: keyring na ho, ya Linux par koi tijori na chal rahi ho, toh
# purana file wala tareeka. App kabhi key ki wajah se band nahi hota.
# Flow: save_settings() yahan likhta hai, load_settings() yahan se padhta hai.
# ---------------------------------------------------------------------------
KEYRING_SERVICE = "Likhit"
KEYRING_USER = "api_key"


def _keyring():
    """Kaam karne wala keyring module, ya None. LIKHIT_NO_KEYRING=1 se band
    (tests aur un logon ke liye jo file hi chahte hain)."""
    if os.environ.get("LIKHIT_NO_KEYRING"):
        return None
    try:
        import keyring
        from keyring.backends import fail
    except ImportError:
        return None
    try:
        # "fail" backend = koi tijori nahi mili; ise use karna bekaar hai
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:  # noqa: BLE001 - backend dhoondhne mein koi bhi galti = fallback
        return None
    return keyring


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

    kr = _keyring()
    if s.key_in_keyring and not s.api_key:
        # Key tijori mein hai: wahan se lao. Na mile toh khaali; top bar
        # "no key" dikhayega aur user Settings mein dobara daal sakta hai.
        if kr is not None:
            try:
                s.api_key = kr.get_password(KEYRING_SERVICE, KEYRING_USER) or ""
            except Exception:  # noqa: BLE001
                s.api_key = ""
    elif s.api_key and not s.key_in_keyring and kr is not None:
        # Migration: v1.0 ki file mein key saada text mein padi hai. Ek baar
        # save karo; save_settings() key ko tijori mein likhkar, wapas padh
        # kar pakka karke hi file se hatata hai. Fail ho toh file jaisi thi.
        try:
            save_settings(s)
        except OSError:
            pass
    return s


# ---------------------------------------------------------------------------
# File mein settings likhna.
# Why: API key ek secret hai. v1.1 se wo pehle OS ki tijori (keyring) mein
# jaati hai; tijori na ho tabhi file mein, aur tab Linux/macOS par file sirf
# owner ke liye readable (chmod 600).
# Flow: SettingsDialog ka Save button, aur file dialog ke baad last_folder.
# ---------------------------------------------------------------------------
def save_settings(s: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(s)
    data["key_in_keyring"] = False
    kr = _keyring()
    if kr is not None:
        try:
            if s.api_key:
                kr.set_password(KEYRING_SERVICE, KEYRING_USER, s.api_key)
                # Wapas padh ke pakka karo; tabhi file se hatao. Warna key
                # dono jagah se kho sakti thi.
                if kr.get_password(KEYRING_SERVICE, KEYRING_USER) == s.api_key:
                    data["api_key"] = ""
                    data["key_in_keyring"] = True
            elif s.key_in_keyring:
                # User ne key mita di: tijori se bhi hatao
                kr.delete_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception:  # noqa: BLE001 - tijori na chale toh file wala fallback
            data["api_key"] = s.api_key
            data["key_in_keyring"] = False
    s.key_in_keyring = data["key_in_keyring"]

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Pehle tmp file, phir rename: beech mein app band ho jaaye toh bhi
    # purani settings file adhoori nahi rehti
    os.replace(tmp, path)
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
