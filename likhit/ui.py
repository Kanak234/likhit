"""
ui.py - Likhit ki desktop window (Tkinter).

Why Tkinter: Python ke saath Windows aur macOS par pehle se aata hai, Linux
par ek package se. Koi bhaari GUI framework install nahi karna padta, aur
teeno OS par ek hi code chalta hai.

Layout (baayein se daayein):
  [Pages list]  [Photo preview]  [Padha hua text - editable]
Neeche: engine chunne ka menu, "Read handwriting", progress, "Save as Word".

Flow: main.py -> run_app() -> LikhitApp. Handwriting padhne ka kaam alag
thread mein hota hai (engines.py), taaki window atke nahi; thread apni
khabar ek queue mein daalta hai aur _poll_queue() use UI par dikhata hai.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from . import engines, imaging
from .docx_writer import ASSETS, Page, build_document
from .settings import load_settings, save_settings

# ---------------------------------------------------------------------------
# Rang aur font. Kaagaz jaisa halka cream background aur syahi jaisa gehra
# neela text, taaki app "notes" wala kaam jaisa mehsoos ho. Accent orange
# KP logo ke gradient se liya gaya hai.
# ---------------------------------------------------------------------------
PAPER = "#f6f1e7"
PANEL = "#fffdf8"
INK = "#1f2a44"
MUTED = "#6b7280"
LINE = "#e3d9c6"
ACCENT = "#d9531e"
ACCENT_DARK = "#b8431a"
OK = "#2f7d4f"
WARN = "#a15c07"

MODES = [("Auto (best available)", "auto"), ("Cloud AI (API key)", "cloud"),
         ("Local LLM (offline)", "local"), ("Without AI (Tesseract)", "offline")]
PROVIDERS = [("OpenAI", "openai"), ("Anthropic Claude", "anthropic"),
             ("Google Gemini", "gemini"), ("Other OpenAI-compatible", "openai_compatible")]


def _ui_font(size, weight="normal"):
    # Har OS ka apna saaf system font; na mile toh Tk khud fallback karta hai
    if sys.platform == "darwin":
        family = "Helvetica Neue"
    elif sys.platform.startswith("win"):
        family = "Segoe UI"
    else:
        family = "DejaVu Sans"
    return (family, size, weight)


def open_with_system(path):
    """Bani hui Word file ko system ke default app (Word/LibreOffice) mein kholo."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa: S606 - user ki apni file
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


