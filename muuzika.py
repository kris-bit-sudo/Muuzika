# -*- coding: utf-8 -*-
"""
Muuzika GPT-BETA — MP3/audio lejátszó lokális fájlokhoz és Nextcloud Music
(Subsonic API) könyvtárhoz.

Vibe-coded by kris
Függőségek: customtkinter, pygame, mutagen, tkinterdnd2, pystray, pillow
Opcionális: requests + nextcloud_music.py (Nextcloud), keyring (jelszótárolás),
            pywinstyles (Windows 11 címsorszín)
"""

from __future__ import annotations

import json
import queue
import math
from datetime import datetime
from beta_core import VERSION, LibraryStore, ShuffleOrder, profile_id, cache_filename, search_text, friendly_error
from ui_icons import transport_icon
from normalization import Normalizer, Cancelled
from retro_ui import RetroWheel
import os
import random
import sys
import tempfile
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import filedialog, messagebox

import customtkinter as ctk
import pygame
from PIL import Image, ImageDraw, ImageTk
from mutagen import File as MutagenFile
from tkinterdnd2 import DND_FILES, TkinterDnD

import pystray

# A Nextcloud támogatás opcionális: ha nincs requests vagy nextcloud_music.py,
# a lejátszó lokális módban ugyanúgy elindul.
try:
    from nextcloud_music import SubsonicClient, SubsonicError
    NEXTCLOUD_AVAILABLE = True
    NEXTCLOUD_IMPORT_ERROR = ""
except Exception as _e:          # ImportError vagy hiányzó requests
    SubsonicClient = None
    SubsonicError = Exception
    NEXTCLOUD_AVAILABLE = False
    NEXTCLOUD_IMPORT_ERROR = str(_e)

try:
    import keyring
    KEYRING_AVAILABLE = True
except Exception:
    KEYRING_AVAILABLE = False


APP_NAME = "Muuzika"
APP_VERSION = VERSION
APP_ID = "Muuzika GPT-BETA"

# ----------------------------------------------------------------------
# ÚTVONALAK
# A beállítások SOSEM a szkript mappájába mennek: az lehet írásvédett
# (pl. C:\Program Files), ilyenkor a mentés csendben elveszne.
# ----------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _app_data_dir() -> str:
    base = (os.environ.get("APPDATA")
            or os.environ.get("XDG_CONFIG_HOME")
            or os.path.join(os.path.expanduser("~"), ".config"))
    path = os.environ.get("MUUZIKA_DATA_DIR") or os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


APP_DIR = _app_data_dir()
PLAYER_DATA_FILE = os.path.join(APP_DIR, "player_data.json")
CACHE_DIR = os.path.join(APP_DIR, "cache")
LEGACY_DATA_FILE = os.path.join(SCRIPT_DIR, "player_data.json")

DEFAULT_VOLUME = 0.20
SUPPORTED_EXT = (".mp3", ".ogg", ".flac", ".wav", ".opus", ".m4a")

REPEAT_OFF, REPEAT_ALL, REPEAT_ONE = 0, 1, 2

# Windowson a Segoe UI a natív; máshol visszaesünk valami épeszűre.
# Az eredeti kinézet Arial-t használ, a szimbólumokat a Windows automatikusan
# a Segoe UI Symbol-ból pótolja.
UI_FONT = "Segoe UI" if sys.platform.startswith("win") else "Arial"
SYMBOL_FONT = "Segoe UI Symbol" if sys.platform.startswith("win") else "DejaVu Sans"

# ----------------------------------------------------------------------
# SZÍNTÉMÁK
# ----------------------------------------------------------------------
from theme_system import THEMES, DEFAULT_THEME, normalize_appearance, saved_size, MIN_WIDTH, MIN_HEIGHT
from studio_ui import StudioUI

# Aktuális színek – az update_globals_from_theme() írja felül.
COLOR_DARK_BG = THEMES[DEFAULT_THEME]["COLOR_DARK_BG"]
COLOR_MAIN_CONTAINER = THEMES[DEFAULT_THEME]["COLOR_MAIN_CONTAINER"]
COLOR_PLAYLIST_BG = THEMES[DEFAULT_THEME]["COLOR_PLAYLIST_BG"]
COLOR_BUTTON_NORMAL = THEMES[DEFAULT_THEME]["COLOR_BUTTON_NORMAL"]
COLOR_ACCENT = THEMES[DEFAULT_THEME]["COLOR_ACCENT"]
COLOR_NOW_PLAYING_TITLE = THEMES[DEFAULT_THEME]["COLOR_NOW_PLAYING_TITLE"]
COLOR_DRAG_BORDER_NORMAL = THEMES[DEFAULT_THEME]["COLOR_DRAG_BORDER_NORMAL"]
COLOR_GENERAL_FOREGROUND = THEMES[DEFAULT_THEME]["COLOR_GENERAL_FOREGROUND"]
COLOR_TEXT_DARK = THEMES[DEFAULT_THEME]["COLOR_TEXT_DARK"]


def update_globals_from_theme(theme_name: str) -> None:
    global COLOR_DARK_BG, COLOR_MAIN_CONTAINER, COLOR_PLAYLIST_BG, COLOR_BUTTON_NORMAL
    global COLOR_ACCENT, COLOR_NOW_PLAYING_TITLE, COLOR_DRAG_BORDER_NORMAL
    global COLOR_GENERAL_FOREGROUND, COLOR_TEXT_DARK
    c = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
    COLOR_DARK_BG = c["COLOR_DARK_BG"]
    COLOR_MAIN_CONTAINER = c["COLOR_MAIN_CONTAINER"]
    COLOR_PLAYLIST_BG = c["COLOR_PLAYLIST_BG"]
    COLOR_BUTTON_NORMAL = c["COLOR_BUTTON_NORMAL"]
    COLOR_ACCENT = c["COLOR_ACCENT"]
    COLOR_NOW_PLAYING_TITLE = c["COLOR_NOW_PLAYING_TITLE"]
    COLOR_DRAG_BORDER_NORMAL = c["COLOR_DRAG_BORDER_NORMAL"]
    COLOR_GENERAL_FOREGROUND = c["COLOR_GENERAL_FOREGROUND"]
    COLOR_TEXT_DARK = c["COLOR_TEXT_DARK"]


