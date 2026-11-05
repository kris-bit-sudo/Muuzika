"""Offline integration checks shared by source and frozen Windows builds."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tkinter as tk
import traceback
from unittest.mock import patch


def run_checks(app, m, sample):
    checks, errors = [], []
    app.report_callback_exception = lambda *args: errors.append(''.join(traceback.format_exception(*args)))
    def pump():
        app.update_idletasks();app.update()
        assert not errors, errors
    def no_windows():
        assert not any(isinstance(w,tk.Toplevel) for w in app.winfo_children())
    pump()
    assert app.title() == 'Muuzika'
    assert (app.winfo_width(),app.winfo_height()) == (400,500)
    assert tuple(map(int,app.resizable())) == (0,0)
    app.tracks = [m.Track(path=str(sample),title=title,artist='Test Artist',duration=30)
                  for title in ('First sample','Second sample','Third sample')]
    app.refresh_rows();pump()
    bounds = app.playlist_box.bbox(1)
    with patch.object(app,'play_index') as play:
        app.playlist_box.event_generate('<ButtonPress-1>',x=15,y=bounds[1]+2)
        app.playlist_box.event_generate('<ButtonRelease-1>',x=15,y=bounds[1]+2)
        pump();play.assert_called_once_with(1)
    app.show_list_search();pump()
    app.main_container.event_generate('<Button-1>',x=1,y=1);pump()
    assert app.list_search.winfo_ismapped() and not app.list_search.get()
    assert app.focus_get() != app.list_search._entry
    center=app.brand_label.winfo_rootx()+app.brand_label.winfo_width()/2
    assert abs(center-(app.winfo_rootx()+app.winfo_width()/2)) < 2
    assert app.add_files_button.winfo_rooty() < app.playlist_box.winfo_rooty()
    assert app.sync_button.winfo_rooty() < app.playlist_box.winfo_rooty()
    assert not app.footer.winfo_ismapped()
    app.list_search.insert(0,'Third');app.search_from_header();pump()
    assert app.playlist_box.curselection() == (2,)
    app.hide_list_search(False)
    app.list_search.insert(0,'sample');app.update_search_results();pump()
    assert app.playlist_box.curselection()==(0,) and app.search_count.cget('text')=='1/3'
    app.search_next.invoke();pump()
    assert app.playlist_box.curselection()==(1,) and app.list_search.get()=='sample'
    app.search_previous.invoke();app.search_previous.invoke();pump()
    assert app.playlist_box.curselection()==(2,) and app.search_count.cget('text')=='3/3'
    app.list_search.delete(0,'end');app.list_search.insert(0,'absent');app.update_search_results()
    assert app.search_count.cget('text')=='0/0'
    app.main_container.event_generate('<Button-1>',x=1,y=1);pump()
    assert not app.list_search.get() and app.search_count.cget('text')==''
    checks.append('Search arrows cycle all matches in both directions; outside click ends search')
    checks.append('Default 400 × 500; single click plays; persistent header search finds tracks and clears')
    app.volume_slider.set(0);app.set_volume(0)
    app.play_index(0);pump()
    assert app.playing and app.title() == 'Muuzika'
    app.toggle_play_pause();assert app.paused
    app.toggle_play_pause();assert not app.paused
    checks.append('Real silent audio play/pause; title always Muuzika')
    watched = (app.repeat_button,app.shuffle_button,app.play_pause_btn,app.playlist_box)
    def positions():
        pump()
        return [(w.winfo_x(),w.winfo_y(),w.winfo_width(),w.winfo_height()) for w in watched]
    baseline = positions()
    for _ in range(6):
        app.cycle_repeat();app.toggle_shuffle()
        app.set_status('Downloading audio…')
        assert positions() == baseline
    assert app.status_label.cget('text') == ''
    center = app.play_pause_btn.winfo_rootx()+app.play_pause_btn.winfo_width()/2
    assert abs(center-(app.winfo_rootx()+app.winfo_width()/2)) < 2
    checks.append('Stable symmetric transport and silent routine progress')
    for theme in ('Retro Silver','Retro Pink','Original Green'):
        app.rebuild_ui(theme);pump()
        assert app.playing and app.title() == 'Muuzika'
        assert app.retro_wheel is not None if theme.startswith('Retro') else app.retro_wheel is None
        if app.retro_wheel is not None: assert app.retro_wheel.winfo_ismapped()
        assert app.playlist_box.winfo_height() >= 60
    checks.append('Original and Retro styles switch without interrupting audio')
    app.preferences.update(nc_url='https://example.test/music',nc_user='test')
    remote = m.Track(kind='remote',id='sample',title='Offline sample',source_profile=app.active_profile())
    app.library_store.save(app.active_profile(),[remote.to_dict()])
    app.open_nextcloud_browser();pump();no_windows()
    assert app._view == 'Library' and app.library_box.size() == 1
    assert app.library_search_glyph.winfo_ismapped()
    for shell in (app.library_search_shell,app.search_shell):
        assert shell.cget('height')==34
    for arrow in (app.search_previous,app.search_next,app.library_previous,app.library_next):
        assert arrow.cget('fg_color')=='transparent' and arrow.cget('border_width')==0
    assert not app.playback_panel.winfo_ismapped() and not app.search_shell.winfo_ismapped()
    assert not app.status_host.winfo_ismapped() and app.playing
    original=list(app.tracks)
    new=m.Track(kind='remote',id='new',title='New remote',source_profile=app.active_profile())
    app.add_tracks([remote],announce=False)
    def immediate_thread(target,daemon):return SimpleNamespace(start=target)
    with patch.object(app,'get_client',return_value=SimpleNamespace(all_songs=lambda **kw:[remote,new])), \
         patch.object(m.Track,'from_remote',side_effect=lambda track:track), \
         patch.object(m.threading,'Thread',side_effect=immediate_thread):
        app.library_missing_button.invoke();app._drain_ui();pump()
        assert len(app.tracks)==len(original)+2 and app._view=='Library'
        assert app.library_status.cget('text')=='1 missing tracks added.'
        app.library_missing_button.invoke();app._drain_ui();pump()
        assert len(app.tracks)==len(original)+2
        assert app.library_status.cget('text')=='Your playlist is already up to date.'
    app.tracks=original;app.refresh_rows()
    app.show_view('Player');pump()
    watched_header=(app.add_files_button,app.sync_button,app.search_shell,app.playlist_box)
    def header_positions():
        pump()
        return [(w.winfo_x(),w.winfo_y(),w.winfo_width(),w.winfo_height()) for w in watched_header]
    stable=header_positions()
    for busy in (True,False,True,False):
        app.set_sync_busy(busy)
        app.status_label.configure(text='Server sync · manual refresh')
        assert header_positions()==stable
    # Exercise the actual mouse bindings, async completion and delayed click animation.
    import time
    tasks=[]
    def deferred_thread(target,daemon):return SimpleNamespace(start=lambda:tasks.append(target))
    movements=[]
    for widget in watched_header:
        widget.bind('<Configure>',lambda e:movements.append((e.widget,e.x,e.y,e.width,e.height)),add='+')
    with patch.object(app,'get_client',return_value=SimpleNamespace(all_songs=lambda **kw:[remote,new])), \
         patch.object(m.Track,'from_remote',side_effect=lambda track:track), \
         patch.object(m.threading,'Thread',side_effect=deferred_thread):
        for _ in range(3):
            app.sync_button._canvas.event_generate('<Enter>');pump()
            app.sync_button._canvas.event_generate('<ButtonPress-1>',x=12,y=12);pump()
            assert app._syncing and header_positions()==stable
            app.sync_button._canvas.event_generate('<ButtonRelease-1>',x=12,y=12);pump()
            tasks.pop()();app._drain_ui();pump()
            deadline=time.monotonic()+.15
            while time.monotonic()<deadline:
                pump();time.sleep(.005)
            assert header_positions()==stable
    assert not movements, movements
    checks.append('Actual cloud press/release and delayed completion never move neighboring widgets; both search bars use transparent arrows')
    app.hide_tooltip();app.show_view('Library');pump()
    checks.append('Library hides playback and duplicate search; Add missing syncs once and deduplicates; header geometry stays fixed')
    app.library_search.insert(0,'missing')
    app.library_search.event_generate('<KeyRelease>');pump()
    assert app.library_box.size() == 0
    for section in ('Appearance','Window','Connection','About'):
        app.settings_section(section);pump();no_windows();assert app.playing
        assert not app.playback_panel.winfo_ismapped()
        assert not app.search_shell.winfo_ismapped()
        assert not app.add_files_button.winfo_ismapped()
        assert not app.sync_button.winfo_ismapped()
    app.show_notice('The server is unavailable. This is a test.');pump();no_windows()
    assert app._view == 'Notice'
    checks.append('Library, Settings, About and errors stay inside one window')
    before = copy.deepcopy(app.preferences)
    app.appearance_draft()['custom_colors']['COLOR_MAIN_CONTAINER'] = '#183040'
    app._view='Colors';app.rebuild_ui();pump();no_windows()
    assert app.colors['COLOR_MAIN_CONTAINER'] == '#183040'
    app.save_data()
    saved=json.loads(Path(m.PLAYER_DATA_FILE).read_text(encoding='utf-8'))['preferences']
    assert saved.get('custom_colors') == before.get('custom_colors')
    app.cancel_appearance();pump()
    assert app.colors['COLOR_MAIN_CONTAINER'] != '#183040'
    app.appearance_draft()['custom_colors']['ICON'] = '#ABCDEF'
    app.rebuild_ui();pump();app.save_appearance();pump()
    assert app.preferences['custom_colors']['ICON'] == '#ABCDEF'
    app.restore_green();pump();app.save_appearance();pump()
    assert app.preferences['theme'] == 'Original Green' and app.preferences['custom_colors'] == {}
    checks.append('Color preview never autosaves; Save, Cancel and Original Green reset work')
    start = (app.winfo_width(),app.winfo_height())
    app.begin_resize();pump();assert tuple(map(int,app.resizable())) == (1,1)
    app.geometry('600x680');pump();app.save_data()
    assert app.preferences.get('window_size') is None
    app.cancel_resize();pump()
    assert (app.winfo_width(),app.winfo_height()) == start
    assert tuple(map(int,app.resizable())) == (0,0)
    app.begin_resize();app.geometry('520x600');pump();app.save_window_size();pump()
    assert app.preferences['window_size'] == {'width':520,'height':600}
    assert tuple(map(int,app.resizable())) == (0,0)
    checks.append('Resize unlock, cancel, save and relock preserve explicit size choices')
    app.show_view('Player');pump()
    app.volume_slider.set(.23);app.on_mousewheel(SimpleNamespace(delta=120))
    assert app.volume_slider.get() == .25
    app.volume_slider.set(.23);app.on_mousewheel(SimpleNamespace(delta=-120))
    assert app.volume_slider.get() == .20
    app.volume_slider.set(0);app.set_volume(0)
    checks.append('Volume wheel keeps directional 5-percent snapping')
    from theme_system import FINISHES, saved_size, TEXT_PAIRS, contrast, THEMES
    for name,colors in THEMES.items():
        for foreground,background in TEXT_PAIRS:
            assert contrast(colors[foreground],colors[background])>=4.5,(name,foreground,background)
    checks.append('Every preset passes text contrast checks; Settings hides playback/header actions while audio continues')
    assert saved_size({'window_size':{'width':100,'height':100}}) == (360,440)
    app.geometry('360x440');pump()
    for name in ('Original Green',*FINISHES):
        app.preferences.update(theme=name,layout='Retro',custom_colors={})
        app.rebuild_ui();pump()
        assert app.retro_wheel.winfo_ismapped() and not app.stop_button.winfo_ismapped()
        assert app.playlist_box.winfo_height() >= 55, (name,app.playlist_box.winfo_height())
        assert not app.menu_button.winfo_ismapped()
        for widget in (app.list_search,app.sync_button,app.retro_shuffle,app.retro_repeat,app.volume_slider):
            assert widget.winfo_ismapped()
            assert widget.winfo_rootx() >= app.winfo_rootx()
            assert widget.winfo_rootx()+widget.winfo_width() <= app.winfo_rootx()+app.winfo_width()
            assert widget.winfo_rooty()+widget.winfo_height() <= app.winfo_rooty()+app.winfo_height()
    checks.append('All 17 reference finishes and Original Green fit the 360 × 440 Retro layout; no duplicate Stop')
    app.retro_wheel.clicked(SimpleNamespace(x=72,y=21));pump();assert app.tabs.winfo_ismapped()
    assert app._view == 'Navigation' and not app.playback_panel.winfo_ismapped()
    app.tab_buttons['Settings'].invoke();pump()
    assert app._view == 'Settings' and not app.tabs.winfo_ismapped()
    assert app.back_button.winfo_ismapped()
    app.back_button.invoke();pump();assert app._view == 'Player'
    app.open_settings();pump()
    app.page_menu_button.invoke();pump()
    app.main_container.event_generate('<Button-1>',x=1,y=1);pump()
    assert not app.tabs.winfo_ismapped()
    app.page_menu_button.invoke();pump()
    app.event_generate('<Escape>');pump();assert not app.tabs.winfo_ismapped()
    app.show_view('Player');pump()
    app.volume_slider.set(.35);app.toggle_mute();assert app.volume_slider.get() == 0
    app.toggle_mute();assert app.volume_slider.get() == .35
    app.set_volume(0)
    checks.append('Wheel MENU opens navigation; alternate pages retain navigation; outside click/Escape close it')
    app.show_view('Palettes');pump();no_windows()
    app.choose_palette('Purple');pump()
    assert app.colors['COLOR_MAIN_CONTAINER'] == m.THEMES['Purple']['COLOR_MAIN_CONTAINER']
    app.appearance_draft()['custom_colors']['COLOR_ACCENT']='#123456'
    app.rebuild_ui();pump()
    assert app.save_named_palette('My purple') is None
    assert app.save_named_palette('My purple') is not None
    assert app.save_named_palette('') is not None
    app.cancel_appearance();pump()
    app.choose_palette('My purple',True);pump()
    assert app.colors['COLOR_ACCENT'] == '#123456'
    app.save_appearance();pump()
    stored=json.loads(Path(m.PLAYER_DATA_FILE).read_text(encoding='utf-8'))
    assert stored['preferences']['saved_palettes']['My purple']['colors']['COLOR_ACCENT'] == '#123456'
    checks.append('Visual palette previews, named saving, duplicate-name validation and custom selection persist')
    app.preferences.update(theme='Original Green',layout='Original',custom_colors={})
    app.geometry('520x600');app.rebuild_ui();pump()
    app.save_data();no_windows();pump()
    return checks
