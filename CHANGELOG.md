# Changelog

## 3.1.0-beta5

- Optional Settings > Audio > Normalize volume, saved locally and applied on track start.
- Offline integrated-loudness/true-peak analysis and constant-gain lossless playback cache.
- Cancellable preparation, cache reuse, peak protection and unchanged originals.
- Bundled FFmpeg and build/license notices; no extra user installation required.
- Reapply the master volume after loading each stream, including normalized copies.

## 3.1.0-beta4

- Shared Player/Library search bar with magnifier and transparent arrow controls.
- Library arrows navigate the filtered results without starting playback.
- Fixed header action slots isolate cloud/add redraws from neighboring widgets.
- Mouse press/release and asynchronous sync completion are covered by UI tests.

## 3.1.0-beta3

- Search match counter, previous/next arrows, Enter and Shift+Enter navigation.
- Stable header icon dimensions and a bounded tooltip area during sync.
- Library uses one search field and hides playback controls while audio continues.
- Add missing explicitly syncs and adds only missing server tracks to the playlist.
- Removed obsolete publishing/license-status material from source packages.
- README and Windows packaging now include the repository's GPLv3 license.

## 3.1.0-beta2

- Default size 400 × 500; saved custom size still respected.
- Persistent compact header search; no separate search icon.
- Retro MENU moves to the wheel; cloud icon distinguishes server sync.
- More readable controls, timestamps, volume and contextual hints.
- Visual palette gallery with named personal palette snapshots.
- Added repository templates, Windows CI, release preparation and launch guide.

## 3.1.0-beta.1

- Minimum size 360 × 440; compact icon navigation.
- Matching Retro controls, improved contrast and no duplicate Stop.
- Added 17 reference-inspired color finishes without device branding.

## 3.0.0-beta.1

- Single-window English UI, independent Original/Retro styles and color editing.
- Explicit resizing mode with save/cancel, fixed Muuzika window title.

### Pre-release review
- Integrated navigation screen instead of an overlay toolbar.
- Distraction-free Settings and palette editing; audio continues in background.
- Removed all decorative color strips and audited built-in text contrast.
- Logo provenance recorded from the maintainer's confirmation.