def fmt_time(seconds: float) -> str:
    """0:00 / 1:02:03 — a régi time.strftime 60 perc fölött körbefordult."""
    try:
        s = max(0, int(seconds))
    except (TypeError, ValueError):
        return "0:00"
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ----------------------------------------------------------------------
# SZÁM MODELL — lokális fájl és távoli (Subsonic) szám közös formája
# ----------------------------------------------------------------------
@dataclass
class Track:
    kind: str = "local"          # "local" vagy "remote"
    path: str = ""               # lokális fájl útvonala
    id: str = ""                 # Subsonic azonosító
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    suffix: str = "mp3"
    cover_art: str = ""          # Subsonic borító-azonosító
    source_profile: str = ""

    # --- azonosítás (duplikátum-szűréshez) ---
    @property
    def key(self) -> tuple:
        if self.kind == "local":
            return ("local", os.path.normcase(os.path.abspath(self.path)))
        return ("remote", self.source_profile, self.id)

    @property
    def is_remote(self) -> bool:
        return self.kind == "remote"

    def display_name(self) -> str:
        if self.artist and self.title:
            return f"{self.artist} – {self.title}"
        return self.title or os.path.splitext(os.path.basename(self.path))[0] or "(untitled)"

    def row_text(self, playing: bool = False) -> str:
        prefix = "▶ " if playing else "  "
        cloud = "☁ " if self.is_remote else ""
        return f"{prefix}{cloud}{self.display_name()}   ·   {fmt_time(self.duration)}"

    def cache_name(self) -> str:
        return cache_filename(self.id, self.suffix)

    # --- (de)szerializálás ---
    def to_dict(self) -> dict:
        d = {"kind": self.kind, "title": self.title, "artist": self.artist,
             "album": self.album, "duration": round(self.duration, 2)}
        if self.kind == "local":
            d["path"] = self.path
        else:
            d["id"] = self.id
            d["suffix"] = self.suffix
            d["cover_art"] = self.cover_art
            d["source_profile"] = self.source_profile
        return d

    @staticmethod
    def from_dict(d) -> "Track | None":
        # Régi formátum: a lejátszási lista sima útvonal-sztringekből állt.
        if isinstance(d, str):
            return Track.from_path(d)
        if not isinstance(d, dict):
            return None
        kind = d.get("kind", "local")
        if kind not in ("local", "remote"):
            return None
        if kind == "local":
            path = d.get("path", "")
            if not isinstance(path, str) or not path:
                return None
            t = Track(kind="local", path=path)
        else:
            if not d.get("id"):
                return None
            t = Track(kind="remote", id=str(d["id"]), suffix=str(d.get("suffix") or "mp3"),
                      cover_art=str(d.get("cover_art") or ""), source_profile=str(d.get("source_profile") or ""))
        t.title = str(d.get("title") or "")
        t.artist = str(d.get("artist") or "")
        t.album = str(d.get("album") or "")
        try:
            t.duration = float(d.get("duration") or 0)
        except (TypeError, ValueError):
            t.duration = 0.0
        if not math.isfinite(t.duration) or t.duration < 0:
            t.duration = 0.0
        if not t.title and t.kind == "local":
            t.title = os.path.splitext(os.path.basename(t.path))[0]
        return t

    @staticmethod
    def from_path(path: str) -> "Track":
        """A metaadatot EGYSZER olvassuk ki, utána a JSON-ból jön — így az
        indulás nagy listánál is azonnali."""
        t = Track(kind="local", path=path,
                  title=os.path.splitext(os.path.basename(path))[0],
                  suffix=os.path.splitext(path)[1].lstrip(".").lower() or "mp3")
        try:
            audio = MutagenFile(path)
            if audio is not None:
                if getattr(audio, "info", None) is not None:
                    t.duration = float(getattr(audio.info, "length", 0) or 0)
                tags = getattr(audio, "tags", None)
                if tags:
                    def tag(*names):
                        for n in names:
                            try:
                                v = tags.get(n)
                            except Exception:
                                v = None
                            if v:
                                return str(v[0]) if isinstance(v, list) else str(v)
                        return ""
                    t.title = tag("TIT2", "title", "\xa9nam") or t.title
                    t.artist = tag("TPE1", "TPE2", "artist", "\xa9ART")
                    t.album = tag("TALB", "album", "\xa9alb")
        except Exception:
            pass
        return t

    @staticmethod
    def from_remote(rt) -> "Track":
        return Track(kind="remote", id=rt.id, title=rt.title, artist=rt.artist,
                     album=rt.album, duration=float(rt.duration or 0),
                     suffix=rt.suffix or "mp3", cover_art=rt.cover_art or "")


def fallback_icon(size: int = 64, color: str = "#5fd685", bg: str = "#245a3a"):
    """Vész-ikon a tálcára, ha a fekete.ico nem található."""
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    r = size // 7
    d.ellipse([size * 0.22, size * 0.55, size * 0.22 + r * 2, size * 0.55 + r * 2], fill=color)
    d.ellipse([size * 0.58, size * 0.45, size * 0.58 + r * 2, size * 0.45 + r * 2], fill=color)
    d.rectangle([size * 0.22 + r * 1.7, size * 0.22, size * 0.22 + r * 2, size * 0.66], fill=color)
    d.rectangle([size * 0.58 + r * 1.7, size * 0.12, size * 0.58 + r * 2, size * 0.56], fill=color)
    d.polygon([(size * 0.22 + r * 1.7, size * 0.22), (size * 0.58 + r * 2, size * 0.12),
               (size * 0.58 + r * 2, size * 0.24), (size * 0.22 + r * 1.7, size * 0.34)], fill=color)
    return img


# ----------------------------------------------------------------------
# FŐABLAK
# Szándékosan sima TkinterDnD.Tk, NEM ctk.CTk: az eredeti kód is ezt
# használta. A ctk.CTk saját, automatikus DPI-alapú ablakskálázást vezet be,
# ami a set_widget_scaling(1.1)-gyel összeadódva a valós Windows-gépen
# jóval nagyobb ablakot eredményezett a kelleténél. Sima Tk-alapon a
# geometria pontosan azt adja, amit beállítunk.
# ----------------------------------------------------------------------
WINDOW_W, WINDOW_H = 400, 500   # default size


