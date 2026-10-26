"""Create a reviewable source ZIP from an explicit allowlist; never publish."""
from pathlib import Path
import zipfile
from beta_core import VERSION

ROOT=Path(__file__).resolve().parent
NAMES=['muuzika.py','beta_core.py','nextcloud_music.py','studio_ui.py','palette_ui.py',
       'theme_system.py','retro_ui.py','ui_icons.py','Inditas.pyw','release_check.py',
       'ui_validation.py','build_release.py','prepare_source.py','Muuzika.spec',
       'requirements.txt','requirements-release.txt','VERSION','README.md',
       'README-WINDOWS.txt','CONTRIBUTING.md','SECURITY.md','LICENSE-STATUS.md',
       'CHANGELOG.md','.gitignore','fekete.ico','zold.ico','tests/test_beta.py',
       'tests/ui_smoke.py','tests/visual_preview.py','docs/PUBLISHING-HU.md',
       'docs/RELEASE-NOTES.md','.github/workflows/windows.yml',
       '.github/ISSUE_TEMPLATE/bug_report.md','.github/ISSUE_TEMPLATE/feature_request.md',
       '.github/pull_request_template.md']
if (ROOT/'LICENSE').is_file(): NAMES.append('LICENSE')
target=ROOT/'releases'/f'Muuzika-{VERSION}-Source.zip'
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as out:
    for name in NAMES:
        path=ROOT/name
        if not path.is_file(): raise FileNotFoundError(name)
        out.write(path,'Muuzika/'+name)
with zipfile.ZipFile(target) as check:
    assert check.testzip() is None
print(f'Source package: {target} ({len(NAMES)} files)')
