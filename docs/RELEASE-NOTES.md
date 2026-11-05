# Muuzika 3.1.0-beta3

- Search keeps its query, shows the current match and supports previous/next arrows.
- Enter moves forward; Shift+Enter moves back; clicking outside ends search.
- Stable cloud/add buttons during sync.
- Library hides playback controls and duplicate header search while music continues.
- Add missing refreshes the server library and adds only tracks absent from the playlist.
- Source documentation cleanup and GPLv3 license included in Windows packages.

## Previous beta2 highlights

A compact Windows music player with Original Green, Retro controls and
customizable palettes. Vibe-coded by kris.

## New in this beta
- 400 × 500 default window; previously saved sizes remain intact.
- Compact header search and MENU on the Retro wheel.
- A distinct cloud icon for manual server sync.
- Improved typography for controls, timestamps, volume and hints.
- Visual palette previews and named personal color snapshots.

## Download
Download the **Windows-x64.zip**, extract the entire archive and run
**Muuzika-Windows/Muuzika.exe**. Python is not required. Keep `_internal`
beside the executable. Close the old version before launching the new one.

Library sync is manual; uncached remote audio downloads when played.
This unsigned beta was tested on Windows using isolated synthetic data,
including the extracted executable. No live Nextcloud server or clean Windows
VM was tested. Report issues with version, reproduction steps and redacted
screenshots; never attach credentials or player_data.json.
