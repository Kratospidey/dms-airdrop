#!/usr/bin/env python3
"""Build and verify the KDE adapter using already-installed libraries."""
from pathlib import Path
from picker_build import build_picker

if __name__ == "__main__":
    try: build_picker(Path(__file__).resolve().parents[1])
    except ValueError as error: raise SystemExit(str(error))
