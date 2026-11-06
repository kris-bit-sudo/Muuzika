# Muuzika 3.1.0-beta5

Vibe-coded by kris.

A compact Windows music player with local audio and a manually synchronized
Nextcloud Music library. Player, Library, Settings, color editing and errors
share one window; playback remains available across views.

## Run

Extract the complete Windows ZIP and run `Muuzika-Windows/Muuzika.exe`.
Keep its `_internal` folder beside it. Python is not required.
See `README-WINDOWS.txt` for usage and release limitations.

For source development, use Python 3.12 on Windows, install
`requirements-release.txt`, then run `Inditas.pyw` or `muuzika.py`.

## Personalization

- Palette and Original/Retro layout are independent choices.
- Original Green remains the default. Customize colors provides grouped HEX
  and RGB editing for theme roles, including controls, text, fields and wheel.
- Changes are previews until Save. Cancel restores saved preferences. Reset
  a color group or restore the Original Green palette at any time.
- Settings > Window > Adjust window size temporarily unlocks resizing.
  Save size commits; Cancel restores. The window otherwise stays locked.
- The title stays Muuzika; all interface labels are English.

## Controls and privacy

Click a playlist row to play. Ctrl/Shift selects multiple rows; drag reorders.
Click outside playlist search or press Escape to dismiss it. Volume wheel
snaps to 5-percent boundaries. Retro supplies a matching click wheel.

Preferences and cached library live in `%APPDATA%/Muuzika GPT-BETA`.
Source and standalone share this location: run only one copy at a time.
`MUUZIKA_DATA_DIR` selects an isolated test directory.

Server sync is explicit. Browsing and search use local library data. An uncached
remote track downloads on playback; cached audio needs no server request.
Test connection is explicit. Automatic sync, prefetch and listening reports
are disabled. Credentials use Windows keyring when available.
No personal data, tracks or server configuration is included in the ZIP.

## Build and verify

Settings > Audio > Normalize volume enables optional per-track loudness
normalization. It applies when the next track starts (or the current one is
restarted). First playback analyzes the entire locally available file, then
caches a lossless FLAC copy with constant gain. Originals are never edited.
The target is -18 LUFS with a -2 dB true-peak ceiling and at most 20 dB gain;
peak-limited tracks can remain quieter. Silence is left unchanged. Prepared
audio uses a roughly 512 MB cache, retaining the currently prepared file.
Analysis never initiates downloads; uncached server tracks are downloaded only
as part of their normal playback request. Stop or another track cancels preparation.
If preparation fails, a message offers retry or disabling normalization; the
unadjusted track does not unexpectedly start at a higher volume.

The Windows package includes FFmpeg with license/build details under
`licenses/FFmpeg`. For source use and builds, install FFmpeg on PATH first.

Use a clean environment containing `requirements-release.txt` and PyInstaller,
then run `python build_release.py`. It creates a versioned ZIP with runtime
libraries, dependency notices and a SHA-256 checksum.

Run `python -m unittest discover -s tests -v` and `python tests/ui_smoke.py`.
The executable accepts `--self-test <report.json>` for isolated UI checks,
including silent audio, theme preview, persistence and window locking.
Networking is blocked and credentials disabled during these checks.

The unsigned beta is tested on Windows x64, but not in a clean Windows VM or
against a live Nextcloud server.



## Beta2 highlights

The default window is 400 x 500. Retro MENU lives on the wheel, header search
is always available, and manual server sync has its own cloud icon. Typography
is larger. Settings > Style > Choose a color palette shows previews; Save as
stores the current colors as a reusable named preset, immediately and locally.

## Beta3 improvements

Search keeps your query and shows a match counter with previous/next arrows.
Enter moves forward; Shift+Enter moves back. Click outside to end the search.
Library has one search field and hides playback controls while music continues.
Add missing explicitly refreshes the server library and adds only tracks not
already in the playlist. Ordinary Server sync only refreshes the library.

## Development and license

See [release notes](docs/RELEASE-NOTES.md), [contributing](CONTRIBUTING.md)
and [LICENSE](LICENSE) (GNU GPL version 3). The logo is maintainer-provided.
`python prepare_source.py` creates a source ZIP without user data.
Windows CI checks, tests and builds; it does not publish releases.