class MuuzikaApp(StudioUI, TkinterDnD.Tk):

    PLACEHOLDER = "Drop music here, or use + to add files."
    track_from_dict = staticmethod(Track.from_dict)
    format_time = staticmethod(fmt_time)

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_widget_scaling(1.0)

        self.title("Muuzika")
        # A geometria + resizable(False, False) TUDATOSAN a widgetek
        # létrehozása ELŐTT áll: ha ez lemarad (ez volt a korábbi hiba),
        # Tk a widgetek tényleges igénye szerint utólag felfújja az
        # ablakot, függetlenül attól, amit itt beállítunk.
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # --- állapot ---
        self.tracks: list[Track] = []
        self.current_index = -1
        self.playing = False
        self.paused = False
        self.song_length = 0.0
        self.seek_offset = 0.0          # play(start=...) miatti eltolás
        self.seeking = False
        self.drag_start_index = -1
        self.dirty_order = False
        self.repeat_mode = REPEAT_OFF
        self.shuffle = False
        self.loading = False            # épp letöltünk egy távoli számot
        self._play_token = 0            # elavult letöltések kiszűrése
        self._started_at = 0.0          # a dalvég-detektálás védőideje
        self._client = None
        self._client_lock = threading.Lock()
        self.settings_win = None
        self.browser_win = None
        self._closed = False
        self._view = "Player"
        self._appearance_draft = None
        self._resize_original = None
        self._settings_section = "Appearance"
        self._ui_queue = queue.Queue()
        self._shuffle_order = ShuffleOrder()
        self._syncing = False
        self._importing = False
        self._session_secret = ""
        self._failed_tracks = set()
        self._active_path = ""
        self._resume_position = 0.0
        self._queued_next = []
        self.library_store = LibraryStore(os.path.join(APP_DIR, "libraries"))
        self.normalizer = Normalizer(os.path.join(APP_DIR, 'normalized_audio'))

        # --- ikonok (a tálcaikon SOSEM maradhat definiálatlan) ---
        self._setup_icons()

        # --- hang ---
        self.audio_ok = True
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        except Exception as e:
            self.audio_ok = False
            print(f"Audio device error: {e}")

        # --- adatok ---
        self.load_data()
        normalize_appearance(self.preferences)
        self._apply_palette()
        width, height = saved_size(self.preferences)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.geometry(f"{width}x{height}")
        self.repeat_mode = int(self.preferences.get("repeat_mode", REPEAT_OFF))
        self.shuffle = bool(self.preferences.get("shuffle", False))

        pos = self.preferences.get("window_pos")
        if pos:
            x, y = self._clamped_position(pos)
            self.geometry(f"{width}x{height}+{x}+{y}")
        self.configure(bg=self.colors["COLOR_DARK_BG"])
        self.config(highlightthickness=0)
        self._apply_header_color()

        self.create_widgets()
        self.setup_system_tray()
        self.bind_hotkeys()

        vol = float(self.preferences.get("volume", DEFAULT_VOLUME))
        self.volume_slider.set(vol)
        self.set_volume(vol)

        self._drain_ui()
        self.update_progress()
        self.after(15000, self._autosave)

        if self.tracks:
            self.current_index = max(0, min(int(self.preferences.get("resume_index", 0)), len(self.tracks)-1))
            self.show_track_info(self.tracks[self.current_index])
            self._resume_position = max(0.0, float(self.preferences.get("resume_position", 0)))
            if self._resume_position:
                self.seek_bar.set(min(self._resume_position, max(self.song_length, 1)))
                self.time_label_start.configure(text=fmt_time(self._resume_position))
                self.set_status("Ready to resume · press Play.")
            self.refresh_rows()

        if self.preferences.get("start_minimized", False):
            self.after(200, self.withdraw)

    # ------------------------------------------------------------------
    # IKONOK
    # ------------------------------------------------------------------
    def _setup_icons(self):
        # Mindenhol (ablak, tálca, asztal) a fekete.ico.
        self.icon_path = os.path.join(SCRIPT_DIR, "fekete.ico")
        if not os.path.exists(self.icon_path):
            self.icon_path = ""

        # Biztos fallback MÉG a betöltési kísérlet előtt: enélkül egy hibás
        # ikonfájl az egész tálcaikont megölné.
        self.icon_img = fallback_icon(64)
        self.tk_icon = None

        if self.icon_path:
            try:
                self.iconbitmap(self.icon_path)
            except Exception as e:
                print(f"Icon bitmap error: {e}")
            try:
                img = Image.open(self.icon_path)
                # A .ico több méretet tartalmaz; a 32x32 réteg élesebb a tálcán,
                # mint a 256x256 lekicsinyítve.
                try:
                    img.size = (32, 32)
                    img.load()
                except Exception:
                    pass
                self.icon_img = img.convert("RGBA")
                # A wm_iconphoto a Toplevel ablakokra is érvényes.
                self.tk_icon = ImageTk.PhotoImage(Image.open(self.icon_path).convert("RGBA"))
                self.wm_iconphoto(True, self.tk_icon)
            except Exception as e:
                print(f"Icon load error: {e}")

    def _apply_header_color(self):
        try:
            import pywinstyles
            pywinstyles.change_header_color(self, color=self.colors["TITLEBAR"])
        except Exception:
            pass

    def _clamped_position(self, pos: dict) -> tuple[int, int]:
        """Ne nyíljon a képernyőn kívül, ha megváltozott a monitorelrendezés."""
        x, y = int(pos.get("x", 100)), int(pos.get("y", 100))
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x, sw - 200))
        y = max(0, min(y, sh - 200))
        return x, y

    # ------------------------------------------------------------------
    # TÁLCAIKON — minden Tk-hívás a fő szálra terelve
    # ------------------------------------------------------------------
    def setup_system_tray(self):
        def ui(fn):
            return lambda icon=None, item=None: self.ui_call(fn)

        menu = pystray.Menu(
            pystray.MenuItem("Show / Hide Muuzika", ui(self.toggle_window), default=True),
            pystray.MenuItem("Previous", ui(self.prev_song)),
            pystray.MenuItem("Play / Pause", ui(self.toggle_play_pause)),
            pystray.MenuItem("Next", ui(self.next_song)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", ui(self.on_closing)),
        )
        try:
            self.tray_icon = pystray.Icon(APP_NAME, self.icon_img, f"{APP_NAME} Player", menu)

            def _run_tray():
                try:
                    self.tray_icon.run()
                except Exception as e:
                    print(f"Tray icon stopped: {e}")

            self.tray_thread = threading.Thread(target=_run_tray, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            self.tray_icon = None
            print(f"Tray icon failed to start: {e}")

    def toggle_window(self):
        if self.state() == "withdrawn":
            self.deiconify()
            self.lift()
            self.focus_force()
        else:
            self.withdraw()

    def minimize_to_tray(self):
        self.withdraw()

    def on_closing(self):
        self._closed = True
        self._play_token += 1
        try:
            self.save_data()
        finally:
            if getattr(self, "tray_icon", None):
                try:
                    self.tray_icon.stop()
                except Exception:
                    pass
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass
            for callback in self.tk.splitlist(self.tk.call('after', 'info')):
                self.after_cancel(callback)
            self.destroy()

    # ------------------------------------------------------------------
    # ADATOK
    # ------------------------------------------------------------------
    def load_data(self):
        self.preferences = {
            "normalize_volume": False,
            "volume": DEFAULT_VOLUME,
            "theme": DEFAULT_THEME,
            "start_minimized": False,
            "repeat_mode": REPEAT_OFF,
            "shuffle": False,
            "nc_url": "",
            "nc_user": "",
            "nc_verify_tls": True,
            "nc_cache_mb": 2048,
        }
        self.tracks = []

        source = PLAYER_DATA_FILE
        if not os.path.exists(source) and os.path.exists(LEGACY_DATA_FILE):
            source = LEGACY_DATA_FILE      # egyszeri átvétel a régi helyről

        if not os.path.exists(source):
            return

        try:
            with open(source, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Cannot read saved data ({e}); using defaults.")
            return

        if isinstance(data, dict):
            if "volume" in data and "preferences" not in data:     # nagyon régi formátum
                self.preferences["volume"] = data.get("volume", DEFAULT_VOLUME)
            prefs = data.get("preferences", {})
            if isinstance(prefs, dict):
                self.preferences.update(prefs)

            playlist = data.get("playlist", [])
            for entry in playlist if isinstance(playlist, list) else []:
                t = Track.from_dict(entry)
                if t is None:
                    continue
                # A hiányzó helyi fájl is megmarad: pl. kihúzott külső meghajtó.
                if t.kind == "local" and not os.path.exists(t.path):
                    self._failed_tracks.add(t.key)
                self.tracks.append(t)

        try:
            v = float(self.preferences.get("volume", DEFAULT_VOLUME))
        except (TypeError, ValueError):
            v = DEFAULT_VOLUME
        self.preferences["volume"] = v if 0.0 <= v <= 1.0 else DEFAULT_VOLUME
        for key, default, minimum, maximum in (
            ("repeat_mode", REPEAT_OFF, 0, 2), ("resume_index", 0, 0, 10000000),
            ("nc_cache_mb", 2048, 64, 1048576)):
            try:
                self.preferences[key] = max(minimum, min(maximum, int(self.preferences.get(key, default))))
            except (TypeError, ValueError, OverflowError):
                self.preferences[key] = default
        try:
            position = float(self.preferences.get("resume_position", 0))
            self.preferences["resume_position"] = max(0, position) if math.isfinite(position) else 0
        except (TypeError, ValueError):
            self.preferences["resume_position"] = 0
        if not isinstance(self.preferences.get("window_pos"), dict):
            self.preferences.pop("window_pos", None)
        else:
            try:
                for axis in ("x", "y"):
                    self.preferences["window_pos"][axis] = int(self.preferences["window_pos"].get(axis, 100))
            except (TypeError, ValueError, OverflowError):
                self.preferences.pop("window_pos", None)
        for key in ("nc_url", "nc_user"):
            self.preferences[key] = str(self.preferences.get(key) or "")
        self.preferences.pop("nc_password", None)

    def save_data(self):
        if hasattr(self, "volume_slider"):
            self.preferences["volume"] = round(float(self.volume_slider.get()), 3)
        self.preferences["repeat_mode"] = self.repeat_mode
        self.preferences["shuffle"] = self.shuffle
        try:
            if self.state() == "normal":
                self.preferences["window_pos"] = {"x": self.winfo_x(), "y": self.winfo_y()}
        except Exception:
            pass

        self.preferences["resume_index"] = self.current_index
        self.preferences["resume_position"] = self.current_position() if self.playing else self._resume_position
        data = {
            "schema": 3,
            "playlist": [t.to_dict() for t in self.tracks],
            "preferences": self.preferences,
        }
        # Atomi írás: félbeszakadt mentés ne tegye tönkre a listát.
        try:
            fd, tmp = tempfile.mkstemp(dir=APP_DIR, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, PLAYER_DATA_FILE)
        except Exception as e:
            print(f"Save error: {e}")

    # ------------------------------------------------------------------
    # FELÜLET
    # ------------------------------------------------------------------






    def _bind_volume_wheel(self, *extra_widgets):
        """Görgő a teljes hangerő-területen. A csúszkánál a canvasra kötünk
        (add nélkül), különben a CustomTkinter saját görgőkezelője is lefutna,
        és duplán lépne a hangerő."""
        for w in extra_widgets:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                try:
                    w.bind(seq, self.on_mousewheel)
                except Exception:
                    pass
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                self.volume_slider.bind(seq, self.on_mousewheel)
            except Exception:
                pass
            try:
                self.volume_slider._canvas.bind(seq, self.on_mousewheel)
            except Exception:
                pass

    def bind_hotkeys(self):
        self.bind("<Button-1>", self.dismiss_search_on_click, add="+")
        # A szóköz ne lőjön el, ha épp egy beviteli mezőbe gépelnek.
        def not_in_entry():
            try:
                w = self.focus_get()
            except Exception:
                return True
            return not isinstance(w, (tk.Entry, ctk.CTkEntry))

        self.bind("<space>", lambda e: self.toggle_play_pause() if not_in_entry() else None)
        self.bind("<Right>", lambda e: self.next_song() if not_in_entry() else None)
        self.bind("<Left>", lambda e: self.prev_song() if not_in_entry() else None)
        # Ctrl+fel/le: a sima fel/le a listában a kijelölést mozgatja,
        # korábban egyszerre csinálta mindkettőt.
        self.bind("<Control-Up>", lambda e: self.change_volume(0.05))
        self.bind("<Control-Down>", lambda e: self.change_volume(-0.05))
        self.bind("<Shift-Up>", lambda e: self.move_selected(-1))
        self.bind("<Shift-Down>", lambda e: self.move_selected(1))
        self.bind("<Control-f>", lambda e: self.show_list_search())
        self.bind("<Control-o>", lambda e: self.add_files())


    def ui_call(self, fn):
        if not self._closed:
            self._ui_queue.put(fn)


    # ------------------------------------------------------------------
    # HANGERŐ / MÓDOK
    # ------------------------------------------------------------------
    def set_volume(self, val):
        try:
            volume = max(0.0, min(1.0, float(val)))
        except (TypeError, ValueError):
            return
        if self.audio_ok:
            pygame.mixer.music.set_volume(volume)
        self.volume_label.configure(text=f"{int(round(volume * 100))}%")

    def change_volume(self, amount):
        new_vol = max(0.0, min(1.0, round(self.volume_slider.get() + amount, 2)))
        self.volume_slider.set(new_vol)
        self.set_volume(new_vol)

    def on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            steps = 1
        elif getattr(event, "num", None) == 5:
            steps = -1
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return "break"
            steps = (1 if delta > 0 else -1) * max(1, int(abs(delta) / 120))
        # Move to the next 5% boundary in the scroll direction, not by +5%.
        units = round(float(self.volume_slider.get()) * 20, 8)
        target = math.floor(units) + steps if steps > 0 else math.ceil(units) + steps
        volume = max(0, min(20, target)) / 20
        self.volume_slider.set(volume)
        self.set_volume(volume)
        return "break"

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        current = self.tracks[self.current_index].key if 0 <= self.current_index < len(self.tracks) else None
        self._shuffle_order.reset([t.key for t in self.tracks], current)
        self.update_mode_buttons()
        self.save_data()

    def cycle_repeat(self):
        self.repeat_mode = (self.repeat_mode + 1) % 3
        self.update_mode_buttons()
        self.save_data()


    def set_button_icon(self, button, kind, color):
        size=16 if button.cget('width')<=24 else 18
        icon = ctk.CTkImage(transport_icon(kind, color), size=(size, size))
        self._button_images[str(button)] = icon
        button.configure(require_redraw=True, text="", image=icon)


    # ------------------------------------------------------------------
    # LEJÁTSZÁS
    # ------------------------------------------------------------------
    def show_track_info(self, track: Track, status: str = ""):
        self.song_length = float(track.duration or 0)
        name = track.display_name()
        self.song_label.configure(text=name if len(name) <= 48 else name[:47] + "…")
        self.title("Muuzika")
        self.time_label_end.configure(text=fmt_time(self.song_length))
        self.time_label_start.configure(text="0:00")
        # to=0 esetén a CTkSlider set()-je nullával osztana → ZeroDivisionError
        self.seek_bar.configure(to=max(self.song_length, 1))
        self.seek_bar.set(0)
        self.set_status(status)

    def play_index(self, index: int, start_at: float = 0.0, from_order=False):
        if not self.tracks or not (0 <= index < len(self.tracks)):
            return
        if not self.audio_ok:
            self.set_status("No audio device is available. Connect one and restart Muuzika.")
            return
        self.stop_song()
        token = self._play_token
        self.current_index = index
        track = self.tracks[index]
        if not from_order:
            self._shuffle_order.reset([t.key for t in self.tracks], track.key)
        self._resume_position = start_at
        self.show_track_info(track)
        self.refresh_rows()
        if not track.is_remote:
            self._start_file(track.path, token, start_at)
            return
        cached = self.cache_path(track)
        if os.path.isfile(cached) and os.path.getsize(cached) > 0:
            os.utime(cached, None)
            self._start_file(cached, token, start_at)
            return
        if track.source_profile != self.active_profile():
            self.set_status("This track belongs to another server or account. Restore that connection to download it.")
            return
        client = self.get_client()
        if client is None:
            self.set_status("Configure your Nextcloud connection in Settings.")
            return
        self.loading = True
        self.play_pause_btn.configure(state="disabled")
        self.set_status("Downloading audio… Stop cancels playback after the download.")
        cache_dir = os.path.dirname(cached)
        def worker():
            last = [0.0]
            def progress(done, total):
                now = time.monotonic()
                if now - last[0] < .2:
                    return
                last[0] = now
                label = f"Download · {done * 100 // total}%" if total else f"Download · {done / 1024 / 1024:.1f} MB"
                self.ui_call(lambda msg=label: self.set_status(msg) if token == self._play_token else None)
            try:
                path = client.download_to_cache(_as_remote(track), cache_dir, progress=progress)
            except Exception as error:
                self.ui_call(lambda err=error: self._remote_failed(token, err))
                return
            self.ui_call(lambda: self._remote_ready(token, path, start_at))
        threading.Thread(target=worker, daemon=True).start()

    def _remote_ready(self, token, path, start_at):
        if token != self._play_token:
            return
        self.loading = False
        self.play_pause_btn.configure(state="normal")
        self.set_status("")
        self._start_file(path, token, start_at)
        if SubsonicClient:
            SubsonicClient.prune_cache(os.path.dirname(path),
                int(self.preferences.get("nc_cache_mb", 2048)) * 1024 * 1024, protected=(path,))

    def _remote_failed(self, token, err):
        if token != self._play_token:
            return
        self.loading = False
        self.play_pause_btn.configure(state="normal")
        self.update_play_button()
        self.set_status(friendly_error(err))

    def _start_file(self, path, token, start_at=0.0, prepared=False):
        if token != self._play_token:
            return
        if self.preferences.get('normalize_volume',False) and not prepared:
            self.loading=True
            self.play_pause_btn.configure(state='disabled')
            self.status_label.configure(text='Preparing volume…')
            def worker():
                try:
                    result=self.normalizer.prepare(path,lambda:token!=self._play_token or self._closed)
                except Cancelled:
                    return
                except Exception:
                    self.ui_call(lambda:self._normalization_ready(token,None,start_at))
                    return
                self.ui_call(lambda:self._normalization_ready(token,result,start_at))
            threading.Thread(target=worker,daemon=True).start()
            return
        try:
            pygame.mixer.music.load(path)
            # SDL_mixer resets music volume when loading a new stream.
            self.set_volume(self.volume_slider.get())
            if start_at > 0:
                try:
                    pygame.mixer.music.play(start=start_at)
                except pygame.error:
                    pygame.mixer.music.play()
                    start_at = 0.0
                    self.set_status("Resume is unavailable for this audio format; playing from the start.")
            else:
                pygame.mixer.music.play()
        except Exception as e:
            self.handle_playback_error(self.current_index, e)
            return

        self._active_path = path
        self._resume_position = 0.0
        self._failed_tracks.discard(self.tracks[self.current_index].key)
        self.seek_offset = start_at
        self._started_at = time.monotonic()
        self.playing = True
        self.paused = False
        self.update_play_button()
        self.refresh_rows()

        if 0 <= self.current_index < len(self.tracks):
            t = self.tracks[self.current_index]
            # A hossz pontosítása, ha a metaadat hiányzott.
            if self.song_length <= 0:
                try:
                    info = MutagenFile(path)
                    if info is not None and getattr(info, "info", None):
                        t.duration = float(info.info.length)
                        self.song_length = t.duration
                        self.seek_bar.configure(to=max(self.song_length, 1))
                        self.time_label_end.configure(text=fmt_time(self.song_length))
                except Exception:
                    pass
        self.save_data()

    def _normalization_ready(self, token, path, start_at):
        if token != self._play_token or self._closed: return
        self.loading=False
        self.play_pause_btn.configure(state='normal')
        self.status_label.configure(text='')
        if path is None:
            self.show_notice('Cannot normalize this track. Retry it, or turn off Normalize volume in Settings > Audio to play the original.')
            return
        self._start_file(path,token,start_at,prepared=True)

    def _scrobble(self, track_id):
        # Manual-sync edition: never send listening activity to the server.
        return

    def handle_playback_error(self, index, err):
        if not (0 <= index < len(self.tracks)):
            return
        track = self.tracks[index]
        self.stop_song()
        self._failed_tracks.add(track.key)
        self.refresh_rows()
        self.set_status("Cannot play: " + track.display_name() + ". The track remains in your playlist. Retry it or choose another track.")

    def prefetch_next(self):
        # No automatic downloads: only explicitly selected/played audio is fetched.
        return

    def toggle_play_pause(self):
        if not self.tracks:
            return
        if self.loading:
            return
        if self.playing:
            if self.paused:
                pygame.mixer.music.unpause()
                self.paused = False
            else:
                pygame.mixer.music.pause()
                self.paused = True
            self.update_play_button()
            return

        sel = self.playlist_box.curselection()
        index = sel[0] if sel else (self.current_index if self.current_index >= 0 else 0)
        self.play_index(index, self._resume_position if index == self.current_index else 0)

    def stop_song(self):
        self._play_token += 1          # a folyamatban lévő letöltés se induljon el
        self.status_label.configure(text='')
        self.loading = False
        self._resume_position = 0.0
        self._active_path = ""
        self.play_pause_btn.configure(state="normal")
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.playing = False
        self.paused = False
        self.seek_offset = 0.0
        self.update_play_button()
        self.seek_bar.set(0)
        self.time_label_start.configure(text="0:00")
        self.set_status("")

    def _step(self, direction: int, auto: bool = False):
        if not self.tracks:
            return
        if direction > 0 and self._queued_next:
            keys = [t.key for t in self.tracks]
            while self._queued_next:
                key = self._queued_next.pop(0)
                if key in keys:
                    self.play_index(keys.index(key))
                    return
        if self.current_index < 0:
            self.play_index(0)
            return
        if self.shuffle:
            keys = [t.key for t in self.tracks]
            current = keys[self.current_index]
            if set(keys) != self._shuffle_order.known:
                self._shuffle_order.reset(keys, current)
            key = (self._shuffle_order.previous() if direction < 0 else
                   self._shuffle_order.next(keys, current, repeat=self.repeat_mode == REPEAT_ALL))
            if key is None:
                if direction > 0:
                    self.stop_song()
                    self.set_status("End of shuffled playlist.")
                return
            self.play_index(keys.index(key), from_order=True)
            return
        nxt = self.current_index + direction
        if auto and direction > 0 and nxt >= len(self.tracks) and self.repeat_mode == REPEAT_OFF:
            self.stop_song()
            return
        self.play_index(nxt % len(self.tracks))

    def next_song(self):
        self._step(1)

    def prev_song(self):
        # 3 másodperc után a "előző" a dal elejére ugrik, mint a rendes lejátszókban
        if self.playing and self.current_position() > 3:
            self.play_index(self.current_index, from_order=True)
            return
        self._step(-1)

    def play_selected(self):
        sel = self.playlist_box.curselection()
        if sel:
            self.play_index(sel[0])

    def current_position(self) -> float:
        if not self.playing:
            return 0.0
        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            return self.seek_offset
        return self.seek_offset + pos / 1000.0

    # ------------------------------------------------------------------
    # TEKERÉS
    # ------------------------------------------------------------------
    def start_seeking(self, event=None):
        if self.playing and self.song_length > 0:
            self.seeking = True

    def on_seek_drag(self, val):
        if self.seeking and self.song_length > 0:
            self.time_label_start.configure(text=fmt_time(float(val)))

    def finish_seeking(self, event=None):
        if not self.seeking:
            return
        self.seeking = False
        if self.current_index < 0 or self.song_length <= 0:
            return
        was_paused = self.paused
        new_time = float(self.seek_bar.get())
        track = self.tracks[self.current_index]
        path = track.path if track.kind == "local" else self.cache_path(track)
        if not os.path.exists(path):
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play(start=new_time)
            self.seek_offset = new_time
            self._started_at = time.monotonic()
            self.playing = True
            self.paused = False
            if was_paused:                     # szünetben maradunk, ha ott voltunk
                pygame.mixer.music.pause()
                self.paused = True
            self.update_play_button()
        except Exception as e:
            print(f"Seek error: {e}")

    def update_progress(self):
        if getattr(self, '_rebuilding_ui', False):
            self.after(200, self.update_progress)
            return
        if self.playing and not self.paused and not self.loading:
            busy = pygame.mixer.music.get_busy()
            # Az indítás utáni első fél másodpercben a get_busy() néha még
            # hamis - ilyenkor ne ugorjunk véletlenül a következő számra.
            if not busy and (time.monotonic() - self._started_at) > 0.5:
                if self.repeat_mode == REPEAT_ONE:
                    self.play_index(self.current_index, from_order=True)
                else:
                    self._step(1, auto=True)
            elif busy and not self.seeking and self.song_length > 0:
                pos = self.current_position()
                self.seek_bar.set(min(pos, self.song_length))
                self.time_label_start.configure(text=fmt_time(pos))
        self.after(200, self.update_progress)

    # ------------------------------------------------------------------
    # LISTAKEZELÉS
    # ------------------------------------------------------------------
    def refresh_rows(self):
        box = self.playlist_box
        try:
            top = box.yview()[0]
        except Exception:
            top = 0.0
        sel = [i for i in box.curselection()]
        box.delete(0, tk.END)

        if not self.tracks:
            box.insert(tk.END, self.PLACEHOLDER)
            box.configure(fg=self.colors["COLOR_DRAG_BORDER_NORMAL"])
            return

        box.configure(fg=self.colors["LIST_TEXT"])
        for i, t in enumerate(self.tracks):
            text = t.row_text(playing=(i == self.current_index and self.playing))
            if t.key in self._failed_tracks:
                text = "! " + text.lstrip()
            box.insert(tk.END, text)
            if i == self.current_index:
                box.itemconfigure(i, bg=self.colors["CURRENT_BG"], fg=self.colors["CURRENT_TEXT"])

        for i in sel:
            if i < len(self.tracks):
                box.selection_set(i)
        if not sel and 0 <= self.current_index < len(self.tracks):
            box.selection_set(self.current_index)
            box.see(self.current_index)
        if sel:
            box.yview_moveto(top)

    def add_tracks(self, new_tracks, announce=True):
        existing = {t.key for t in self.tracks}
        added = 0
        for t in new_tracks:
            if t.key in existing:
                continue
            existing.add(t.key)
            self.tracks.append(t)
            added += 1
        if added:
            self.refresh_rows()
            self.save_data()
            if announce:
                self.set_status(f"{added} tracks added.")
        elif announce:
            self.set_status("No new tracks added; they are already in the playlist.")
        return added

    def add_files(self):
        paths = filedialog.askopenfilenames(title="Choose audio files",
            filetypes=(("Audio files", " ".join("*" + e for e in SUPPORTED_EXT)), ("All files", "*.*")))
        if paths:
            self.import_paths(paths)

    def drop_files(self, event):
        self.import_paths(self._parse_dnd(event.data))

    def _parse_dnd(self, data):
        try:
            return list(self.tk.splitlist(data))
        except tk.TclError:
            return data.strip("{}").split()

    def delete_selected(self, event=None):
        if not self.tracks:
            return
        indices = sorted(self.playlist_box.curselection(), reverse=True)
        if not indices:
            return
        stop_needed = self.current_index in indices
        for i in indices:
            if 0 <= i < len(self.tracks):
                self.tracks.pop(i)
                if i < self.current_index:
                    self.current_index -= 1
        if stop_needed:
            self.stop_song()
            self.current_index = min(indices[-1], len(self.tracks) - 1) if self.tracks else -1
            if self.current_index >= 0:
                self.show_track_info(self.tracks[self.current_index])
            else:
                self.song_label.configure(text="Choose a track")
                self.title("Muuzika")
        elif not self.tracks:
            self.current_index = -1
        self.refresh_rows()
        self.save_data()

    def move_selected(self, direction):
        sel = self.playlist_box.curselection()
        if not sel or not self.tracks:
            return "break"
        idx = sel[0]
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.tracks)):
            return "break"
        self.tracks[idx], self.tracks[new_idx] = self.tracks[new_idx], self.tracks[idx]
        if self.current_index == idx:
            self.current_index = new_idx
        elif self.current_index == new_idx:
            self.current_index = idx
        self.refresh_rows()
        self.playlist_box.selection_clear(0, tk.END)
        self.playlist_box.selection_set(new_idx)
        self.playlist_box.see(new_idx)
        self.save_data()
        return "break"

    def on_press(self, event):
        self.drag_start_index = self.playlist_box.nearest(event.y) if self.tracks else -1
        self._press_position = (event.x, event.y)
        self._press_modified = bool(event.state & (0x0001 | 0x0004))
        self._did_drag = False

    def on_drag(self, event):
        origin = getattr(self, "_press_position", (event.x, event.y))
        if abs(event.x - origin[0]) + abs(event.y - origin[1]) < 5:
            return
        self._did_drag = True
        if self.drag_start_index < 0 or not self.tracks:
            return
        new_index = self.playlist_box.nearest(event.y)
        if new_index == self.drag_start_index or not (0 <= new_index < len(self.tracks)):
            return
        track = self.tracks.pop(self.drag_start_index)
        self.tracks.insert(new_index, track)

        if self.current_index == self.drag_start_index:
            self.current_index = new_index
        elif self.drag_start_index < self.current_index <= new_index:
            self.current_index -= 1
        elif new_index <= self.current_index < self.drag_start_index:
            self.current_index += 1

        self.drag_start_index = new_index
        self.dirty_order = True
        self.refresh_rows()
        self.playlist_box.selection_clear(0, tk.END)
        self.playlist_box.selection_set(new_index)

    def on_drop_reorder(self, event=None):
        # Mentés csak az egér elengedésekor, nem minden mozdulatnál.
        if self.dirty_order:
            self.dirty_order = False
            self.save_data()
            return
        if event is None or not self.tracks or getattr(self, "_did_drag", False) or getattr(self, "_press_modified", False):
            return
        index = self.playlist_box.nearest(event.y)
        box = self.playlist_box.bbox(index)
        if box and box[1] <= event.y < box[1] + box[3]:
            # Do not restart the same song on the second click of a double click.
            if index != self.current_index or not self.playing:
                self.play_index(index)
            elif self.paused:
                self.toggle_play_pause()

    def dismiss_search_on_click(self, event):
        if not self.list_search.winfo_ismapped():
            return
        # CTk events originate in nested canvases/entries; compare ancestry.
        widget = event.widget
        while widget is not None:
            if widget in (self.list_search, self.search_button):
                return
            widget = getattr(widget, "master", None)
        self.hide_list_search(restore_focus=True)

    # ------------------------------------------------------------------
    # NEXTCLOUD
    # ------------------------------------------------------------------
    def _get_secret(self) -> str:
        if self._session_secret:
            return self._session_secret
        if KEYRING_AVAILABLE:
            try:
                return keyring.get_password(APP_ID, self.active_profile()) or ""
            except Exception:
                pass
        return ""

    def _set_secret(self, value: str):
        self._session_secret = value
        self.preferences.pop("nc_password", None)
        if KEYRING_AVAILABLE:
            try:
                keyring.set_password(APP_ID, self.active_profile(), value)
                return True
            except Exception:
                pass
        self.set_status("The password is only kept for this session; Windows credential storage is unavailable.")
        return False

    def get_client(self):
        if not NEXTCLOUD_AVAILABLE:
            return None
        url = self.preferences.get("nc_url", "").strip()
        user = self.preferences.get("nc_user", "").strip()
        pwd = self._get_secret()
        if not (url and user and pwd):
            return None
        with self._client_lock:
            sig = (url, user, pwd, bool(self.preferences.get("nc_verify_tls", True)))
            if self._client is None or getattr(self._client, "_sig", None) != sig:
                try:
                    self._client = SubsonicClient(
                        url, username=user, password=pwd,
                        verify_tls=bool(self.preferences.get("nc_verify_tls", True)))
                except ValueError:
                    return None
                self._client._sig = sig
            return self._client

    def invalidate_client(self):
        with self._client_lock:
            self._client = None


    def _safe_iconbitmap(self, window):
        try:
            window.iconbitmap(self.icon_path)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # BEÁLLÍTÁSOK
    # ------------------------------------------------------------------

    def _cache_info(self) -> str:
        total, count = 0, 0
        directory = os.path.join(CACHE_DIR, self.active_profile())
        if os.path.isdir(directory):
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                if os.path.isfile(path) and not name.endswith((".part", ".tmp")):
                    try:
                        total += os.path.getsize(path)
                        count += 1
                    except OSError:
                        pass
        return f"Offline: {count} tracks · {total / 1024 / 1024:.1f} MB"


    def active_profile(self):
        return profile_id(self.preferences.get("nc_url", ""), self.preferences.get("nc_user", ""))

    def cache_path(self, track):
        profile = track.source_profile
        if len(profile) != 24 or any(c not in "0123456789abcdef" for c in profile):
            profile = "unassigned"
        return os.path.join(CACHE_DIR, profile, track.cache_name())

    def _drain_ui(self):
        if self._closed:
            return
        for _ in range(100):
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as error:
                self.set_status(friendly_error(error))
        self.after(50, self._drain_ui)

    def _autosave(self):
        if self._closed:
            return
        if self.playing:
            self.save_data()
        self.after(15000, self._autosave)

    def set_sync_busy(self, busy):
        for name in ('sync_button','library_sync_button','library_missing_button'):
            button=getattr(self,name,None)
            if button is not None and button.winfo_exists():
                button.configure(state='disabled' if busy else 'normal')

    def sync_library(self, add_missing=False):
        if self._syncing:
            self.set_status("Sync is already in progress.")
            return
        client = self.get_client()
        if client is None:
            self.set_status("Configure your Nextcloud connection in Settings first.")
            self.open_settings()
            return
        profile = self.active_profile()
        self._syncing = True
        self.hide_tooltip()
        self.set_sync_busy(True)
        self.set_status("Fetching library… The current local copy is kept until sync succeeds.")
        def progress(count):
            self.ui_call(lambda: self.set_status(f"Syncing · {count} tracks")
                         if profile == self.active_profile() else None)
        def worker():
            try:
                remote = client.all_songs(progress=progress)
                tracks = [Track.from_remote(rt) for rt in remote]
                for track in tracks:
                    track.source_profile = profile
                # Persistence is completed before the UI reports success.
                self.library_store.save(profile, [t.to_dict() for t in tracks])
            except Exception as error:
                self.ui_call(lambda err=error: finish(None, err))
                return
            self.ui_call(lambda: finish(tracks, None))
        def finish(tracks, error):
            self._syncing = False
            self.set_sync_busy(False)
            if profile != self.active_profile():
                self.set_status("Previous connection sync finished. You can now sync the new connection.")
                return
            if error is not None:
                self.set_status(friendly_error(error) + " Your previous library was preserved.")
                return
            self.set_status(f"Sync complete · {len(tracks)} tracks. Open Library to browse.")
            reload_library = getattr(self, "_reload_library", None)
            if reload_library:
                reload_library()
            if add_missing:
                added=self.add_tracks(tracks,announce=False)
                status=getattr(self,'library_status',None)
                if status is not None and status.winfo_exists():
                    status.configure(text=f'{added} missing tracks added.' if added else 'Your playlist is already up to date.')
        threading.Thread(target=worker, daemon=True).start()


    def find_in_queue(self, event=None, direction=1):
        query = search_text(self.list_search.get().strip())
        if not query:
            self._search_query=''
            self._search_index=None
            self.search_count.configure(text='')
            return "break"
        matches=[i for i,t in enumerate(self.tracks)
                 if all(word in search_text(f'{t.title} {t.artist} {t.album}') for word in query.split())]
        previous=getattr(self,'_search_index',None)
        same=query==getattr(self,'_search_query','')
        self._search_query=query
        if not matches:
            self._search_index=None
            self.search_count.configure(text='0/0')
            return 'break'
        position=(matches.index(previous)+direction)%len(matches) if same and previous in matches else (len(matches)-1 if direction<0 else 0)
        index=matches[position]
        self._search_index=index
        self.playlist_box.selection_clear(0,tk.END)
        self.playlist_box.selection_set(index)
        self.playlist_box.see(index)
        self.search_count.configure(text=f'{position+1}/{len(matches)}')
        return "break"

    def queue_menu(self, event):
        if not self.tracks:
            return
        index = self.playlist_box.nearest(event.y)
        self.playlist_box.selection_clear(0, tk.END)
        self.playlist_box.selection_set(index)
        menu = tk.Menu(self, tearoff=False, bg=self.colors["COLOR_PLAYLIST_BG"], fg=self.colors["LIST_TEXT"])
        menu.add_command(label="Play / Retry", command=lambda: self.play_index(index))
        def enqueue():
            key = self.tracks[index].key
            self._queued_next.append(key)
            self.set_status("Up next: " + self.tracks[index].display_name())
        menu.add_command(label="Play next", command=enqueue)
        menu.add_separator()
        menu.add_command(label="Remove from playlist", command=self.delete_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def import_paths(self, paths):
        if self._importing:
            self.set_status("File import is already in progress.")
            return
        self._importing = True
        self.set_status("Reading audio files…")
        def worker():
            tracks = []
            try:
                for raw in paths:
                    path = str(raw).strip()
                    if os.path.isdir(path):
                        for root, _, names in os.walk(path):
                            if self._closed:
                                return
                            for name in sorted(names):
                                if name.lower().endswith(SUPPORTED_EXT):
                                    tracks.append(Track.from_path(os.path.join(root, name)))
                    elif os.path.isfile(path) and path.lower().endswith(SUPPORTED_EXT):
                        tracks.append(Track.from_path(path))
            except Exception as error:
                self.ui_call(lambda err=error: finish([], err))
                return
            self.ui_call(lambda: finish(tracks, None))
        def finish(tracks, error):
            self._importing = False
            if error:
                self.set_status(friendly_error(error))
            elif tracks:
                self.add_tracks(tracks)
            else:
                self.set_status("No supported audio files found.")
        threading.Thread(target=worker, daemon=True).start()


def _as_remote(track: Track):
    """Track -> RemoteTrack a nextcloud_music modul letöltőjéhez."""
    from nextcloud_music import RemoteTrack
    return RemoteTrack(id=track.id, title=track.title, artist=track.artist,
                       album=track.album, duration=int(track.duration or 0),
                       suffix=track.suffix or "mp3", cover_art=track.cover_art or None)


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)
    app = MuuzikaApp()
    app.mainloop()
