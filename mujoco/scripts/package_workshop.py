#!/usr/bin/env python3
"""Package only workshop sources; never upstream robot assets or runtime results."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'README.md','NOTICE.md','.gitignore','contentspec.yaml','index.html','requirements-docs.txt','requirements-validation.txt'}
DIRS={'content','docs','scripts','static','tests'}
EXCLUDE={'__pycache__','node_modules','.venv','.venv-docs','artifacts','local','_site','_gitbook'}
FORBIDDEN={'.stl','.obj','.urdf','.mjcf','.usd','.usda','.usdc','.onnx','.pt','.pth','.npz','.pkl','.pickle'}


def source_files():
    result=[]
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if any(x in EXCLUDE or x.startswith('.venv') for x in rel.parts): continue
        if rel.parts[0] not in DIRS and rel.as_posix() not in ROOT_FILES: continue
        if p.is_symlink(): raise ValueError(f'Symlinks not permitted in distribution: {rel}')
        if not p.is_file(): continue
        if p.suffix.lower() in FORBIDDEN or p.name.endswith('.onnx.data'):
            raise ValueError(f'Robot assets/weights must not be distributed: {rel}')
        if p.suffix=='.pyc': continue
        result.append(p)
    return result


def write_stage_inventory(directory, payloads):
    manifest = {"schema_version": 1, "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())}}
    for name, data in payloads.items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"Unsafe staging path: {name}")
        dest = directory / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    (directory / "BUILD-INVENTORY.json").write_text(json.dumps(manifest, indent=2) + "\n")
    validate_stage(directory)


def validate_stage(directory):
    if directory.is_symlink():
        raise ValueError(f"Staging root is a symlink: {directory}")
    inventory = json.loads((directory / "BUILD-INVENTORY.json").read_text())["files"]
    actual = {}
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Staging contains a symlink: {path}")
        if path.is_file() and path != directory / "BUILD-INVENTORY.json":
            rel = path.relative_to(directory).as_posix()
            if path.suffix.lower() in FORBIDDEN or path.name.endswith(".onnx.data"):
                raise ValueError(f"Restricted file in staging: {rel}")
            actual[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != inventory:
        raise ValueError(f"Staging inventory/hash mismatch: {directory}")
    return len(actual)


def main():
    files=source_files()
    target=ROOT.parent/(ROOT.name+'.zip')
    if not (ROOT/'index.html').is_file(): raise ValueError('Build index.html first')
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in files:
            name=(Path(ROOT.name)/p.relative_to(ROOT)).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,9,9,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            archive.writestr(info,p.read_bytes())
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        for p in files:
            assert archive.read((Path(ROOT.name)/p.relative_to(ROOT)).as_posix())==p.read_bytes()
    print(json.dumps({'file':str(target),'files':len(files),'bytes':target.stat().st_size,'sha256':digest}))

if __name__=='__main__': main()
