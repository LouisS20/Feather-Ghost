"""
Feather Ghost — le copier-coller qui tape lettre par lettre.

Colle ton texte, clique sur « Lancer », puis clique là où tu veux que ça
s'écrive : Feather Ghost tape à ta place, comme si c'était ton clavier.

Arrêt d'urgence : touche Échap (fonctionne même si la fenêtre n'est pas active).
"""

import json
import os
import random
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from pynput import keyboard, mouse
from pynput.keyboard import Controller, Key

IS_WIN = sys.platform.startswith("win")
if IS_WIN:
    import ctypes
    from ctypes import wintypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # coordonnées cohérentes avec la souris
    except Exception:
        pass
    _user32 = ctypes.windll.user32
    _user32.WindowFromPoint.restype = wintypes.HWND
    _user32.WindowFromPoint.argtypes = [wintypes.POINT]
    _user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetAncestor.restype = wintypes.HWND
    _user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    WM_ACTIVATE, WM_SETFOCUS = 0x0006, 0x0007
    WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0100, 0x0101, 0x0102


def window_at(x, y):
    return _user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))


def post_char(hwnd, ch):
    """Envoie un caractère directement à une fenêtre, sans toucher au clavier réel."""
    data = ch.encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        _user32.PostMessageW(hwnd, WM_CHAR, unit, 0)


def _lparam(scan, up=False):
    v = 1 | (scan << 16)
    if up:
        v |= (1 << 30) | (1 << 31)
    return v


def post_key(hwnd, ch):
    """Rejoue ce que Windows envoie pour une vraie frappe : KEYDOWN, CHAR, KEYUP.
    Beaucoup d'applis modernes (Rust, jeux, etc.) attendent cette séquence complète."""
    if ch == "\r":
        vk, shift = 0x0D, False
    elif ch == "\t":
        vk, shift = 0x09, False
    else:
        r = -1 if ord(ch) > 0xFFFF else _user32.VkKeyScanW(ch)
        state = (r >> 8) & 0xFF
        if r == -1 or state & 6:  # inconnu ou Ctrl/Alt requis : on envoie juste le caractère
            return post_char(hwnd, ch)
        vk, shift = r & 0xFF, bool(state & 1)
    scan = _user32.MapVirtualKeyW(vk, 0)
    sscan = _user32.MapVirtualKeyW(0x10, 0)
    if shift:
        _user32.PostMessageW(hwnd, WM_KEYDOWN, 0x10, _lparam(sscan))
    _user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _lparam(scan))
    post_char(hwnd, ch)
    _user32.PostMessageW(hwnd, WM_KEYUP, vk, _lparam(scan, True))
    if shift:
        _user32.PostMessageW(hwnd, WM_KEYUP, 0x10, _lparam(sscan, True))


def fake_focus(root, hwnd):
    """Fait croire à la fenêtre cible qu'elle a le focus (sans la mettre au premier plan)."""
    _user32.PostMessageW(root, WM_ACTIVATE, 1, 0)
    _user32.PostMessageW(root, WM_SETFOCUS, 0, 0)
    if hwnd != root:
        _user32.PostMessageW(hwnd, WM_SETFOCUS, 0, 0)

APP_NAME = "Feather Ghost"

# Palette
BG = "#14121f"
PANEL = "#1e1b2e"
FG = "#e8e6f5"
MUTED = "#8f8aab"
ACCENT = "#9d7bff"
ACCENT_HOVER = "#b79bff"
DANGER = "#ff6b8a"


