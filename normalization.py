"""Offline track loudness normalization; originals are never rewritten.

FFmpeg measures integrated EBU R128 loudness and true peak. A single constant
gain is rendered to lossless FLAC, preserving the track's internal dynamics.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

TARGET_LUFS = -18.0
PEAK_DB = -2.0
CACHE_VERSION = 'r128-static-v1'


class Cancelled(Exception):
    pass


def find_ffmpeg():
    bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'tools' / 'ffmpeg.exe'
    return str(bundled) if bundled.is_file() else shutil.which('ffmpeg')


def gain_for(loudness, peak):
    if not math.isfinite(loudness) or not math.isfinite(peak):
        return 0.0  # Silence has no meaningful integrated loudness.
    return min(TARGET_LUFS-loudness, PEAK_DB-peak, 20.0)


class Normalizer:
    def __init__(self, directory, executable=None, max_bytes=512*1024*1024):
        self.directory=Path(directory)
        self.executable=executable or find_ffmpeg()
        self.max_bytes=max_bytes
        self.lock=threading.Lock()

    def _run(self, args, cancelled):
        if cancelled(): raise Cancelled()
        if not self.executable: raise RuntimeError('FFmpeg is unavailable')
        command=[self.executable,'-hide_banner','-nostdin','-y',*args]
        with subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) as process:
            deadline=time.monotonic()+300
            while True:
                if cancelled() or time.monotonic()>deadline:
                    process.kill();process.communicate()
                    if cancelled(): raise Cancelled()
                    raise RuntimeError('Loudness analysis timed out')
                try:
                    _,error=process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode: raise RuntimeError('Audio could not be analyzed')
            return error.decode('utf-8',errors='replace')

    def prepare(self, source, cancelled=lambda:False):
        source=Path(source).resolve(strict=True)
        if not source.is_file(): raise ValueError('Audio must be a local file')
        digest=hashlib.sha256(CACHE_VERSION.encode())
        with source.open('rb') as stream:
            while chunk:=stream.read(1024*1024):
                if cancelled(): raise Cancelled()
                digest.update(chunk)
        key=digest.hexdigest()
        while not self.lock.acquire(timeout=.1):
            if cancelled(): raise Cancelled()
        try:
            if cancelled(): raise Cancelled()
            self.directory.mkdir(parents=True,exist_ok=True)
            output=self.directory/(key+'.flac')
            record=self.directory/(key+'.json')
            data=None
            try:
                data=json.loads(record.read_text(encoding='utf-8'))
                if (not isinstance(data,dict) or not isinstance(data.get('silent'),bool)
                        or not isinstance(data['gain_db'],(int,float))
                        or not math.isfinite(data['gain_db'])): data=None
            except (OSError,ValueError,TypeError,KeyError): data=None
            if data and data.get('silent'): return str(source)
            if data and output.is_file() and output.stat().st_size>0:
                os.utime(output,None)
                return str(output)
            inputs=['-protocol_whitelist','file,pipe','-i',str(source),'-map','0:a:0','-vn','-sn','-dn']
            if data is None:
                report=self._run([*inputs,'-af','aformat=channel_layouts=stereo,aresample=48000,loudnorm=I=-18:TP=-2:LRA=11:print_format=json','-f','null','-'],cancelled)
                measured=json.loads(report[report.rfind('{'):report.rfind('}')+1])
                loudness=float(measured['input_i']);peak=float(measured['input_tp'])
                silent=not math.isfinite(loudness) or not math.isfinite(peak)
                data={'gain_db':gain_for(loudness,peak),'silent':silent,
                      'input_lufs':loudness if math.isfinite(loudness) else None,
                      'input_peak_db':peak if math.isfinite(peak) else None}
            temporary=self.directory/(key+'.'+uuid.uuid4().hex+'.tmp.flac')
            meta=record.with_suffix('.tmp.json')
            try:
                if not data['silent']:
                    self._run([*inputs,'-af',f"aformat=channel_layouts=stereo,aresample=48000,volume={data['gain_db']:.8f}dB",'-ar','48000',
                        '-ac','2','-c:a','flac','-sample_fmt','s32','-map_metadata','-1',str(temporary)],cancelled)
                    if not temporary.is_file() or temporary.stat().st_size==0: raise RuntimeError('Empty normalized audio')
                if cancelled(): raise Cancelled()
                if temporary.exists(): temporary.replace(output)
                meta.write_text(json.dumps(data,allow_nan=False),encoding='utf-8');meta.replace(record)
            finally:
                temporary.unlink(missing_ok=True);meta.unlink(missing_ok=True)
            self._prune(output)
            return str(source if data['silent'] else output)
        finally:
            self.lock.release()

    def _prune(self, protected):
        files=sorted(self.directory.glob('*.flac'),key=lambda p:p.stat().st_mtime)
        total=sum(p.stat().st_size for p in files)
        for path in files:
            if total<=self.max_bytes: break
            if path==protected: continue
            try:
                size=path.stat().st_size;path.unlink();total-=size
            except OSError: pass  # A playing file can be locked by Windows.
