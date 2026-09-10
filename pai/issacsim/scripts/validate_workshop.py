#!/usr/bin/env python3
"""Check source syntax, local Markdown links and Workshop Studio conventions."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import struct
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
errors = []
figures = []
pages = list((ROOT / "content").rglob("*.ko.md"))
for path in pages:
    text = path.read_text(encoding="utf-8")
    if not re.match(r'^---\ntitle: "[^"\n]+"\nweight: \d+\n---\n', text):
        errors.append(f"{path.relative_to(ROOT)}: front matter")
    if "chapter:" in text or "{{%" in text:
        errors.append(f"{path.relative_to(ROOT)}: unsupported directive")
    for line in text.splitlines():
        if not line.startswith(":image["):
            continue
        match = re.fullmatch(r':image\[([^\]]+)\]\{src="(/static/images/[^"]+\.png)"(?: width=\d+)?\}', line)
        if not match:
            errors.append(f"{path.relative_to(ROOT)}: invalid image directive")
            continue
        image = (ROOT / match[2].lstrip("/")).resolve()
        if not image.is_relative_to(ROOT / "static" / "images") or not image.is_file():
            errors.append(f"{path.relative_to(ROOT)}: missing image {match[2]}")
            continue
        figures.append(image)
        data = image.read_bytes()
        if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
            errors.append(f"{image.relative_to(ROOT)}: invalid PNG")
        elif min(struct.unpack(">II", data[16:24])) < 300:
            errors.append(f"{image.relative_to(ROOT)}: insufficient illustration resolution")
if len(figures) != 7 or len(set(figures)) != 7:
    errors.append("Expected exactly seven distinct source figures")
execution = ROOT / "static/images/execution"
try:
    provenance = json.loads((execution / "isaac-smoke.provenance.json").read_text(encoding="utf-8"))
    public_fields = {"date", "isaac_sim_version", "instance_type", "gpu", "driver_version", "seed", "png_sha256"}
    if not isinstance(provenance, dict) or set(provenance) != public_fields:
        errors.append("Isaac screenshot provenance must contain only the seven public fields")
    elif provenance["png_sha256"] != hashlib.sha256((execution / "isaac-smoke.png").read_bytes()).hexdigest():
        errors.append("Isaac screenshot differs from its provenance SHA-256")
except (OSError, ValueError) as exc:
    errors.append(f"Isaac screenshot provenance: {exc}")
for path in (ROOT / "static" / "images").rglob("*.svg"):
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
for path in list((ROOT / "content").rglob("*.md")) + list((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        errors.append(f"{path.relative_to(ROOT)}: replacement character")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if re.match(r"^(https?://|mailto:|#)", target):
            continue
        if not (path.parent / target.split("#")[0]).resolve().exists():
            errors.append(f"{path.relative_to(ROOT)}: missing {target}")
for folder in ("static/code", "scripts", "tests"):
    for path in (ROOT / folder).rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(str(exc))
for path in (ROOT / "scripts").rglob("*.sh"):
    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
    if result.returncode:
        errors.append(result.stderr.strip())
for required in ("contentspec.yaml", "static/workshop.yaml", "static/code/workshop_core.py",
                 "static/code/train.py", "static/code/sim/run_sim.py",
                 "static/code/device/ros_policy_node.py", "docs/verification.md"):
    if not (ROOT / required).exists():
        errors.append(f"missing {required}")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"PASS: {len(pages)} Korean pages; {len(figures)} figures, PNG provenance hash, local links/images, SVG XML, Python syntax, shell syntax, required files")
