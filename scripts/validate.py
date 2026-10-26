#!/usr/bin/env python3
"""Validate skill metadata/source and optionally build a private-data-free ZIP."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ALLOWED_TOP = {'name','description','license','compatibility','metadata','allowed-tools'}
EXCLUDE_PARTS = {'.venv','venv','__pycache__','.git','.pytest_cache','build','dist','node_modules','local-data','reports'}
EXCLUDE_FILES = {'.atlas-runtime.json','user-requirements.md','engineering-contract.md'}
ROOT_FILES = {'SKILL.md','LICENSE','README.md','README_EN.md','CHANGELOG.md','pyproject.toml','.gitignore','MANIFEST.in','requirements.lock'}
ROOT_DIRS = {'atlas','agents','references','scripts','schemas','docs'}


def publication_files(root: Path):
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in EXCLUDE_PARTS or part.endswith('.egg-info') for part in rel.parts):
            continue
        if not path.is_file() or path.name in EXCLUDE_FILES or path.suffix in {'.pyc','.db','.sqlite','.pem','.key'} or path.suffix.startswith('.sqlite') or path.name.startswith('.env') or path.name.endswith(('-wal','-shm')):
            continue
        if rel.parts[0] not in ROOT_DIRS and str(rel) not in ROOT_FILES:
            continue
        allowed={'.py','.md','.json','.toml','.yaml','.yml'}
        if rel.parts[:3]==('atlas','web','static'):allowed.update({'.html','.css','.js'})
        if rel.parts[:2]==('docs','examples'):allowed.add('.png')
        if rel.parts[:2]==('docs','images'):allowed.update({'.jpg','.jpeg','.png','.webp'})
        if len(rel.parts)>1 and path.suffix not in allowed:
            continue
        # Only the source identity ledger/notices are necessary in release packages.
        if len(rel.parts) > 2 and rel.parts[:2] == ('docs','upstream') and path.name not in {'source-lock.json','NOTICE.md'}:
            continue
        yield path


def validate(root: Path) -> dict:
    errors: list[str] = []
    skill = root / 'SKILL.md'
    if not skill.is_file():
        return {'ok':False,'errors':['Missing SKILL.md']}
    text = skill.read_text()
    match = re.match(r'^---\n(.*?)\n---\n',text,re.S)
    if not match:
        return {'ok':False,'errors':['Missing YAML frontmatter delimiters']}
    try:
        import yaml
        front = yaml.safe_load(match.group(1))
    except ImportError:
        return {'ok':False,'errors':['PyYAML is required for the development validator: pip install PyYAML']}
    except Exception as exc:
        return {'ok':False,'errors':[f'Invalid YAML: {exc}']}
    if not isinstance(front,dict):
        return {'ok':False,'errors':['Frontmatter must be a map']}
    if set(front) - ALLOWED_TOP:
        errors.append('Unknown metadata fields: '+str(sorted(set(front)-ALLOWED_TOP)))
    name = front.get('name','')
    if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64 or root.name!=name:
        errors.append('Skill name must match directory and naming rules')
    if not isinstance(front.get('description'),str) or not 0<len(front['description'])<=1024:
        errors.append('Description must contain 1–1024 characters')
    if 'compatibility' in front and (not isinstance(front['compatibility'],str) or len(front['compatibility'])>500):
        errors.append('Compatibility must be a string <=500 characters')
    if not isinstance(front.get('metadata',{}),dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in front.get('metadata',{}).items()):
        errors.append('Metadata keys/values must be strings')
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if '://' not in target and not (root/target.split('#')[0]).exists():
            errors.append('Missing SKILL reference: '+target)
    files = list(publication_files(root))
    for path in files:
        rel = str(path.relative_to(root))
        if path.is_symlink():
            errors.append('Symlink in publication: '+rel)
        if path.suffix == '.py':
            try:
                tree=ast.parse(path.read_text(),filename=rel)
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call):
                        if isinstance(node.func,ast.Name) and node.func.id in {'eval','exec'}:
                            errors.append(f'Dynamic code evaluation: {rel}:{node.lineno}')
                        for kw in node.keywords:
                            if kw.arg=='shell' and isinstance(kw.value,ast.Constant) and kw.value.value is True:
                                errors.append(f'Shell execution: {rel}:{node.lineno}')
            except (SyntaxError,UnicodeDecodeError) as exc:
                errors.append(f'Syntax/read error: {rel}: {exc}')
        if path.suffix in {'.py','.json','.toml','.yaml','.yml','.md'}:
            content=path.read_text()
            for pattern in (r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'\bsk-[A-Za-z0-9_-]{24,}\b',
                            r'(?i)(?:api_key|secret_key|passphrase)\s*=\s*[\"\x27][A-Za-z0-9+/_=-]{20,}[\"\x27]'):
                if re.search(pattern,content):
                    errors.append('Potential literal secret requires manual review: '+rel)
    return {'ok':not errors,'errors':errors,'files_checked':len(files),'scope':'metadata, links, Python syntax, high-confidence accidental-secret patterns, no dynamic eval/shell=True; not a comprehensive security audit'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('path',nargs='?',type=Path,default=Path(__file__).resolve().parent.parent)
    p.add_argument('--package',type=Path)
    a=p.parse_args();root=a.path.resolve();result=validate(root)
    if result['ok'] and a.package:
        a.package.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(a.package,'w',compression=zipfile.ZIP_DEFLATED) as out:
            for path in publication_files(root):
                out.write(path,root.name+'/'+str(path.relative_to(root)))
        result['package']=str(a.package.resolve())
        result['sha256']=hashlib.sha256(a.package.read_bytes()).hexdigest()
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['ok'] else 1)


if __name__=='__main__': main()
