"""Installer/publication boundary checks using isolated toy source trees."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def source_tree(tmp_path):
    source=tmp_path/'source';source.mkdir()
    installer=load_script('install')
    for file in installer.FILES:
        (source/file).write_text('release file\n')
    (source/'SKILL.md').write_text('---\nname: atlas-institutional-research\ndescription: Research\n---\n')
    for folder in installer.DIRS:
        (source/folder).mkdir()
    (source/'atlas'/'__init__.py').write_text('VERSION="test"\n')
    return source


def test_install_is_idempotent_and_never_copies_private_state(tmp_path):
    source=source_tree(tmp_path);dest=tmp_path/'installed'/'atlas-institutional-research'
    (source/'.env').write_text('private configuration')
    (source/'.venv').mkdir();(source/'.venv'/'token').write_text('local data')
    (source/'atlas.db').write_text('research archive')
    (source/'atlas'/'.env').write_text('nested private config')
    (source/'atlas'/'private.sqlite3').write_text('nested archive')
    installer=load_script('install')
    first=installer.copy_skill(source,dest)
    (dest/'.atlas-runtime.json').write_text('{"python":"/prepared/runtime"}')
    (source/'atlas'/'__init__.py').write_text('VERSION="updated"\n')
    second=installer.copy_skill(source,dest)
    assert first==second
    assert 'updated' in (dest/'atlas'/'__init__.py').read_text()
    assert (dest/'.atlas-runtime.json').read_text()=='{"python":"/prepared/runtime"}'
    assert not (dest/'.env').exists() and not (dest/'.venv').exists() and not (dest/'atlas.db').exists()
    assert not (dest/'atlas'/'.env').exists() and not (dest/'atlas'/'private.sqlite3').exists()
    assert (source/'atlas.db').read_text()=='research archive'


def test_installer_refuses_unrelated_destination_and_symlink(tmp_path):
    source=source_tree(tmp_path);dest=tmp_path/'occupied';dest.mkdir()
    (dest/'important.txt').write_text('preserve')
    with pytest.raises(ValueError,match='not an ATLAS'):
        load_script('install').copy_skill(source,dest)
    assert (dest/'important.txt').read_text()=='preserve'
    if hasattr(Path,'symlink_to'):
        try:
            (source/'atlas'/'linked.py').symlink_to(source/'README.md')
        except OSError:
            pytest.skip('Symlinks unavailable for this account')
        with pytest.raises(ValueError,match='Symlinks'):
            load_script('install').copy_skill(source,tmp_path/'safe-target')


def test_release_inventory_excludes_private_and_developer_files(tmp_path):
    source=source_tree(tmp_path)
    for name in ['.env','atlas.db','.atlas-runtime.json']:
        (source/name).write_text('private')
    (source/'docs').mkdir();(source/'docs'/'user-requirements.md').write_text('user input')
    (source/'docs'/'installation.md').write_text('public instructions')
    (source/'docs'/'examples').mkdir();(source/'docs'/'examples'/'figure.png').write_bytes(b'public figure')
    (source/'docs'/'examples'/'private.db').write_bytes(b'private archive')
    (source/'atlas'/'__pycache__').mkdir();(source/'atlas'/'__pycache__'/'x.pyc').write_bytes(b'cache')
    items={str(p.relative_to(source)) for p in load_script('validate').publication_files(source)}
    assert 'SKILL.md' in items and 'atlas/__init__.py' in items and 'docs/installation.md' in items and 'docs/examples/figure.png' in items
    assert not items.intersection({'.env','atlas.db','.atlas-runtime.json','docs/user-requirements.md','docs/examples/private.db','atlas/__pycache__/x.pyc'})


def test_validator_blocks_dynamic_execution_in_release(tmp_path):
    root=tmp_path/'atlas-institutional-research';root.mkdir()
    (root/'SKILL.md').write_text('---\nname: atlas-institutional-research\ndescription: Research\n---\n')
    (root/'atlas').mkdir();(root/'atlas'/'unsafe.py').write_text('def action(s):\n    return eval(s)\n')
    result=load_script('validate').validate(root)
    assert not result['ok']
    assert any('Dynamic code evaluation' in error for error in result['errors'])
