"""Run with .build-env/Scripts/python.exe to build the Windows ZIP."""
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from beta_core import VERSION
from normalization import find_ffmpeg

ROOT = Path(__file__).resolve().parent
dist_root = ROOT / 'dist' / VERSION
subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(dist_root), 'Muuzika.spec'], cwd=ROOT, check=True)
package = dist_root / 'Muuzika-Windows'
for name in ('README-WINDOWS.txt', 'VERSION', 'LICENSE'):
    shutil.copy2(ROOT / name, package / name)
license_dir = package / 'licenses'
license_dir.mkdir(exist_ok=True)
notices = []
ffmpeg=Path(find_ffmpeg()).resolve()
ffmpeg_license=license_dir/'FFmpeg'
ffmpeg_license.mkdir(exist_ok=True)
for name in ('LICENSE','README.txt'):
    source=ffmpeg.parent.parent/name
    if source.is_file(): shutil.copy2(source,ffmpeg_license/name)
if not (ffmpeg_license/'LICENSE').exists():
    shutil.copy2(ROOT/'LICENSE',ffmpeg_license/'LICENSE')
configuration=subprocess.run([str(ffmpeg),'-version'],capture_output=True,text=True,check=True).stdout
(ffmpeg_license/'BUILD.txt').write_text(configuration+'\nFFmpeg: https://ffmpeg.org/\nWindows build/source information: https://www.gyan.dev/ffmpeg/builds/\n',encoding='utf-8')
notices.append('FFmpeg (GPLv3 build; license and original build/source details in licenses/FFmpeg)')
for distribution in metadata.distributions():
    name = distribution.metadata['Name']
    if name.lower() in ('pip', 'pyinstaller', 'pyinstaller-hooks-contrib', 'altgraph', 'pefile'):
        continue
    notices.append(f'{name} {distribution.version}')
    for file in distribution.files or []:
        if any(word in file.name.lower() for word in ('license', 'copying', 'notice')) and file.suffix.lower() not in ('.py', '.pyc'):
            source = Path(distribution.locate_file(file))
            if source.is_file():
                target = license_dir / name / str(file).replace('/', '__').replace('\\', '__')
                target.parent.mkdir(exist_ok=True)
                shutil.copy2(source, target)
python_license = Path(sys.base_prefix, 'LICENSE.txt')
if python_license.is_file():
    shutil.copy2(python_license, license_dir / 'Python-LICENSE.txt')
for directory in Path(sys.base_prefix, 'tcl').glob('*'):
    license_file = directory / 'license.terms'
    if license_file.is_file():
        shutil.copy2(license_file, license_dir / (directory.name + '-license.terms'))
(package / 'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(sorted(notices)) + '\n\nLicense texts: licenses/\n', encoding='utf-8')
release = ROOT / 'releases'
release.mkdir(exist_ok=True)
archive = release / f'Muuzika-{VERSION}-Windows-x64.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
    for path in sorted(package.rglob('*')):
        if path.is_file():
            zipped.write(path, path.relative_to(package.parent))
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': digest}))
