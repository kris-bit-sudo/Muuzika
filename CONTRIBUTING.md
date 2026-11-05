# Contributing

Please open an issue before a large change. Use synthetic audio and metadata;
do not connect automated tests to a personal server.

Windows / Python 3.12 setup:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-release.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe tests/ui_smoke.py
```

Use `MUUZIKA_DATA_DIR` for isolated manual tests. Keep preferences outside the
source tree. Preserve English UI labels, explicit server sync, keyboard access
and saved appearance behavior. Include reproduction steps for fixes.

See LICENSE for the project's GNU GPL version 3 license.
