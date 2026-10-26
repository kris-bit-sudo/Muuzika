"""Double-click launcher; errors are shown instead of silently disappearing."""
import traceback
import sys
from pathlib import Path

if '--self-test' in sys.argv:
    from release_check import run
    position = sys.argv.index('--self-test')
    if position + 1 >= len(sys.argv):
        raise SystemExit('A self-test report path is required')
    raise SystemExit(run(sys.argv[position + 1]))

try:
    from muuzika import MuuzikaApp, APP_VERSION
    MuuzikaApp().mainloop()
except Exception:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Muuzika – startup error",
                        "Muuzika could not start.\n\n" + traceback.format_exc())
    root.destroy()
