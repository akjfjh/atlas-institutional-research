#!/usr/bin/env python3
"""Portable ATLAS skill launcher. Never evaluates shell command strings."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    marker = root / '.atlas-runtime.json'
    if marker.is_file() and os.environ.get('ATLAS_LAUNCHER_ACTIVE') != '1':
        try:
            runtime = Path(json.loads(marker.read_text())['python'])
        except (OSError, ValueError, KeyError) as exc:
            raise SystemExit(f'Invalid local runtime marker: {exc}')
        if not runtime.is_file():
            raise SystemExit('Installed runtime is missing. Re-run scripts/install.py with a working Python 3.11+.')
        env = dict(os.environ, ATLAS_LAUNCHER_ACTIVE='1')
        os.execve(str(runtime), [str(runtime), '-m', 'atlas.cli', *sys.argv[1:]], env)
    sys.path.insert(0, str(root))
    try:
        from atlas.cli import main as cli_main
    except ModuleNotFoundError as exc:
        raise SystemExit(f'ATLAS runtime dependency missing ({exc.name}). Run python scripts/install.py first.')
    cli_main()


if __name__ == '__main__':
    main()
