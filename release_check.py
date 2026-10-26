"""Explicit --self-test; isolated data and networking disabled."""
import json
import os
import tempfile
import traceback
import wave
from pathlib import Path
from unittest.mock import patch


def run(report_path):
    report={'passed':False,'checks':[],'errors':[]}
    app=None
    with tempfile.TemporaryDirectory(prefix='muuzika-3-test-') as directory:
        os.environ['MUUZIKA_DATA_DIR']=directory
        os.environ['PYGAME_HIDE_SUPPORT_PROMPT']='1'
        try:
            import muuzika as m
            from ui_validation import run_checks
            sample=Path(directory,'silent.wav')
            with wave.open(str(sample),'wb') as sound:
                sound.setnchannels(2);sound.setsampwidth(2);sound.setframerate(44100)
                sound.writeframes(b'\0'*44100*4*30)
            with patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden')) as network, \
                 patch.object(m,'KEYRING_AVAILABLE',False), \
                 patch.object(m.MuuzikaApp,'setup_system_tray',lambda self:None):
                app=m.MuuzikaApp()
                assert Path(m.SCRIPT_DIR,'fekete.ico').is_file()
                report['checks']=run_checks(app,m,sample)
                app.on_closing();app=None
                app=m.MuuzikaApp();app.update_idletasks()
                assert (app.winfo_width(),app.winfo_height()) == (520,600)
                assert tuple(map(int,app.resizable())) == (0,0)
                assert app.title() == 'Muuzika'
                assert app.preferences['saved_palettes']['My purple']['colors']['COLOR_ACCENT'] == '#123456'
                report['checks'].append('Saved window size restores on restart and remains locked')
                network.assert_not_called()
                report['checks'].append('No server requests or user credentials accessed')
                app.on_closing();app=None
                report['passed']=True
        except Exception:
            report['errors'].append(traceback.format_exc())
        finally:
            if app is not None:
                try:app.on_closing()
                except Exception:pass
    Path(report_path).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1