class LikhitApp:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.pages: list[Page] = []
        self.current = None           # abhi selected page ka index
        self.busy = False             # padhai chal rahi hai toh buttons band
        self.events = queue.Queue()   # worker thread -> UI thread
        self._preview_img = None      # PhotoImage ka reference; warna Tk use mita deta hai
        self._loading_text = False    # text box bharte waqt "edit hua" na samjho

        self._setup_window()
        self._setup_styles()
        self._build_header()
        # Footer pehle pack karte hain (neeche chipka ke), taaki chhoti window
        # mein bhi Save button kabhi kat kar gayab na ho
        self._build_footer()
        self._build_body()
        self._bind_keys()
        self._refresh_list()
        self._show_page(None)

        self.root.after(100, self._poll_queue)
        self.refresh_status()

    # ------------------------------------------------------------------
    # Window aur styles
    # ------------------------------------------------------------------
    def _setup_window(self):
        self.root.title("Likhit - handwriting to Word")
        self.root.geometry("1180x720")
        self.root.minsize(900, 560)
        self.root.configure(bg=PAPER)
        icon = ASSETS / "logo-light-bg-256.png"
        if icon.exists():
            self._icon = tk.PhotoImage(file=str(icon))
            self.root.iconphoto(True, self._icon)

    def _setup_styles(self):
        st = ttk.Style(self.root)
        # "clam" theme teeno OS par ek jaisa dikhta hai aur rang badalne deta hai
        st.theme_use("clam")
        st.configure(".", background=PAPER, foreground=INK, font=_ui_font(10))
        st.configure("Panel.TFrame", background=PANEL)
        st.configure("Paper.TFrame", background=PAPER)
        st.configure("TLabel", background=PAPER, foreground=INK)
        st.configure("Panel.TLabel", background=PANEL)
        st.configure("Muted.TLabel", background=PAPER, foreground=MUTED, font=_ui_font(9))
        st.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=_ui_font(9))
        st.configure("Title.TLabel", background=PAPER, font=_ui_font(17, "bold"))
        st.configure("Section.TLabel", background=PANEL, foreground=MUTED,
                     font=_ui_font(9, "bold"))
        st.configure("TButton", padding=(12, 6), background=PANEL, bordercolor=LINE,
                     lightcolor=PANEL, darkcolor=PANEL)
        st.map("TButton", background=[("active", "#f1e9da"), ("disabled", PAPER)])
        st.configure("Accent.TButton", background=ACCENT, foreground="white",
                     bordercolor=ACCENT_DARK, lightcolor=ACCENT, darkcolor=ACCENT,
                     font=_ui_font(10, "bold"))
        st.map("Accent.TButton", background=[("active", ACCENT_DARK), ("disabled", "#e8b9a5")],
               foreground=[("disabled", "white")])
        st.configure("Small.TButton", padding=(8, 3), font=_ui_font(9))
        st.configure("TCheckbutton", background=PAPER)
        st.configure("TCombobox", fieldbackground=PANEL, background=PANEL)
        st.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=LINE,
                     bordercolor=LINE, lightcolor=ACCENT, darkcolor=ACCENT)

    # ------------------------------------------------------------------
    # Upar ki patti: logo (watermark), naam, engine status, settings
    # ------------------------------------------------------------------
    def _build_header(self):
        bar = ttk.Frame(self.root, style="Paper.TFrame", padding=(18, 14, 18, 8))
        bar.pack(fill="x")

        logo_path = ASSETS / "logo-light-bg-48.png"
        if logo_path.exists():
            self._logo = tk.PhotoImage(file=str(logo_path))
            ttk.Label(bar, image=self._logo).pack(side="left", padx=(0, 10))

        titles = ttk.Frame(bar, style="Paper.TFrame")
        titles.pack(side="left")
        ttk.Label(titles, text="Likhit", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Turn handwritten pages into a Word document",
                  style="Muted.TLabel").pack(anchor="w")

        ttk.Button(bar, text="Settings", command=self.open_settings).pack(side="right")
        self.status_label = tk.Label(bar, text="Checking what's available...", bg=PAPER,
                                     fg=MUTED, font=_ui_font(9))
        self.status_label.pack(side="right", padx=14)

    # ------------------------------------------------------------------
    # Beech ka hissa: teen panel
    # ------------------------------------------------------------------
    def _build_body(self):
        body = ttk.Frame(self.root, style="Paper.TFrame", padding=(18, 4, 18, 8))
        body.pack(fill="both", expand=True)
        panes = ttk.PanedWindow(body, orient="horizontal")
        panes.pack(fill="both", expand=True)

        # --- Pages list ---
        left = ttk.Frame(panes, style="Panel.TFrame", padding=12)
        ttk.Label(left, text="PAGES", style="Section.TLabel").pack(anchor="w")
        self.listbox = tk.Listbox(left, activestyle="none", bg=PANEL, fg=INK, bd=0,
                                  highlightthickness=0, selectbackground="#f3dccf",
                                  selectforeground=INK, font=_ui_font(10), width=26)
        self.listbox.pack(fill="both", expand=True, pady=(8, 8))
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        row = ttk.Frame(left, style="Panel.TFrame")
        row.pack(fill="x")
        self.add_btn = ttk.Button(row, text="+ Add photos", command=self.add_files)
        self.add_btn.pack(side="left", fill="x", expand=True)
        row2 = ttk.Frame(left, style="Panel.TFrame")
        row2.pack(fill="x", pady=(6, 0))
        self.up_btn = ttk.Button(row2, text="↑", width=3, style="Small.TButton",
                                 command=lambda: self.move(-1))
        self.down_btn = ttk.Button(row2, text="↓", width=3, style="Small.TButton",
                                   command=lambda: self.move(1))
        self.remove_btn = ttk.Button(row2, text="Remove", style="Small.TButton",
                                     command=self.remove_page)
        self.up_btn.pack(side="left")
        self.down_btn.pack(side="left", padx=4)
        self.remove_btn.pack(side="right")
        panes.add(left, weight=1)

        # --- Preview ---
        mid = ttk.Frame(panes, style="Panel.TFrame", padding=12)
        ttk.Label(mid, text="PHOTO", style="Section.TLabel").pack(anchor="w")
        self.canvas = tk.Canvas(mid, bg="#efe8da", highlightthickness=0, bd=0,
                                width=420)
        self.canvas.pack(fill="both", expand=True, pady=(8, 0))
        self.canvas.bind("<Configure>", lambda e: self._draw_preview())
        panes.add(mid, weight=3)

        # --- Text ---
        right = ttk.Frame(panes, style="Panel.TFrame", padding=12)
        head = ttk.Frame(right, style="Panel.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text="TEXT", style="Section.TLabel").pack(side="left")
        self.reread_btn = ttk.Button(head, text="Read this page again",
                                     style="Small.TButton", command=self.reread_current)
        self.reread_btn.pack(side="right")
        self.page_engine = ttk.Label(right, text="", style="PanelMuted.TLabel")
        self.page_engine.pack(anchor="w", pady=(4, 0))

        # Hint neeche chipka hua, taaki bada text box use dhakel na de
        ttk.Label(right, text="You can fix mistakes here before saving. "
                              "Words marked [?] were hard to read.",
                  style="PanelMuted.TLabel", wraplength=360).pack(side="bottom", anchor="w",
                                                                   pady=(6, 0))
        text_wrap = ttk.Frame(right, style="Panel.TFrame")
        text_wrap.pack(fill="both", expand=True, pady=(6, 0))
        self.text = tk.Text(text_wrap, wrap="word", undo=True, bg="white", fg=INK, width=44,
                            insertbackground=INK, relief="flat", padx=12, pady=10,
                            font=_ui_font(11), highlightthickness=1,
                            highlightbackground=LINE, highlightcolor=ACCENT)
        scroll = ttk.Scrollbar(text_wrap, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<<Modified>>", self._on_text_modified)
        self.text.tag_configure("unclear", background="#fff1a8")
        panes.add(right, weight=3)

    # ------------------------------------------------------------------
    # Neeche ki patti: engine, read, progress, save
    # ------------------------------------------------------------------
    def _build_footer(self):
        bar = ttk.Frame(self.root, style="Paper.TFrame", padding=(18, 6, 18, 16))
        bar.pack(fill="x", side="bottom")

        # Daayein wale button pehle pack karte hain: jagah kam pade toh
        # progress ka text chhota hoga, Save button nahi
        self.save_btn = ttk.Button(bar, text="Save as Word", style="Accent.TButton",
                                   command=self.save_docx)
        self.save_btn.pack(side="right")
        self.scan_var = tk.BooleanVar(value=self.settings.include_scans)
        ttk.Checkbutton(bar, text="Include original photos", variable=self.scan_var
                        ).pack(side="right", padx=12)

        ttk.Label(bar, text="Read with").pack(side="left")
        self.mode_var = tk.StringVar(value=self._mode_label(self.settings.mode))
        mode_box = ttk.Combobox(bar, textvariable=self.mode_var, state="readonly",
                                values=[m[0] for m in MODES], width=24)
        mode_box.pack(side="left", padx=(8, 12))
        mode_box.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.read_btn = ttk.Button(bar, text="Read handwriting", style="Accent.TButton",
                                   command=self.read_all)
        self.read_btn.pack(side="left")

        self.progress = ttk.Progressbar(bar, mode="determinate", length=140)
        self.progress.pack(side="left", padx=14)
        self.progress_label = ttk.Label(bar, text="", style="Muted.TLabel")
        self.progress_label.pack(side="left")

    def _bind_keys(self):
        # Ctrl on Windows/Linux, Command on macOS
        mod = "Command" if sys.platform == "darwin" else "Control"
        self.root.bind(f"<{mod}-o>", lambda e: self.add_files())
        self.root.bind(f"<{mod}-s>", lambda e: self.save_docx())
        self.root.bind(f"<{mod}-r>", lambda e: self.read_all())

    # ------------------------------------------------------------------
    # Status: kaun-kaun se engine taiyaar hain
    # Why: user ko pehle hi dikh jaaye ki Auto mode kya chalayega, warna
    # "Read" dabane ke baad pata chalta.
    # ------------------------------------------------------------------
    def refresh_status(self):
        self.status_label.configure(text="Checking what's available...", fg=MUTED)

        def work():
            found = engines.detect_all(self.settings)
            self.events.put(("status", found))

        threading.Thread(target=work, daemon=True).start()

    def _show_status(self, found):
        bits = []
        if found["cloud"]:
            bits.append("API key ✓")
        local = found["ollama"] or found["lmstudio"]
        bits.append(f"Local model: {local[0]}" if local else "No local model")
        bits.append("Tesseract ✓" if found["tesseract"] else "No Tesseract")
        ready = found["cloud"] or local or found["tesseract"]
        self.status_label.configure(text="   ·   ".join(bits), fg=OK if ready else WARN)

    # ------------------------------------------------------------------
    # Pages jodna, hatana, upar-neeche karna
    # ------------------------------------------------------------------
    def add_files(self):
        if self.busy:
            return
        types = [("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif")]
        if imaging.PDF_SUPPORTED:
            types.insert(0, ("Images and PDF", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff "
                                                "*.webp *.gif *.pdf"))
            types.append(("PDF", "*.pdf"))
        paths = filedialog.askopenfilenames(parent=self.root, title="Choose handwritten pages",
                                            initialdir=self.settings.last_folder,
                                            filetypes=types)
        if not paths:
            return
        self.settings.last_folder = str(Path(paths[0]).parent)
        save_settings(self.settings)

        problems = []
        for p in paths:
            try:
                for name, img in imaging.load_pages(p):
                    self.pages.append(Page(name=name, image=img))
            except Exception as e:  # noqa: BLE001 - user ko har file ki galti dikhani hai
                problems.append(f"{Path(p).name}: {e}")
        self._refresh_list()
        self._select(len(self.pages) - 1)
        if problems:
            messagebox.showwarning("Some files were skipped", "\n".join(problems),
                                   parent=self.root)

    def remove_page(self):
        if self.busy or self.current is None:
            return
        del self.pages[self.current]
        self._refresh_list()
        self._select(min(self.current, len(self.pages) - 1))

    def move(self, step):
        i = self.current
        if self.busy or i is None or not (0 <= i + step < len(self.pages)):
            return
        self.pages[i], self.pages[i + step] = self.pages[i + step], self.pages[i]
        self._refresh_list()
        self._select(i + step)

    def _refresh_list(self):
        self.listbox.delete(0, "end")
        for n, page in enumerate(self.pages, start=1):
            mark = "✓" if page.text.strip() else "·"
            self.listbox.insert("end", f" {mark}  {n}. {page.name}")
        self._update_buttons()

    def _select(self, index):
        if 0 <= index < len(self.pages):
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            self.listbox.see(index)
            self._show_page(index)
        else:
            self._show_page(None)

    def _on_list_select(self, _event):
        sel = self.listbox.curselection()
        if sel:
            self._show_page(sel[0])

    # ------------------------------------------------------------------
    # Selected page ko preview aur text box mein dikhana
    # ------------------------------------------------------------------
    def _show_page(self, index):
        self.current = index
        self._loading_text = True
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        if index is None:
            self.page_engine.configure(text="")
            self.text.configure(state="disabled")
        else:
            page = self.pages[index]
            self.text.insert("1.0", page.text)
            self._mark_unclear()
            self.page_engine.configure(text=f"Read by {page.engine_label}"
                                       if page.engine_label else "Not read yet")
        self.text.edit_modified(False)
        self._loading_text = False
        self._draw_preview()
        self._update_buttons()

    def _draw_preview(self):
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        if self.current is None:
            c.create_text(w / 2, h / 2 - 12, text="No pages yet", fill=INK,
                          font=_ui_font(13, "bold"))
            c.create_text(w / 2, h / 2 + 14, fill=MUTED, font=_ui_font(10),
                          text="Click “+ Add photos” and pick photos of your notes.")
            return
        img = self.pages[self.current].image.copy()
        img.thumbnail((w - 16, h - 16), Image.LANCZOS)
        self._preview_img = ImageTk.PhotoImage(img)
        c.create_image(w / 2, h / 2, image=self._preview_img)

    def _on_text_modified(self, _event):
        # User ne text badla toh turant page mein save karo
        if self.text.edit_modified() and not self._loading_text and self.current is not None:
            page = self.pages[self.current]
            had_text = bool(page.text.strip())
            page.text = self.text.get("1.0", "end-1c")
            self._mark_unclear()
            if had_text != bool(page.text.strip()):
                self._refresh_list()
                self.listbox.selection_set(self.current)
        self.text.edit_modified(False)

    def _mark_unclear(self):
        self.text.tag_remove("unclear", "1.0", "end")
        start = "1.0"
        while True:
            pos = self.text.search("[?]", start, stopindex="end")
            if not pos:
                break
            end = f"{pos}+3c"
            self.text.tag_add("unclear", pos, end)
            start = end

    def _update_buttons(self):
        has_pages = bool(self.pages)
        has_sel = self.current is not None
        state = lambda ok: "normal" if ok and not self.busy else "disabled"  # noqa: E731
        self.add_btn.configure(state=state(True))
        self.read_btn.configure(state=state(has_pages))
        self.save_btn.configure(state=state(any(p.text.strip() for p in self.pages)))
        self.remove_btn.configure(state=state(has_sel))
        self.up_btn.configure(state=state(has_sel and self.current > 0))
        self.down_btn.configure(state=state(has_sel and self.current < len(self.pages) - 1))
        self.reread_btn.configure(state=state(has_sel))

    # ------------------------------------------------------------------
    # Handwriting padhna (background thread)
    # ------------------------------------------------------------------
    def _mode_label(self, key):
        return next((label for label, k in MODES if k == key), MODES[0][0])

    def _mode_key(self):
        return next((k for label, k in MODES if label == self.mode_var.get()), "auto")

    def _on_mode_change(self, _e=None):
        self.settings.mode = self._mode_key()
        save_settings(self.settings)

    def read_all(self):
        if self.busy or not self.pages:
            return
        todo = [i for i, p in enumerate(self.pages) if not p.text.strip()]
        if not todo:
            if not messagebox.askyesno("Read again?", "Every page already has text. "
                                       "Read all of them again? Your edits will be replaced.",
                                       parent=self.root):
                return
            todo = list(range(len(self.pages)))
        self._start_reading(todo)

    def reread_current(self):
        if self.busy or self.current is None:
            return
        if self.pages[self.current].text.strip() and not messagebox.askyesno(
                "Read again?", "Replace the text of this page?", parent=self.root):
            return
        self._start_reading([self.current])

    def _start_reading(self, indexes):
        self.busy = True
        self._update_buttons()
        self.progress.configure(maximum=len(indexes), value=0)
        self.progress_label.configure(text="Getting ready...")
        mode = self._mode_key()
        # Worker ke liye pages ki images ki copy; UI thread beech mein list badal de
        # toh bhi galat page par text na jaaye
        jobs = [(i, self.pages[i]) for i in indexes]

        def work():
            try:
                engine = engines.choose_engine(self.settings, mode)
            except engines.EngineError as e:
                self.events.put(("fatal", str(e)))
                return
            self.events.put(("engine", engine.label))
            for n, (i, page) in enumerate(jobs, start=1):
                self.events.put(("progress", (n - 1, len(jobs), page.name)))
                try:
                    text = engine.recognize(page.image)
                    self.events.put(("page", (page, text, engine.label)))
                except engines.EngineError as e:
                    self.events.put(("page_error", (page, str(e))))
                except Exception as e:  # noqa: BLE001
                    self.events.put(("page_error", (page, f"Unexpected problem: {e}")))
            self.events.put(("done", len(jobs)))

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # Worker thread ki khabrein UI par dikhana. Tk sirf main thread se
    # chhoona chahiye, isliye ye har 100ms queue check karta hai.
    # ------------------------------------------------------------------
    def _poll_queue(self):
        errors = []
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "status":
                    self._show_status(data)
                elif kind == "engine":
                    self.progress_label.configure(text=f"Using {data}")
                elif kind == "progress":
                    done, total, name = data
                    self.progress.configure(value=done)
                    self.progress_label.configure(text=f"Reading {done + 1} of {total}: {name}")
                elif kind == "page":
                    page, text, label = data
                    page.text, page.engine_label = text, label
                    self._after_page_change(page)
                elif kind == "page_error":
                    page, msg = data
                    errors.append(f"{page.name}: {msg}")
                elif kind == "fatal":
                    self._finish_reading()
                    self.progress_label.configure(text="")
                    messagebox.showerror("Can't read yet", data, parent=self.root)
                elif kind == "done":
                    self.progress.configure(value=data)
                    self._finish_reading()
                    self.progress_label.configure(text="Done. Review, then save.")
        except queue.Empty:
            pass
        if errors:
            messagebox.showwarning("Some pages could not be read", "\n\n".join(errors),
                                   parent=self.root)
        self.root.after(100, self._poll_queue)

    def _after_page_change(self, page):
        if page in self.pages:
            idx = self.pages.index(page)
            self._refresh_list()
            self._select(idx)

    def _finish_reading(self):
        self.busy = False
        self._update_buttons()

    # ------------------------------------------------------------------
    # Word file save karna
    # ------------------------------------------------------------------
    def save_docx(self):
        if self.busy or not any(p.text.strip() for p in self.pages):
            return
        default = (self.pages[0].name if self.pages else "notes") + ".docx"
        path = filedialog.asksaveasfilename(parent=self.root, title="Save Word document",
                                            defaultextension=".docx", initialfile=default,
                                            initialdir=self.settings.last_folder,
                                            filetypes=[("Word document", "*.docx")])
        if not path:
            return
        self.settings.include_scans = self.scan_var.get()
        self.settings.last_folder = str(Path(path).parent)
        save_settings(self.settings)
        try:
            out = build_document(self.pages, path, include_scans=self.scan_var.get(),
                                 page_breaks=self.settings.page_breaks)
        except PermissionError:
            messagebox.showerror("Couldn't save", "The file is open in another program. "
                                 "Close it in Word and try again.", parent=self.root)
            return
        except OSError as e:
            messagebox.showerror("Couldn't save", str(e), parent=self.root)
            return
        if messagebox.askyesno("Saved", f"Saved to\n{out}\n\nOpen it now?", parent=self.root):
            open_with_system(out)

    # ------------------------------------------------------------------
    # Settings window
    # ------------------------------------------------------------------
    def open_settings(self):
        SettingsDialog(self)


class SettingsDialog:
    """
    API key, cloud provider, local server aur Tesseract ki settings.
    Why alag window: main screen saaf rahe; ye cheezein ek baar set hoti hain.
    Flow: Save -> settings.save_settings() -> app.refresh_status().
    """

    def __init__(self, app):
        self.app = app
        s = app.settings
        win = self.win = tk.Toplevel(app.root)
        win.title("Settings")
        win.configure(bg=PAPER)
        win.transient(app.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, style="Paper.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self.row = 0

        self._section(frame, "Cloud AI")
        self.provider = tk.StringVar(value=next(l for l, k in PROVIDERS
                                                if k == s.cloud_provider))
        self._combo(frame, "Provider", self.provider, [p[0] for p in PROVIDERS])
        self.key = tk.StringVar(value=s.api_key)
        self._entry(frame, "API key", self.key, show="•",
                    hint="Stored only on this computer. Leave empty to skip cloud AI.")
        self.model = tk.StringVar(value=s.cloud_model)
        self._entry(frame, "Model", self.model, hint="Empty = provider's default model.")
        self.base = tk.StringVar(value=s.custom_base_url)
        self._entry(frame, "Base URL", self.base,
                    hint="Only for 'Other OpenAI-compatible', e.g. https://api.groq.com/openai/v1")

        self._section(frame, "Local LLM")
        self.ollama = tk.StringVar(value=s.ollama_url)
        self._entry(frame, "Ollama address", self.ollama)
        self.lms = tk.StringVar(value=s.lmstudio_url)
        self._entry(frame, "LM Studio address", self.lms)
        self.local_model = tk.StringVar(value=s.local_model or "(pick automatically)")
        self.local_box = self._combo(frame, "Model", self.local_model,
                                     ["(pick automatically)"], readonly=False)
        ttk.Button(frame, text="Find models", style="Small.TButton",
                   command=self._find_models).grid(row=self.row - 1, column=2, padx=(8, 0))

        self._section(frame, "Without AI")
        self.lang = tk.StringVar(value=s.ocr_lang)
        self._entry(frame, "OCR language", self.lang, hint="eng, hin, or eng+hin")
        self.tess = tk.StringVar(value=s.tesseract_path)
        self._entry(frame, "Tesseract path", self.tess, hint="Only if it isn't found automatically.")

        btns = ttk.Frame(frame, style="Paper.TFrame")
        btns.grid(row=self.row, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(btns, text="Save", style="Accent.TButton",
                   command=self._save).pack(side="right", padx=8)
        win.grab_set()

    def _section(self, parent, title):
        ttk.Label(parent, text=title, font=_ui_font(11, "bold")).grid(
            row=self.row, column=0, columnspan=3, sticky="w", pady=(12 if self.row else 0, 4))
        self.row += 1

    def _entry(self, parent, label, var, show=None, hint=None):
        ttk.Label(parent, text=label).grid(row=self.row, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(parent, textvariable=var, width=46, show=show or "").grid(
            row=self.row, column=1, sticky="ew", pady=2)
        self.row += 1
        if hint:
            ttk.Label(parent, text=hint, style="Muted.TLabel").grid(
                row=self.row, column=1, sticky="w")
            self.row += 1

    def _combo(self, parent, label, var, values, readonly=True):
        ttk.Label(parent, text=label).grid(row=self.row, column=0, sticky="w", padx=(0, 12))
        box = ttk.Combobox(parent, textvariable=var, values=values, width=44,
                           state="readonly" if readonly else "normal")
        box.grid(row=self.row, column=1, sticky="ew", pady=2)
        self.row += 1
        return box

    def _find_models(self):
        names = (engines.detect_ollama(self.ollama.get())
                 + engines.detect_lmstudio(self.lms.get()))
        self.local_box.configure(values=["(pick automatically)"] + names)
        if not names:
            messagebox.showinfo("No models found", "No local vision model is running. "
                                "Start Ollama and run:  ollama pull qwen2.5vl:3b",
                                parent=self.win)

    def _save(self):
        s = self.app.settings
        s.cloud_provider = next(k for l, k in PROVIDERS if l == self.provider.get())
        s.api_key = self.key.get().strip()
        s.cloud_model = self.model.get().strip()
        s.custom_base_url = self.base.get().strip()
        s.ollama_url = self.ollama.get().strip() or "http://localhost:11434"
        s.lmstudio_url = self.lms.get().strip() or "http://localhost:1234"
        lm = self.local_model.get().strip()
        s.local_model = "" if lm.startswith("(") else lm
        s.ocr_lang = self.lang.get().strip() or "eng"
        s.tesseract_path = self.tess.get().strip()
        save_settings(s)
        self.win.destroy()
        self.app.refresh_status()


def run_app():
    # High-DPI Windows screens par dhundhla text na dikhe. Ye Tk window
    # banne se PEHLE hona chahiye, baad mein koi asar nahi hota.
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    root = tk.Tk()
    LikhitApp(root)
    root.mainloop()
