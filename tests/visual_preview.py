"""Isolated visual preview: synthetic titles, no user data, no network."""
import os
import sys
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests' / '.visual-preview'
DATA.mkdir(exist_ok=True)
os.environ['MUUZIKA_DATA_DIR'] = str(DATA)
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
theme = sys.argv[sys.argv.index('--theme')+1] if '--theme' in sys.argv else 'Original Green'
preferences = {'theme':theme,'layout':'Retro' if '--retro' in sys.argv else 'Original'}
if '--compact' in sys.argv: preferences['window_size']={'width':360,'height':440}
(DATA / 'player_data.json').write_text(json.dumps({'playlist': [], 'preferences': preferences}), encoding='utf-8')
sys.path.insert(0, str(ROOT))
import muuzika as m

with patch('requests.sessions.Session.request', side_effect=AssertionError('Network disabled in preview')), \
     patch.object(m, 'KEYRING_AVAILABLE', False), \
     patch.object(m.MuuzikaApp, 'setup_system_tray', lambda self: None):
    app = m.MuuzikaApp()
    if '--empty' not in sys.argv:
        app.tracks = [m.Track(path=str(DATA / f'demo-{i}.mp3'), title=title,
                              artist='Muuzika Demo', duration=180+i*17)
                      for i, title in enumerate(['Green Room', 'After Hours', 'Pocket Radio',
                                                'Soft Focus', 'Night Drive', 'One More Track'])]
        app.current_index = 0
        app.show_track_info(app.tracks[0])
        app.refresh_rows()
    app.title('Muuzika · Vizuális próba')
    if '--gallery' in sys.argv: app.show_view('Palettes')
    def audit():
        names = ['playlist_box', 'play_pause_btn', 'prev_button', 'next_button', 'sync_button', 'volume_slider', 'search_shell', 'search_glyph', 'list_search', 'search_count', 'search_previous']
        result = {'window': [app.winfo_width(), app.winfo_height()], 'widgets': {}}
        for name in names:
            widget = getattr(app, name)
            result['widgets'][name] = {'width': widget.winfo_width(), 'height': widget.winfo_height(),
                                      'x': widget.winfo_rootx()-app.winfo_rootx(),
                                      'y': widget.winfo_rooty()-app.winfo_rooty()}
            label = getattr(widget, '_image_label', None)
            if label is not None:
                result['widgets'][name]['image_visible'] = bool(label.winfo_ismapped())
        (DATA / 'layout.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    app.after(1000, audit)
    app.mainloop()
