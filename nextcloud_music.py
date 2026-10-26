"""
nextcloud_music.py — Subsonic (OpenSubsonic) kliens a Nextcloud Music apphoz.

Használat:

    from nextcloud_music import SubsonicClient

    cli = SubsonicClient(
        "https://cloud.example.com/index.php/apps/music/subsonic",
        username="your-username",
        password="<Music app -> Beallitasok -> Ampache/Subsonic -> Generalt jelszo>",
        verify_tls=True,
    )
    cli.ping()
    for t in cli.all_songs():
        print(t.display_name(), t.duration)

FONTOS: a Nextcloud Music NEM a Nextcloud jelszavadat varja, hanem a Music app
beallitasainal generalt kulon API jelszot, es NEM tamogatja a token/salt (t+s)
auth-ot, ezert plain 'p=' (illetve 'p=enc:<hex>') megy ki.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.parse
import threading
from beta_core import cache_filename
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

import requests

API_VERSION = "1.16.1"
DEFAULT_CLIENT_NAME = "Muuzika"


class SubsonicError(RuntimeError):
    """A szerver ertelmes hibavalaszt adott (subsonic-response status=failed)."""

    def __init__(self, code: int, message: str):
        super().__init__(f"Subsonic error {code}: {message}")
        self.code = code
        self.message = message


@dataclass
class RemoteTrack:
    id: str
    title: str
    artist: str = ""
    album: str = ""
    duration: int = 0            # masodperc
    suffix: str = "mp3"          # fajlkiterjesztes a szerveren
    cover_art: Optional[str] = None
    size: int = 0

    @classmethod
    def from_json(cls, d: dict) -> "RemoteTrack":
        return cls(
            id=str(d.get("id", "")),
            title=d.get("title") or d.get("name") or "(untitled)",
            artist=d.get("artist", "") or "",
            album=d.get("album", "") or "",
            duration=int(d.get("duration") or 0),
            suffix=(d.get("suffix") or "mp3").lower(),
            cover_art=d.get("coverArt"),
            size=int(d.get("size") or 0),
        )

    def display_name(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

    def cache_name(self) -> str:
        """Utkozesmentes fajlnev a lokalis cache-hez."""
        return cache_filename(self.id, self.suffix)


class SubsonicClient:
    def __init__(
        self,
        base_url: str,
        username: str = "",
        password: str = "",
        api_key: str = "",
        verify_tls: bool = True,
        timeout: float = 15.0,
        client_name: str = DEFAULT_CLIENT_NAME,
    ):
        self.rest_url = self._normalize(base_url)
        self.username = username
        self.password = password
        self.api_key = api_key
        self.verify_tls = verify_tls
        self.timeout = timeout
        self.client_name = client_name
        self._download_lock = threading.Lock()

        self.session = requests.Session()
        self.session.verify = verify_tls
        if not verify_tls:
            # Self-signed cert eseten a figyelmeztetes-arviz elnyomasa.
            try:
                import urllib3

                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

    # ---------- alapok ----------

    @staticmethod
    def _normalize(base_url: str) -> str:
        """Elfogadja a .../apps/music/subsonic es a .../subsonic/rest formatumot is."""
        url = base_url.strip().rstrip("/")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("https", "http") or not parts.hostname or parts.query or parts.fragment or parts.username:
            raise ValueError("Invalid server URL")
        if url.endswith("/rest"):
            return url
        return url + "/rest"

    def _auth_params(self) -> dict:
        p = {"v": API_VERSION, "c": self.client_name, "f": "json"}
        if self.api_key:
            # OpenSubsonic apiKeyAuthentication (ujabb Music verziok)
            p["apiKey"] = self.api_key
        else:
            p["u"] = self.username
            # A Music app nem tamogat token/salt auth-ot -> hex-kodolt jelszo megy.
            p["p"] = "enc:" + self.password.encode("utf-8").hex()
        return p

    def _url(self, method: str, **params) -> str:
        q = self._auth_params()
        q.update({k: v for k, v in params.items() if v is not None})
        return f"{self.rest_url}/{method}.view?" + urllib.parse.urlencode(q)

    def _get(self, method: str, **params) -> dict:
        """JSON API hivas; visszaadja a 'subsonic-response' tartalmat."""
        q = self._auth_params()
        q.update({k: v for k, v in params.items() if v is not None})
        r = self.session.get(
            f"{self.rest_url}/{method}.view", params=q, timeout=self.timeout
        )
        r.raise_for_status()
        body = r.json().get("subsonic-response", {})
        if body.get("status") == "failed":
            err = body.get("error", {})
            raise SubsonicError(int(err.get("code", 0)), err.get("message", "unknown"))
        if body.get("status") != "ok":
            raise SubsonicError(0, "Incomplete server response")
        return body

    # ---------- lekerdezesek ----------

    def ping(self) -> dict:
        """Kapcsolat + auth teszt. Hiba eseten SubsonicError / requests kivetel."""
        return self._get("ping")

    def all_songs(self, batch: int = 500, limit: int | None = None, progress=None) -> list[RemoteTrack]:
        """A teljes konyvtar. A Music app ures query-vel visszaadja az osszes szamot."""
        out: list[RemoteTrack] = []
        offset = 0
        seen = set()
        while limit is None or offset < limit:
            count = batch if limit is None else min(batch, limit - offset)
            body = self._get(
                "search3", query="", songCount=count, songOffset=offset,
                artistCount=0, albumCount=0,
            )
            songs = body.get("searchResult3", {}).get("song", [])
            if not songs:
                break
            parsed = [RemoteTrack.from_json(s) for s in songs]
            fresh = [s for s in parsed if s.id and s.id not in seen]
            if not fresh:
                raise SubsonicError(0, "The server repeated a page; the previous library is preserved.")
            for song in fresh:
                if song.id not in seen:
                    out.append(song)
                    seen.add(song.id)
            offset += len(songs)
            if progress:
                progress(len(out))
        return out

    def search(self, query: str, count: int = 100) -> list[RemoteTrack]:
        body = self._get("search3", query=query, songCount=count, artistCount=0, albumCount=0)
        return [RemoteTrack.from_json(s) for s in body.get("searchResult3", {}).get("song", [])]

    def playlists(self) -> list[dict]:
        body = self._get("getPlaylists")
        return body.get("playlists", {}).get("playlist", [])

    def playlist_tracks(self, playlist_id: str) -> list[RemoteTrack]:
        body = self._get("getPlaylist", id=playlist_id)
        return [RemoteTrack.from_json(s) for s in body.get("playlist", {}).get("entry", [])]

    def albums(self, kind: str = "alphabeticalByArtist", size: int = 500, offset: int = 0) -> list[dict]:
        body = self._get("getAlbumList2", type=kind, size=size, offset=offset)
        return body.get("albumList2", {}).get("album", [])

    def album_tracks(self, album_id: str) -> list[RemoteTrack]:
        body = self._get("getAlbum", id=album_id)
        return [RemoteTrack.from_json(s) for s in body.get("album", {}).get("song", [])]

    def scrobble(self, track_id: str, submission: bool = True) -> None:
        """Lejatszas jelzese a szervernek (Last.fm / play count)."""
        try:
            self._get("scrobble", id=track_id, submission=str(submission).lower())
        except Exception:
            pass  # a scrobble sosem torhet meg lejatszast

    # ---------- media ----------

    def stream_url(self, track_id: str, max_bitrate: int = 0, fmt: Optional[str] = None) -> str:
        """Kozvetlen URL (pl. VLC-nek). fmt='mp3' eseten a szerver atkodol."""
        return self._url(
            "stream", id=track_id,
            maxBitRate=max_bitrate or None,
            format=fmt,
        )

    def cover_url(self, cover_art_id: str, size: int = 300) -> str:
        return self._url("getCoverArt", id=cover_art_id, size=size)

    def cover_bytes(self, cover_art_id: str, size: int = 300) -> bytes:
        q = self._auth_params()
        q.update({"id": cover_art_id, "size": size})
        r = self.session.get(f"{self.rest_url}/getCoverArt.view", params=q, timeout=self.timeout)
        r.raise_for_status()
        return r.content

    def download_to_cache(
        self,
        track: RemoteTrack,
        cache_dir: str,
        progress: Optional[Callable[[int, int], None]] = None,
        transcode_to_mp3: bool = False,
    ) -> str:
        """
        Letolti a szamot a cache-be es visszaadja a lokalis utvonalat.
        Ha mar ott van, azonnal visszater. Igy a pygame.mixer valtozatlanul mukodik.
        """
        with self._download_lock:
            return self._download_locked(track, cache_dir, progress, transcode_to_mp3)

    def _download_locked(self, track, cache_dir, progress, transcode_to_mp3):
        os.makedirs(cache_dir, exist_ok=True)
        name = track.cache_name()
        if transcode_to_mp3 and not name.endswith(".mp3"):
            name = os.path.splitext(name)[0] + ".mp3"
        target = os.path.join(cache_dir, name)
        if os.path.exists(target) and os.path.getsize(target) > 0:
            os.utime(target, None)
            return target

        q = self._auth_params()
        q.update({"id": track.id})
        if transcode_to_mp3:
            q["format"] = "mp3"

        tmp_fd, tmp_path = tempfile.mkstemp(dir=cache_dir, suffix=".part")
        os.close(tmp_fd)
        try:
            with self.session.get(
                f"{self.rest_url}/stream.view", params=q, stream=True, timeout=self.timeout
            ) as r:
                r.raise_for_status()
                content_type = r.headers.get("Content-Type", "").lower()
                if any(kind in content_type for kind in ("json", "xml", "html")):
                    raise SubsonicError(0, "The server returned an error instead of audio.")
                total = int(r.headers.get("Content-Length") or track.size or 0)
                done = 0
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
                if done == 0:
                    raise SubsonicError(0, "Empty audio file")
            os.replace(tmp_path, target)
            return target
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    # ---------- cache karbantartas ----------

    @staticmethod
    def prune_cache(cache_dir: str, max_bytes: int = 2 * 1024 ** 3, protected=()) -> None:
        """Legregebben hasznalt fajlok torlese, amig a cache a limit ala nem megy."""
        if not os.path.isdir(cache_dir):
            return
        files = []
        total = 0
        for n in os.listdir(cache_dir):
            p = os.path.join(cache_dir, n)
            if os.path.isfile(p) and not n.endswith((".part", ".tmp")):
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if p not in protected:
                    files.append((st.st_mtime, st.st_size, p))
                total += st.st_size
        files.sort()
        for _, size, p in files:
            if total <= max_bytes:
                break
            try:
                os.remove(p)
                total -= size
            except OSError:
                pass


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Hasznalat: python nextcloud_music.py <base_url> <user> <api_password>")
        raise SystemExit(1)
    c = SubsonicClient(sys.argv[1], sys.argv[2], sys.argv[3], verify_tls=False)
    info = c.ping()
    print("OK:", info.get("type"), info.get("serverVersion") or info.get("version"))
    songs = c.all_songs(batch=100, limit=100)
    print(f"{len(songs)} szam:")
    for t in songs[:20]:
        print(" -", t.display_name())
