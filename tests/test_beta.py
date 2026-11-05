import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_ROOT = tempfile.TemporaryDirectory(prefix="muuzika-tests-")
os.environ["MUUZIKA_DATA_DIR"] = TEST_ROOT.name
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from beta_core import LibraryStore, ShuffleOrder, cache_filename, profile_id, friendly_error, search_text
from nextcloud_music import SubsonicClient, RemoteTrack, SubsonicError
from muuzika import MuuzikaApp, Track


class CoreTests(unittest.TestCase):
    def test_profiles_isolate_accounts_and_normalize_rest(self):
        self.assertEqual(profile_id("https://EXAMPLE.test/music/", "a"),
                         profile_id("https://example.test/music/rest", "a"))
        self.assertNotEqual(profile_id("https://example.test/music", "a"),
                            profile_id("https://example.test/music", "b"))

    def test_cache_filename_stays_inside_directory(self):
        name = cache_filename("../../other", "../../file")
        self.assertNotIn("/", name)
        self.assertNotIn("\\", name)
        self.assertTrue(name.endswith(".audio"))

    def test_local_library_round_trip_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as root:
            store = LibraryStore(root)
            profile = profile_id("https://example.test", "a")
            self.assertEqual(store.load(profile)["tracks"], [])
            store.save(profile, [{"title": "Árvíz", "id": "1"}])
            with patch("beta_core.os.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    store.save(profile, [])
            self.assertEqual(store.load(profile)["tracks"][0]["title"], "Árvíz")
            self.assertEqual(len(list(Path(root).glob("*.tmp"))), 0)

    def test_shuffle_plays_once_then_stops(self):
        order = ShuffleOrder()
        keys = list(range(30))
        order.reset(keys, 0)
        visited = [0]
        for _ in range(29):
            visited.append(order.next(keys, visited[-1]))
        self.assertEqual(set(visited), set(keys))
        self.assertEqual(len(visited), len(set(visited)))
        self.assertIsNone(order.next(keys, visited[-1]))

    def test_shuffle_previous_and_forward_use_real_history(self):
        order = ShuffleOrder()
        order.reset([1, 2, 3], 1)
        second = order.next([1, 2, 3], 1)
        self.assertEqual(order.previous(), 1)
        self.assertEqual(order.next([1, 2, 3], 1), second)

    def test_shuffle_repeat_all_starts_new_cycle(self):
        order = ShuffleOrder()
        order.reset([1, 2], 1)
        self.assertEqual(order.next([1, 2], 1), 2)
        self.assertEqual(order.next([1, 2], 2, repeat=True), 1)

    def test_errors_do_not_disclose_password_urls(self):
        import requests
        secret = "https://test/?p=enc:SECRET"
        for error in [requests.ConnectionError(secret), requests.HTTPError(secret), ValueError(secret),
                      SubsonicError(40, secret)]:
            self.assertNotIn("SECRET", friendly_error(error))

    def test_hungarian_search_ignores_accents(self):
        self.assertEqual(search_text("ÁRVÍZTŰRŐ TÜKÖRFÚRÓGÉP"), "arvizturo tukorfurogep")

    def test_remote_track_preserves_profile(self):
        a = Track(kind="remote", id="1", source_profile=profile_id("https://a.test", "a"))
        b = Track(kind="remote", id="1", source_profile=profile_id("https://b.test", "a"))
        self.assertNotEqual(a.key, b.key)
        self.assertEqual(Track.from_dict(a.to_dict()).key, a.key)


class ClientTests(unittest.TestCase):
    def client(self):
        return SubsonicClient("https://example.test/music", username="test", password="test")

    def test_library_over_ten_thousand_and_server_page_cap(self):
        client = self.client()
        def page(method, **params):
            offset = params["songOffset"]
            return {"searchResult3": {"song": [{"id": str(i), "title": str(i)}
                for i in range(offset, min(offset + 100, 10123))]}}
        client._get = Mock(side_effect=page)
        self.assertEqual(len(client.all_songs()), 10123)

    def test_repeated_server_page_fails_instead_of_replacing_library(self):
        client = self.client()
        client._get = Mock(return_value={"searchResult3": {"song": [{"id": "1"}]}})
        with self.assertRaises(SubsonicError):
            client.all_songs()

    def test_download_rejects_server_error_body(self):
        client = self.client()
        response = Mock()
        response.headers = {"Content-Type": "application/json"}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        client.session.get = Mock(return_value=response)
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(SubsonicError):
                client.download_to_cache(RemoteTrack("1", "Song"), root)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_cached_audio_never_contacts_server(self):
        client = self.client()
        client.session.get = Mock(side_effect=AssertionError("network"))
        track = RemoteTrack("1", "Song")
        with tempfile.TemporaryDirectory() as root:
            target = Path(root, track.cache_name())
            target.write_bytes(b"cached audio")
            self.assertEqual(client.download_to_cache(track, root), str(target))
        client.session.get.assert_not_called()

    def test_cache_cleanup_protects_playing_and_incomplete_files(self):
        with tempfile.TemporaryDirectory() as root:
            playing = Path(root, "playing.mp3")
            old = Path(root, "old.mp3")
            partial = Path(root, "active.part")
            for path in (playing, old, partial):
                path.write_bytes(b"12345")
            SubsonicClient.prune_cache(root, 5, protected=(str(playing),))
            self.assertTrue(playing.exists())
            self.assertTrue(partial.exists())
            self.assertFalse(old.exists())


class PlaybackTests(unittest.TestCase):
    def test_wheel_snaps_to_directional_five_percent_boundaries(self):
        for initial, delta, expected in [(0.23, 120, 0.25), (0.23, -120, 0.20),
                                          (0.25, 120, 0.30), (0.25, -120, 0.20),
                                          (0.98, 120, 1.0), (0.02, -120, 0.0),
                                          (1.0, 120, 1.0), (0.0, -120, 0.0),
                                          (0.23, 240, 0.30), (0.23, -240, 0.15),
                                          (0.23, 10, 0.25)]:
            with self.subTest(initial=initial, delta=delta):
                from types import SimpleNamespace
                app = Mock()
                app.volume_slider.get.return_value = initial
                MuuzikaApp.on_mousewheel(app, SimpleNamespace(delta=delta))
                app.volume_slider.set.assert_called_once_with(expected)
                app.set_volume.assert_called_once_with(expected)

    def test_wheel_zero_delta_does_not_change_volume(self):
        from types import SimpleNamespace
        app = Mock()
        MuuzikaApp.on_mousewheel(app, SimpleNamespace(delta=0))
        app.volume_slider.set.assert_not_called()

    def test_automatic_scrobble_and_prefetch_are_disabled(self):
        app = Mock()
        MuuzikaApp.prefetch_next(app)
        MuuzikaApp._scrobble(app, "1")
        app.get_client.assert_not_called()

    def test_playback_error_keeps_track(self):
        track = Track(path="missing.mp3", title="Missing")
        app = Mock(tracks=[track], _failed_tracks=set())
        MuuzikaApp.handle_playback_error(app, 0, OSError())
        self.assertEqual(app.tracks, [track])
        self.assertIn(track.key, app._failed_tracks)

    def test_stale_download_cannot_start(self):
        app = Mock(_play_token=2)
        MuuzikaApp._remote_ready(app, 1, "old.mp3", 0)
        app._start_file.assert_not_called()

    def test_remote_ready_starts_once_without_prefetch(self):
        app = Mock(_play_token=2, preferences={})
        with patch("muuzika.SubsonicClient.prune_cache"):
            MuuzikaApp._remote_ready(app, 2, "cache/song.mp3", 0)
        app._start_file.assert_called_once_with("cache/song.mp3", 2, 0)
        app.prefetch_next.assert_not_called()


class ManualSyncTests(unittest.TestCase):
    def test_browsing_and_searching_are_strictly_local(self):
        with tempfile.TemporaryDirectory() as root, ExitStack() as stack:
            profile = profile_id('https://example.test', 'a')
            store = LibraryStore(root)
            store.save(profile, [Track(kind='remote', id='1', title='Árvíz',
                                      source_profile=profile).to_dict()])
            from theme_system import THEMES, DEFAULT_THEME
            from studio_ui import StudioUI
            app = Mock(browser_win=None, library_store=store, colors=THEMES[DEFAULT_THEME])
            app.track_from_dict = Track.from_dict
            app.format_time = lambda value: str(value)
            app.active_profile.return_value = profile
            app.cache_path.return_value = str(Path(root, 'not-downloaded.mp3'))
            app.get_client.side_effect = AssertionError('Browser must not get a client')
            request = stack.enter_context(patch('requests.sessions.Session.request',
                                              side_effect=AssertionError('Network forbidden')))
            controls = {}
            for name in ('CTkToplevel', 'CTkLabel', 'CTkFrame', 'CTkEntry', 'CTkScrollbar', 'CTkButton', 'CTkFont'):
                controls[name] = stack.enter_context(patch('muuzika.ctk.' + name))
            box = stack.enter_context(patch('muuzika.tk.Listbox')).return_value
            variable = stack.enter_context(patch('studio_ui.tk.StringVar')).return_value
            entry = app.ui_entry.return_value
            app.search_field.return_value=(Mock(),entry,Mock(),Mock(),Mock(),Mock())
            entry.get.return_value = ''
            StudioUI.build_library(app, Mock())
            self.assertEqual(box.insert.call_count, 1)
            search_callback = variable.trace_add.call_args.args[1]
            entry.get.return_value = 'arviz'
            search_callback()
            self.assertEqual(box.insert.call_count, 2)
            entry.get.return_value = 'nincs ilyen dal'
            search_callback()
            self.assertEqual(box.insert.call_count, 2)
            request.assert_not_called()
            app.get_client.assert_not_called()

    def test_explicit_sync_and_failed_sync_preserve_snapshot(self):
        class ImmediateThread:
            def __init__(self, target, **kwargs):
                self.target = target
            def start(self):
                self.target()
        with tempfile.TemporaryDirectory() as root:
            profile = profile_id('https://example.test', 'a')
            store = LibraryStore(root)
            app = Mock(_syncing=False, library_store=store, _reload_library=None)
            app.active_profile.return_value = profile
            app.ui_call.side_effect = lambda callback: callback()
            client = app.get_client.return_value
            client.all_songs.return_value = [RemoteTrack('1', 'Synced song')]
            with patch('muuzika.threading.Thread', ImmediateThread):
                MuuzikaApp.sync_library(app)
                client.all_songs.assert_called_once()
                saved = store.load(profile)
                self.assertEqual(saved['tracks'][0]['source_profile'], profile)
                self.assertFalse(app._syncing)
                client.all_songs.side_effect = OSError('offline')
                MuuzikaApp.sync_library(app)
                self.assertEqual(store.load(profile), saved)
                self.assertFalse(app._syncing)

    def test_invalid_duration_is_safe(self):
        track = Track.from_dict({'kind': 'remote', 'id': '1', 'duration': 'NaN', 'title': None})
        self.assertEqual(track.duration, 0)
        self.assertEqual(track.title, '')

    def test_transport_icons_are_transparent_images(self):
        from ui_icons import transport_icon
        for name in ('play', 'pause', 'stop', 'previous', 'next', 'repeat', 'repeat_one', 'shuffle'):
            icon = transport_icon(name, '#5fd685')
            self.assertEqual(icon.size, (22, 22))
            self.assertEqual(icon.mode, 'RGBA')
            self.assertIsNotNone(icon.getbbox())


if __name__ == "__main__":
    unittest.main()
