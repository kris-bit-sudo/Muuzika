"""Offline library storage and playback order; no GUI or network side effects."""
from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

VERSION = "3.1.0-beta3"


def profile_id(url: str, username: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith("/rest"):
        url = url[:-5]
    parts = urlsplit(url)
    canonical = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))
    return hashlib.sha256((canonical + "\n" + username.strip()).encode()).hexdigest()[:24]


def cache_filename(track_id: str, suffix: str) -> str:
    suffix = suffix.lower()
    if suffix not in {"mp3", "ogg", "flac", "wav", "opus", "m4a", "aac", "mp4"}:
        suffix = "audio"
    return hashlib.sha256(str(track_id).encode()).hexdigest() + "." + suffix


def search_text(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(c))


def friendly_error(error: Exception) -> str:
    """Never expose requests' URLs (which contain the API password)."""
    name = type(error).__name__
    if "SSL" in name:
        return "Certificate verification failed. Check your connection settings."
    if "Timeout" in name:
        return "The server did not respond in time. Try again."
    if "Connection" in name:
        return "The server is unavailable. Previously downloaded tracks can still be played."
    if hasattr(error, "code"):
        return f"The server rejected the request (code: {error.code})."
    if name == "HTTPError":
        response = getattr(error, "response", None)
        code = getattr(response, "status_code", "?")
        return f"Server error (HTTP {code}). Check the URL and access credentials."
    if isinstance(error, OSError):
        return "The file cannot be read or saved. Check free space and file permissions."
    return "The operation failed. Check the connection or audio file and try again."


def atomic_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


class LibraryStore:
    def __init__(self, root: str):
        self.root = root

    def path(self, profile: str) -> str:
        # Only internally generated profile hashes can select a file.
        if len(profile) != 24 or any(c not in "0123456789abcdef" for c in profile):
            raise ValueError("Invalid profile")
        return os.path.join(self.root, profile + ".json")

    def load(self, profile: str) -> dict:
        try:
            with open(self.path(profile), encoding="utf-8") as stream:
                data = json.load(stream)
            if data.get("schema") != 1 or not isinstance(data.get("tracks"), list):
                raise ValueError("Invalid library")
            return data
        except FileNotFoundError:
            return {"schema": 1, "tracks": [], "synced_at": ""}

    def save(self, profile: str, tracks: list[dict]) -> dict:
        data = {"schema": 1, "tracks": tracks,
                "synced_at": datetime.now().astimezone().isoformat(timespec="seconds")}
        atomic_json(self.path(profile), data)
        return data


class ShuffleOrder:
    """One shuffled pass, plus real back/forward history, keyed by track identity."""
    def __init__(self):
        self.remaining = []
        self.history = []
        self.cursor = -1
        self.known = set()

    def reset(self, keys, current=None):
        self.known = set(keys)
        self.remaining = [key for key in keys if key != current]
        random.shuffle(self.remaining)
        self.history = [current] if current is not None else []
        self.cursor = len(self.history) - 1

    def next(self, keys, current, repeat=False):
        if set(keys) != self.known:
            self.reset(keys, current)
        if self.cursor + 1 < len(self.history):
            self.cursor += 1
            return self.history[self.cursor]
        if not self.remaining:
            if not repeat:
                return None
            self.remaining = [key for key in keys if key != current] or list(keys)
            random.shuffle(self.remaining)
        if not self.remaining:
            return None
        key = self.remaining.pop()
        self.history.append(key)
        self.cursor += 1
        return key

    def previous(self):
        if self.cursor > 0:
            self.cursor -= 1
            return self.history[self.cursor]
        return None
