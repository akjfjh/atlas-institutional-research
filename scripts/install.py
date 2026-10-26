#!/usr/bin/env python3
"""Idempotent user-space installation; research records are never copied/deleted."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

NAME = 'atlas-institutional-research'
FILES = ('SKILL.md', 'LICENSE', 'README.md', 'README_EN.md', 'CHANGELOG.md', 'pyproject.toml', 'requirements.lock')
DIRS = ('atlas', 'agents', 'references', 'schemas', 'scripts')


def runtime_dir() -> Path:
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'ATLAS' / 'runtime'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'ATLAS' / 'runtime'
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share'))) / 'atlas' / 'runtime'


def copy_skill(source: Path, target: Path) -> list[str]:
    """Copy a publication allowlist atomically, without following symlinks."""
    if target.expanduser().is_symlink():
        raise ValueError('Install destination must not be a symlink.')
    source, target = source.resolve(), target.expanduser().resolve()
    if source == target:
        raise ValueError('Install destination must differ from the source directory.')
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='atlas-install-', dir=target.parent))
    copied: list[str] = []
    try:
        for name in FILES:
            src = source / name
            if not src.is_file() or src.is_symlink():
                raise ValueError(f'Required source file is missing or symbolic: {name}')
            shutil.copy2(src, staged / name)
            copied.append(name)
        for name in DIRS:
            src = source / name
            for file in sorted(src.rglob('*')):
                if not file.is_file() or '__pycache__' in file.parts:
                    continue
                if file.is_symlink():
                    raise ValueError(f'Symlinks are not packaged: {file.relative_to(source)}')
                allowed = {'.py'} if name in ('atlas', 'scripts') else ({'.md', '.json'} if name == 'references' else ({'.json'} if name == 'schemas' else {'.yaml', '.yml'}))
                if name=='atlas' and file.relative_to(src).parts[:2]==('web','static'):
                    allowed={'.html','.css','.js','.svg'}
                if file.suffix not in allowed or file.name.startswith('.'):
                    continue
                rel = file.relative_to(source)
                dest = staged / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, dest)
                copied.append(str(rel))
        # Public instructions referenced by SKILL.md. Developer/user inputs stay outside installation.
        public_docs = ('installation.md', 'usage.md', 'visual-dashboard.md', 'architecture.md', 'compatibility.md', 'publishing.md',
                       'data-provenance.md', 'validation-report.md', 'validation-report-v0.2.md', 'validation-report-v0.2.en.md', 'validation-report-v0.3.md', 'validation-report-v0.3.en.md', 'validation-report-v0.4.md', 'validation-report-v0.5.md', 'validation-report-v0.6.md', 'acceptance-matrix.md', 'source-review.md',
                       'provider-verification.md')
        for name in public_docs:
            src = source / 'docs' / name
            if src.is_file():
                dest = staged / 'docs' / name
                dest.parent.mkdir(exist_ok=True)
                shutil.copy2(src, dest)
                copied.append('docs/' + name)
        for name in ('source-lock.json', 'NOTICE.md'):
            src = source / 'docs' / 'upstream' / name
            if src.is_file():
                dest = staged / 'docs' / 'upstream' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied.append('docs/upstream/' + name)
        examples=source/'docs'/'examples'
        if examples.is_dir():
            for file in examples.iterdir():
                if file.is_file() and not file.is_symlink() and file.suffix in {'.png','.json'}:
                    dest=staged/'docs'/'examples'/file.name
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(file,dest)
                    copied.append('docs/examples/'+file.name)
        images=source/'docs'/'images'
        if images.is_dir():
            for file in images.iterdir():
                if file.is_file() and not file.is_symlink() and file.suffix in {'.jpg','.jpeg','.png','.webp','.svg'}:
                    dest=staged/'docs'/'images'/file.name
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(file,dest)
                    copied.append('docs/images/'+file.name)
        old_marker = target / '.atlas-runtime.json'
        marker = old_marker.read_text() if old_marker.is_file() else None
        if target.exists():
            # Only replace a previous installation carrying this exact skill identity.
            identity = (target / 'SKILL.md').read_text() if (target / 'SKILL.md').is_file() else ''
            if f'name: {NAME}' not in identity:
                raise ValueError('Refusing to replace a directory that is not an ATLAS skill installation.')
            backup = target.with_name(target.name + '.install-backup')
            if backup.exists():
                raise ValueError(f'Previous installation backup requires review: {backup}')
            target.rename(backup)
            try:
                staged.rename(target)
            except Exception:
                backup.rename(target)
                raise
            shutil.rmtree(backup)
        else:
            staged.rename(target)
        if marker is not None:
            (target / '.atlas-runtime.json').write_text(marker)
        return copied
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-dir', type=Path, default=Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills' / NAME)
    parser.add_argument('--venv', type=Path, default=runtime_dir())
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--skill-only', action='store_true', help='Copy the skill without changing a Python environment')
    parser.add_argument('--with-mcp', action='store_true', help='Install the optional MCP SDK in the dedicated runtime')
    parser.add_argument('--runtime-python', type=Path, help='Existing prepared runtime Python; skips creating/installing a venv')
    args = parser.parse_args()
    if args.with_mcp and (args.skill_only or args.runtime_python):
        parser.error('--with-mcp requires installation into the dedicated --venv runtime')
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ is required')
    source = Path(__file__).resolve().parent.parent
    if args.runtime_python:
        # Preserve the venv executable path: resolving its symlink selects the
        # base interpreter and loses the dedicated ATLAS site-packages.
        python = args.runtime_python.expanduser().absolute()
        if not python.is_file():
            parser.error('--runtime-python is not a file')
    elif not args.skill_only:
        envdir = args.venv.expanduser().resolve()
        python = envdir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if not python.is_file():
            subprocess.run([args.python, '-m', 'venv', str(envdir)], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', 'pip==26.2.2'], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(source/'requirements.lock')], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', str(source)], check=True)
        if args.with_mcp:
            subprocess.run([str(python), '-m', 'pip', 'install', 'mcp==1.30.0'], check=True)
    else:
        python = None
    # An already installed Skill can bootstrap its missing runtime in place.
    same_dir=source==args.skill_dir.expanduser().resolve()
    if same_dir and f'name: {NAME}' not in (source/'SKILL.md').read_text():
        raise ValueError('Installed source identity is not ATLAS')
    copied = [] if same_dir else copy_skill(source, args.skill_dir)
    if python:
        marker = args.skill_dir.expanduser() / '.atlas-runtime.json'
        marker.write_text(json.dumps({'python': str(python), 'installer_version': '0.6.0'}, indent=2) + '\n')
        if os.name != 'nt':
            marker.chmod(0o600)
    print(json.dumps({'skill_dir': str(args.skill_dir.expanduser()), 'runtime_python': str(python) if python else None,
                      'copied_files': len(copied), 'research_data': 'untouched'}, indent=2))


if __name__ == '__main__':
    main()