if IS_WIN:
    _user32.VkKeyScanW.restype = ctypes.c_short
    _user32.VkKeyScanW.argtypes = [wintypes.WCHAR]

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class _INPUT_U(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_U)]

    def _scan_event(scan, up):
        i = _INPUT(type=1)
        i.ki = _KEYBDINPUT(0, scan, 0x0008 | (0x0002 if up else 0), 0, 0)  # KEYEVENTF_SCANCODE
        return i

    def _send(events):
        arr = (_INPUT * len(events))(*events)
        _user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))

    def type_char_keys(ch):
        """Tape le caractère avec de VRAIES touches (scancodes) selon la disposition du clavier.
        Renvoie False si le caractère n'existe pas sur le clavier."""
        if ord(ch) > 0xFFFF:
            return False
        vk = _user32.VkKeyScanW(ch)
        if vk == -1:
            return False
        code, state = vk & 0xFF, (vk >> 8) & 0xFF
        scan = _user32.MapVirtualKeyW(code, 0)
        if not scan:
            return False
        mods = []
        if state & 1:
            mods.append(0x2A)  # Maj
        if state & 2:
            mods.append(0x1D)  # Ctrl
        if state & 4:
            mods.append(0x38)  # Alt (Ctrl+Alt = AltGr)
        events = [_scan_event(m, False) for m in mods]
        events += [_scan_event(scan, False), _scan_event(scan, True)]
        events += [_scan_event(m, True) for m in reversed(mods)]
        _send(events)
        return True




def wordcraft_settings_dir():
    if IS_WIN:
        return os.path.join(os.environ.get("APPDATA", ""), "WordCraft")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/WordCraft")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "wordcraft")


class WordCraftLink:
    """Parle au canal de contrôle de WordCraft (lancé avec : wordcraft --control 7981).
    Le texte est injecté directement dans l'appli : elle n'a pas besoin d'être au premier plan."""

    def __init__(self, port):
        key = os.environ.get("WORDCRAFT_CONTROL_KEY")
        if not key:
            path = os.path.join(wordcraft_settings_dir(), f"control-key.local-{port}")
            with open(path, encoding="utf-8") as f:
                key = f.read().strip()
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.f = self.sock.makefile("rw", encoding="utf-8", newline="\n")
        self._id = 0
        self.call("auth", key=key)

    def call(self, method, params=None, **extra):
        self._id += 1
        msg = {"id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        msg.update(extra)
        self.f.write(json.dumps(msg) + "\n")
        self.f.flush()
        line = self.f.readline()
        if not line:
            raise ConnectionError("WordCraft a fermé la connexion.")
        reply = json.loads(line)
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "erreur WordCraft"))
        return reply.get("result")

    def text(self, t):
        self.call("ui.text", {"text": t})

    def key(self, k):
        self.call("ui.key", {"key": k})

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass


CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "FeatherGhost")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def find_wordcraft():
    """Cherche wordcraft.exe : chemin mémorisé, PATH, puis emplacements habituels."""
    saved = load_config().get("wordcraft_path")
    if saved and os.path.isfile(saved):
        return saved
    found = shutil.which("wordcraft")
    if found:
        return found
    names = ["wordcraft.exe", "WordCraft.exe"] if IS_WIN else ["wordcraft"]
    roots = []
    for var in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        v = os.environ.get(var)
        if v:
            roots += [v, os.path.join(v, "Programs")]
    roots += [os.path.expanduser("~/Downloads")]
    for root in roots:
        for sub in ("WordCraft", "wordcraft", ""):
            for n in names:
                cand = os.path.join(root, sub, n)
                if os.path.isfile(cand):
                    return cand
    return None


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class FeatherGhost(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("720x640")
        self.minsize(560, 520)
        self.configure(bg=BG)

        try:
            if sys.platform.startswith("win"):
                self.iconbitmap(resource_path("feather_ghost.ico"))
            else:
                self.iconphoto(True, tk.PhotoImage(file=resource_path("feather_ghost.png")))
        except Exception:
            pass

        self.kb = Controller()
        self.stop_event = threading.Event()
        self._bounds = (0, 0, 0, 0)
        self.target = None
        self.worker = None

        self._build_style()
        self._build_ui()

        # Raccourci global : Échap = arrêt d'urgence
        self.listener = keyboard.Listener(on_press=self._on_global_key)
        self.listener.daemon = True
        self.listener.start()

        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ------------------------------------------------------------------ UI
    def _build_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("TLabel", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        s.configure("Title.TLabel", font=("Segoe UI Semibold", 20), foreground=ACCENT)
        s.configure("TCheckbutton", background=BG, foreground=FG, font=("Segoe UI", 10))
        s.map("TCheckbutton", background=[("active", BG)])
        s.configure("Horizontal.TScale", background=BG, troughcolor=PANEL)
        s.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, background=PANEL,
                    arrowcolor=FG, bordercolor=PANEL)
        s.configure("Accent.TButton", background=ACCENT, foreground="#14121f",
                    font=("Segoe UI Semibold", 11), padding=(18, 10), borderwidth=0)
        s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#4a4466")])
        s.configure("Ghost.TButton", background=PANEL, foreground=FG,
                    font=("Segoe UI", 10), padding=(14, 10), borderwidth=0)
        s.map("Ghost.TButton", background=[("active", "#2a2640"), ("disabled", PANEL)],
              foreground=[("disabled", "#5d5878")])
        s.configure("Danger.TButton", background=PANEL, foreground=DANGER,
                    font=("Segoe UI", 10), padding=(14, 10), borderwidth=0)
        s.map("Danger.TButton", background=[("active", "#2a2640"), ("disabled", PANEL)],
              foreground=[("disabled", "#5d5878")])
        s.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT,
                    borderwidth=0, thickness=6)

    def _build_ui(self):
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)

        head = ttk.Frame(root)
        head.pack(fill="x")
        ttk.Label(head, text="✒  " + APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="Échap = arrêt d'urgence", style="Muted.TLabel").pack(side="right")

        bottom = ttk.Frame(root)
        bottom.pack(side="bottom", fill="x")

        ttk.Label(root, text="Colle ton texte ici (aucune limite de longueur) :").pack(
            anchor="w", pady=(16, 6))

        box = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground="#2e2a47")
        box.pack(fill="both", expand=True)
        self.text = tk.Text(box, wrap="word", height=6, bg=PANEL, fg=FG, insertbackground=ACCENT,
                            relief="flat", font=("Consolas", 11), padx=12, pady=10, undo=True,
                            selectbackground=ACCENT, selectforeground="#14121f")
        sb = ttk.Scrollbar(box, command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<<Modified>>", self._update_count)

        self.count_var = tk.StringVar(value="0 caractère")
        ttk.Label(bottom, textvariable=self.count_var, style="Muted.TLabel").pack(anchor="e", pady=(4, 0))

        # Réglages
        opts = ttk.Frame(bottom)
        opts.pack(fill="x", pady=(10, 0))
        opts.columnconfigure(1, weight=1)

        ttk.Label(opts, text="Vitesse").grid(row=0, column=0, sticky="w", pady=4)
        self.speed = tk.DoubleVar(value=15)
        ttk.Scale(opts, from_=1, to=100, variable=self.speed, command=self._update_speed_label
                  ).grid(row=0, column=1, sticky="ew", padx=12)
        self.speed_lbl = ttk.Label(opts, text="", style="Muted.TLabel", width=18)
        self.speed_lbl.grid(row=0, column=2, sticky="e")
        self._update_speed_label()

        ttk.Label(opts, text="Délai avant départ").grid(row=1, column=0, sticky="w", pady=4)
        dframe = ttk.Frame(opts)
        dframe.grid(row=1, column=1, sticky="w", padx=12)
        self.delay = tk.IntVar(value=1)
        ttk.Spinbox(dframe, from_=0, to=60, width=5, textvariable=self.delay).pack(side="left")
        ttk.Label(dframe, text="secondes après ton premier clic",
                  style="Muted.TLabel").pack(side="left", padx=8)

        self.human = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Rythme « humain » (légères variations de vitesse)",
                        variable=self.human).grid(row=2, column=0, columnspan=3, sticky="w", pady=2)
        self.newline_enter = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Les retours à la ligne appuient sur Entrée",
                        variable=self.newline_enter).grid(row=3, column=0, columnspan=3, sticky="w", pady=2)
        self.background = tk.BooleanVar(value=IS_WIN)
        cb = ttk.Checkbutton(opts, text="Mode arrière-plan : écrit dans la fenêtre cliquée, même si tu fais autre chose (Windows)",
                             variable=self.background)
        cb.grid(row=4, column=0, columnspan=3, sticky="w", pady=2)
        if not IS_WIN:
            cb.state(["disabled"])
        self.wc_mode = tk.BooleanVar(value=True)
        wc = ttk.Frame(opts)
        wc.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 2))
        ttk.Checkbutton(wc, text="Mode WordCraft : contrôle direct (vrai arrière-plan)",
                        variable=self.wc_mode).pack(side="left")
        ttk.Button(wc, text="▶ Ouvrir WordCraft", style="Ghost.TButton",
                   command=self.open_wordcraft).pack(side="left", padx=(12, 0))
        ttk.Label(wc, text="  port").pack(side="left")
        self.wc_port = tk.IntVar(value=7981)
        ttk.Spinbox(wc, from_=1024, to=65535, width=7, textvariable=self.wc_port).pack(side="left", padx=4)
        ttk.Label(opts, text="Utilise ce bouton pour ouvrir WordCraft en mode spécial (décoche la case pour les autres applis)",
                  style="Muted.TLabel").grid(row=6, column=0, columnspan=3, sticky="w")
        self.bind("<Configure>", self._on_configure)

        # Boutons
        btns = ttk.Frame(bottom)
        btns.pack(fill="x", pady=(12, 0))
        self.btn_start = ttk.Button(btns, text="▶  Lancer", style="Accent.TButton", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(btns, text="■  Arrêter", style="Danger.TButton",
                                   command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        ttk.Button(btns, text="Vider", style="Ghost.TButton",
                   command=lambda: self.text.delete("1.0", "end")).pack(side="right")

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x", pady=(14, 4))
        self.status = tk.StringVar(value="Prêt.")
        ttk.Label(bottom, textvariable=self.status, style="Muted.TLabel").pack(anchor="w")

    def _update_count(self, _=None):
        if self.text.edit_modified():
            n = len(self._get_text())
            self.count_var.set(f"{n:,} caractère{'s' if n > 1 else ''}".replace(",", " "))
            self.text.edit_modified(False)

    def _update_speed_label(self, _=None):
        cps = int(self.speed.get())
        self.speed_lbl.config(text=f"{cps} car./seconde")

    def _get_text(self):
        return self.text.get("1.0", "end-1c")

    # ------------------------------------------------------------- Contrôle
    def _on_configure(self, _=None):
        self._bounds = (self.winfo_rootx(), self.winfo_rooty(),
                        self.winfo_rootx() + self.winfo_width(),
                        self.winfo_rooty() + self.winfo_height())

    def start(self):
        content = self._get_text()
        if not content:
            messagebox.showinfo(APP_NAME, "Colle d'abord du texte à écrire.")
            return
        if self.worker and self.worker.is_alive():
            return
        self.stop_event.clear()
        self.click_evt = threading.Event()
        self.target = None
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.progress.config(maximum=len(content), value=0)
        self.status.set("Clique là où tu veux écrire…")

        def on_click(x, y, button, pressed):
            if not pressed:
                return None
            x0, y0, x1, y1 = self._bounds
            if x0 <= x <= x1 and y0 <= y <= y1:
                return None  # clic dans Feather Ghost : on l'ignore
            self.target = (x, y)
            self.click_evt.set()
            return False

        self.mouse_listener = mouse.Listener(on_click=on_click)
        self.mouse_listener.daemon = True
        self.mouse_listener.start()
        self.worker = threading.Thread(target=self._run, args=(content,), daemon=True)
        self.worker.start()

    def open_wordcraft(self):
        port = int(self.wc_port.get())
        try:  # déjà ouvert en mode contrôle ?
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            self.status.set("WordCraft est déjà ouvert en mode spécial. Tu peux cliquer sur « Lancer ».")
            return
        except OSError:
            pass
        path = find_wordcraft()
        if not path:
            messagebox.showinfo(APP_NAME, "Je ne trouve pas WordCraft tout seul.\n"
                                "Choisis le fichier wordcraft.exe (une seule fois, je m'en souviendrai).")
            path = filedialog.askopenfilename(title="Choisis wordcraft.exe",
                                              filetypes=[("Programme", "*.exe"), ("Tous les fichiers", "*.*")])
            if not path:
                return
        cfg = load_config()
        cfg["wordcraft_path"] = path
        save_config(cfg)
        try:
            subprocess.Popen([path, "--control", str(port)], cwd=os.path.dirname(path) or None)
            self.status.set("WordCraft s'ouvre en mode spécial… clique ensuite sur « Lancer ».")
        except Exception as e:
            messagebox.showerror(APP_NAME, f"Impossible d'ouvrir WordCraft :\n{e}")

    def stop(self):
        self.stop_event.set()

    def _on_global_key(self, key):
        if key == Key.esc and self.worker and self.worker.is_alive():
            self.stop()

    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    # --------------------------------------------------------------- Saisie
    def _sleep(self, seconds):
        """Dort par petits pas pour rester réactif à l'arrêt."""
        end = time.time() + seconds
        while time.time() < end:
            if self.stop_event.is_set():
                return False
            time.sleep(min(0.02, max(0, end - time.time())))
        return not self.stop_event.is_set()

    def _run(self, content):
        # 1) on attend le premier clic
        while not self.click_evt.wait(0.05):
            if self.stop_event.is_set():
                try:
                    self.mouse_listener.stop()
                except Exception:
                    pass
                return self._finish("Annulé.")

        use_wc = self.wc_mode.get()
        use_bg = IS_WIN and self.background.get() and not use_wc
        hwnd = window_at(*self.target) if use_bg else None
        if use_bg and not hwnd:
            return self._finish("Impossible de repérer la fenêtre cliquée.")
        root = _user32.GetAncestor(hwnd, 2) if use_bg else None

        # 2) petit délai
        for remaining in range(int(self.delay.get()), 0, -1):
            self._ui(lambda r=remaining: self.status.set(f"Départ dans {r} s…"))
            if not self._sleep(1):
                return self._finish("Arrêté avant le départ.")
        self._ui(lambda: self.status.set(
            "Écriture en arrière-plan… tu peux faire autre chose." if (use_bg or use_wc)
            else "Écriture en cours… ne change pas de fenêtre."))

        content = content.replace("\r\n", "\n").replace("\r", "\n")
        base_delay = 1.0 / max(1, self.speed.get())
        human = self.human.get()
        enter = self.newline_enter.get()
        total = len(content)

        link = None
        if use_wc:
            try:
                link = WordCraftLink(int(self.wc_port.get()))
            except FileNotFoundError:
                return self._finish("Clé WordCraft introuvable : lance-le avec  wordcraft.exe --control 7981")
            except Exception as e:
                return self._finish(f"Connexion à WordCraft impossible ({e}). Lance-le avec --control 7981")

        try:
            for i, ch in enumerate(content, 1):
                if self.stop_event.is_set():
                    return self._finish(f"Arrêté à {i - 1}/{total} caractères.")

                if use_wc:
                    if ch == "\n" and enter:
                        link.key("Enter")
                    elif ch == "\t":
                        link.key("Tab")
                    else:
                        link.text(ch)
                elif use_bg:
                    if not _user32.IsWindow(hwnd):
                        return self._finish("La fenêtre cible a été fermée.")
                    if _user32.GetForegroundWindow() != root:
                        fake_focus(root, hwnd)
                    post_key(hwnd, "\r" if (ch == "\n" and enter) else ch)
                elif ch == "\n" and enter:
                    self.kb.press(Key.enter)
                    self.kb.release(Key.enter)
                elif ch == "\t":
                    self.kb.press(Key.tab)
                    self.kb.release(Key.tab)
                elif IS_WIN:
                    if not type_char_keys(ch):
                        self.kb.type(ch)
                else:
                    self.kb.type(ch)

                if i % 5 == 0 or i == total:
                    self._ui(lambda v=i: self.progress.config(value=v))

                d = base_delay
                if human:
                    d *= random.uniform(0.5, 1.6)
                    if ch in " ,;":
                        d *= random.uniform(1.0, 1.8)
                    elif ch in ".!?\n":
                        d *= random.uniform(2.0, 4.0)
                if not self._sleep(d):
                    return self._finish(f"Arrêté à {i}/{total} caractères.")
        except Exception as e:
            return self._finish(f"Erreur : {e}")
        finally:
            if link:
                link.close()

        self._finish(f"Terminé ✔  ({total} caractères écrits)")

    def _finish(self, message):
        def done():
            self.status.set(message)
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")
        self._ui(done)

    def _quit(self):
        self.stop()
        try:
            self.listener.stop()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    FeatherGhost().mainloop()
