"""Isolated integration checks for the source and packaged application."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from release_check import run
raise SystemExit(run(ROOT/'tests'/'ui-smoke-result.json'))
