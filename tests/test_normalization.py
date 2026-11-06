"""Real offline decoding/rendering checks using generated tones, never music."""
from pathlib import Path
from array import array
import hashlib
import json
import math
import os
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from normalization import Normalizer, Cancelled, find_ffmpeg, gain_for

def tone(path, amplitude, seconds=2):
    samples=array('h')
    for i in range(round(48000*seconds)):
        value=int(32767*amplitude*math.sin(2*math.pi*440*i/48000))
        samples.extend((value,value))
    with wave.open(str(path),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(48000)
        wav.writeframes(samples.tobytes())

class NormalizationTests(unittest.TestCase):
    def test_peak_protection_and_silence(self):
        self.assertEqual(gain_for(-30,-1),-1)
        self.assertEqual(gain_for(float('-inf'),float('-inf')),0)
        self.assertEqual(gain_for(-80,-60),20)

    @unittest.skipUnless(find_ffmpeg(),'FFmpeg required for audio integration checks')
    def test_loud_quiet_equalization_cache_and_source_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);engine=Normalizer(root/'cache')
            outputs=[]
            for name,amplitude in (('quiet',.02),('loud',.6)):
                source=root/(name+'.wav');tone(source,amplitude)
                before=hashlib.sha256(source.read_bytes()).digest()
                output=engine.prepare(source)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),before)
                report=engine._run(['-i',output,'-af','loudnorm=I=-18:TP=-2:LRA=11:print_format=json','-f','null','-'],lambda:False)
                data=json.loads(report[report.rfind('{'):report.rfind('}')+1])
                outputs.append(float(data['input_i']))
                self.assertLessEqual(float(data['input_tp']),-1.8)
                with patch.object(engine,'_run',side_effect=AssertionError('Cache must avoid decoding')):
                    os.utime(source,None)
                    self.assertEqual(engine.prepare(source),output)
                if name=='quiet':
                    Path(output).with_suffix('.json').write_text('{"gain_db": 0}')
                    self.assertEqual(engine.prepare(source),output)
                    self.assertIn('silent',json.loads(Path(output).with_suffix('.json').read_text()))
            self.assertLess(abs(outputs[0]-outputs[1]),.3)
            self.assertTrue(all(abs(value+18)<.3 for value in outputs),outputs)
            # Changed bytes invalidate the cache, unlike mere access-time updates.
            source=root/'quiet.wav';tone(source,.1)
            engine.prepare(source)
            self.assertEqual(len(list((root/'cache').glob('*.json'))),3)

    @unittest.skipUnless(find_ffmpeg(),'FFmpeg required')
    def test_cancel_and_invalid_audio_leave_no_playable_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'tone.wav';tone(source,.1)
            engine=Normalizer(root/'cache')
            with self.assertRaises(Cancelled):engine.prepare(source,lambda:True)
            source.write_bytes(b'not audio')
            with self.assertRaises(RuntimeError):engine.prepare(source)
            self.assertFalse(list((root/'cache').glob('*.flac')))

    def test_pruning_keeps_current_audio_and_measurements(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);engine=Normalizer(root,max_bytes=15)
            old=root/'old.flac';new=root/'new.flac'
            old.write_bytes(b'0'*10);new.write_bytes(b'1'*10)
            (root/'old.json').write_text('{}')
            engine._prune(new)
            self.assertFalse(old.exists());self.assertTrue(new.exists())
            self.assertTrue((root/'old.json').exists())

    @unittest.skipUnless(find_ffmpeg(),'FFmpeg required')
    def test_cancel_running_analysis_and_silent_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'silence.wav';tone(source,0)
            engine=Normalizer(root/'cache')
            calls=[0]
            def cancelled():
                calls[0]+=1
                return calls[0]>=4
            with self.assertRaises(Cancelled):engine.prepare(source,cancelled)
            self.assertFalse(list((root/'cache').glob('*.flac')))
            self.assertEqual(engine.prepare(source),str(source))
            with patch.object(engine,'_run',side_effect=AssertionError('Silence analysis should be cached')):
                self.assertEqual(engine.prepare(source),str(source))

if __name__=='__main__':unittest.main()
