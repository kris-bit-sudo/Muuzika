# Reproducible onedir Windows build; run in the isolated .build-env.
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('customtkinter')
datas += [('fekete.ico', '.'), ('VERSION', '.')]
a = Analysis(
    ['Inditas.pyw'], pathex=[], binaries=[], datas=datas,
    hiddenimports=['keyring.backends.Windows'], hookspath=[],
    hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Muuzika',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, icon='fekete.ico')
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Muuzika-Windows')
