#!/usr/bin/env python3
"""Build and verify a GitHub Pages artifact using only the standard library.

Run ``python3 scripts/build_pages.py`` from any directory. This rebuilds the
handbook, validates the workshop, and writes _site/ plus the sibling source ZIP.
It does not publish, run git, or delete an existing output directory.

AUTHORED_FILES is intentionally explicit: new source files must be reviewed and
added here. GitHub workflow YAML is also included in the downloadable source.
Unknown files and runtime outputs are never discovered by extension alone.
"""

import base64
import hashlib
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "_site"
ARCHIVE_NAME = "physical-ai-isaac-aws.zip"
ARCHIVE = ROOT.parent / ARCHIVE_NAME
DOWNLOAD = PurePosixPath("downloads") / ARCHIVE_NAME
DOWNLOAD_URL = "https://comeddy.github.io/pai/issacsim/" + DOWNLOAD.as_posix()
PREFIX = "physical-ai-isaac-aws/"
MANIFEST = PurePosixPath(".pages-build-manifest.json")
GENERATOR = "physical-ai-workshop-pages-v1"
IMAGE = re.compile(
    r'^:image\[([^\]]+)\]\{src="(/static/images/[^"]+\.png)"(?: width=\d+)?\}$',
    re.M,
)
AUTHORED_FILES = tuple(PurePosixPath(name) for name in """
README.md
contentspec.yaml
index.html
.gitignore
content/index.ko.md
content/introduction/index.ko.md
content/module1-preflight/index.ko.md
content/module2-aws/index.ko.md
content/module3-simulation/index.ko.md
content/module4-data/index.ko.md
content/module5-training/index.ko.md
content/module6-evaluation/index.ko.md
content/module7-device/index.ko.md
content/module8-real-run/index.ko.md
content/module9-cleanup/index.ko.md
content/troubleshooting/index.ko.md
docs/aws-evidence.md
docs/device-setup.md
docs/facilitator.md
docs/hardware-options.md
docs/illustrations.md
docs/implementation-contract.md
docs/robot-evidence.md
docs/sources.md
docs/verification.md
scripts/build_gitbook.py
scripts/build_handbook.py
scripts/build_pages.py
scripts/cloud/README.md
scripts/cloud/bootstrap-host.sh
scripts/cloud/cleanup-resources.py
scripts/cloud/cleanup.sh
scripts/cloud/deploy.sh
scripts/cloud/preflight.py
scripts/cloud/run-headless.sh
scripts/cloud/serve-preview.sh
scripts/cloud/verify-local.py
scripts/generate_aws_architecture.py
scripts/generate_existing_network.py
scripts/generate_learning_visuals.py
scripts/validate_workshop.py
scripts/verify-local.sh
scripts/visuals/.gitignore
scripts/visuals/README.md
scripts/visuals/build.mjs
scripts/visuals/export_layout.py
scripts/visuals/layout.json
scripts/visuals/package.json
scripts/visuals/package-lock.json
scripts/visuals/scene.mjs
scripts/visuals/verify.mjs
scripts/visuals/viewer.mjs
static/code/device/apply_bringup_watchdog.py
static/code/device/ros_policy_node.py
static/code/device/workshop_cmd_vel_watchdog.hpp
static/code/inspect_dataset.py
static/code/render_trace.py
static/code/requirements.txt
static/code/sim/README.md
static/code/sim/run_sim.py
static/code/sim/scene_math.py
static/code/sim/test_sim_helpers.py
static/code/train.py
static/code/workshop_core.py
static/images/architecture/aws-deployment.drawio
static/images/architecture/aws-deployment.png
static/images/architecture/aws-deployment.svg
static/images/architecture/aws-deployment.validation.json
static/images/concepts/README.md
static/images/concepts/deployment-stages.png
static/images/concepts/deployment-stages.svg
static/images/concepts/lidar-sectors.png
static/images/concepts/lidar-sectors.svg
static/images/concepts/physical-ai-loop.png
static/images/concepts/physical-ai-loop.svg
static/images/concepts/sim-arena.png
static/images/concepts/sim-arena.svg
static/images/concepts/sim-arena-3d.png
static/images/concepts/sim-arena-3d.svg
static/images/concepts/sim-to-real.png
static/images/concepts/sim-to-real.svg
static/images/execution/isaac-smoke.png
static/images/execution/isaac-smoke.provenance.json
static/visuals/arena-3d.html
static/visuals/THIRD_PARTY_LICENSES.txt
static/workshop.yaml
static/workshop-existing-network.json
tests/test_bringup_watchdog.py
tests/test_policy.py
""".split())
EXCLUDED_PARTS = {
    "gitbook", "_site", ".git", "artifacts", "__pycache__", ".venv",
    "node_modules", ".DS_Store",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or "\0" in value:
        raise ValueError(f"Unsafe relative path: {value!r}")
    if path.as_posix() != value or path == PurePosixPath("."):
        raise ValueError(f"Non-canonical relative path: {value!r}")
    return path


def excluded(path):
    return any(
        part in EXCLUDED_PARTS or part == ".env" or part.startswith(".env.")
        or part.lower().endswith((".pem", ".pyc", ".zip"))
        for part in path.parts
    )


def no_symlinks(base, relative):
    """Check every component, including symlinked parent directories."""
    path = base
    if path.is_symlink():
        return False
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            return False
    return True


def collect_sources(root):
    paths = set(AUTHORED_FILES)
    workflows = root / ".github" / "workflows"
    if no_symlinks(root, PurePosixPath(".github/workflows")) and workflows.is_dir():
        for path in workflows.iterdir():
            if path.suffix.lower() in {".yml", ".yaml"}:
                paths.add(PurePosixPath(path.relative_to(root).as_posix()))
    sources = {}
    for relative in sorted(paths):
        if excluded(relative) or not no_symlinks(root, relative):
            raise ValueError(f"Refusing excluded or symlinked source: {relative}")
        path = root / relative
        if not path.is_file():
            raise ValueError(f"Missing authored source: {relative}")
        sources[relative] = path.read_bytes()
    return sources


def build_archive(sources):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(sources.items()):
            info = zipfile.ZipInfo(PREFIX + relative.as_posix(), date_time=(2020, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | (0o755 if relative.suffix == ".sh" else 0o644)) << 16
            archive.writestr(info, data, compresslevel=9)
    data = buffer.getvalue()
    verify_archive(data, sources)
    return data


def verify_archive(data, sources):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        expected = {PREFIX + path.as_posix(): value for path, value in sources.items()}
        names = archive.namelist()
        if len(names) != len(expected) or set(names) != set(expected):
            raise ValueError("ZIP contains missing, duplicate, or unexpected files")
        if archive.testzip() is not None:
            raise ValueError("ZIP failed CRC validation")
        for name in names:
            if archive.read(name) != expected[name]:
                raise ValueError(f"ZIP differs from source: {name}")


class HandbookParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.references = []
        self.images = []
        self.chapters = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "base":
            raise ValueError("A base element would change GitHub Pages relative URLs")
        for name in ("href", "src"):
            if attrs.get(name):
                self.references.append(attrs[name])
        if tag == "img":
            self.images.append(attrs)
        if tag == "section" and "chapter" in attrs.get("class", "").split():
            self.chapters += 1

    handle_startendtag = handle_starttag


def local_target(value, page):
    value = value.strip()
    parsed = urlsplit(value)
    if value.startswith("#") or parsed.scheme == "data":
        return None
    if parsed.netloc or parsed.scheme in {"https", "http", "mailto", "tel"}:
        return None
    if parsed.scheme:
        raise ValueError(f"Unsupported URL in {page}: {value}")
    path = unquote(parsed.path)
    if path.startswith("/") or "\\" in path or "\0" in path:
        raise ValueError(f"Root-relative or unsafe URL in {page}: {value}")
    joined = posixpath.normpath(posixpath.join(page.parent.as_posix(), path)) if path else page.as_posix()
    return safe_relative(joined)


def verify_html(files, sources):
    links = 0
    handbook = None
    download_link = False
    for page, data in files.items():
        if page.suffix != ".html":
            continue
        parsed = HandbookParser()
        parsed.feed(data.decode("utf-8"))
        parsed.close()
        for value in parsed.references:
            if page == PurePosixPath("index.html") and value == DOWNLOAD_URL:
                if DOWNLOAD not in files:
                    raise ValueError(f"Public download URL has no site artifact: {DOWNLOAD_URL}")
                download_link = True
            destination = local_target(value, page)
            if destination is None:
                continue
            if destination not in files and destination / "index.html" not in files:
                raise ValueError(f"Missing site target in {page}: {value}")
            links += 1
            if page == PurePosixPath("index.html") and destination == DOWNLOAD:
                download_link = True
        if page == PurePosixPath("index.html"):
            handbook = parsed
    if handbook is None or handbook.chapters != 17:
        raise ValueError("Expected exactly 17 handbook chapter sections")
    if not download_link:
        raise ValueError(f"Homepage must link to {DOWNLOAD_URL} or {DOWNLOAD}")
    figures = {}
    for path, data in sources.items():
        if path.parts[0] != "content" or path.suffix != ".md":
            continue
        for alt, target in IMAGE.findall(data.decode("utf-8")):
            if alt in figures:
                raise ValueError(f"Duplicate source image description: {alt}")
            source = safe_relative(target.lstrip("/"))
            if source not in sources:
                raise ValueError(f"Image is not an authored source: {source}")
            figures[alt] = sources[source]
    embedded = [image for image in handbook.images if image.get("src", "").startswith("data:image/png;base64,")]
    if len(figures) != 7 or len(embedded) != 7:
        raise ValueError("Expected exactly seven source figures and seven embedded PNGs")
    seen = set()
    for image in embedded:
        alt = image.get("alt")
        encoded = image["src"].split(",", 1)[1]
        data = base64.b64decode(encoded, validate=True)
        if alt in seen or alt not in figures or data != figures[alt]:
            raise ValueError(f"Embedded PNG differs from its source: {alt}")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"Invalid embedded PNG signature: {alt}")
        seen.add(alt)
    return {"local_links": links, "embedded_pngs": len(embedded), "sections": handbook.chapters}


def inventory(output):
    """Reject redirected paths and special files before any output is written."""
    if output.is_symlink():
        raise ValueError(f"Refusing symlinked output: {output}")
    if not output.exists():
        return set(), set()
    if not output.is_dir():
        raise ValueError(f"Output is not a directory: {output}")
    files, directories = set(), set()
    for directory, names, filenames in os.walk(output, followlinks=False):
        for name in names + filenames:
            path = Path(directory) / name
            relative = PurePosixPath(path.relative_to(output).as_posix())
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError(f"Refusing symlink or special output: {relative}")
            (directories if stat.S_ISDIR(mode) else files).add(relative)
    return files, directories


def expected_directories(files):
    return {parent for path in files for parent in path.parents if parent != PurePosixPath(".")}


def check_output(output, expected):
    files, directories = inventory(output)
    if not files and not directories:
        return
    if MANIFEST not in files:
        raise ValueError(f"{output} is not empty and has no build manifest; inspect it before rebuilding")
    record = json.loads((output / MANIFEST).read_text(encoding="utf-8"))
    if record.get("generator") != GENERATOR or not isinstance(record.get("files"), dict):
        raise ValueError("Unrecognized output manifest")
    previous = {safe_relative(name): sha for name, sha in record["files"].items()}
    if MANIFEST in previous or set(previous) - set(expected):
        raise ValueError("Previous output contains paths not owned by this build; inspect them manually")
    if files != set(previous) | {MANIFEST} or directories != expected_directories(files):
        raise ValueError("Unexpected files or directories in _site; nothing was overwritten")
    for relative, sha in previous.items():
        if digest((output / relative).read_bytes()) != sha:
            raise ValueError(f"Output was modified outside this builder: {relative}; nothing was overwritten")


def write_file(base, relative, data):
    if not no_symlinks(base, relative):
        raise ValueError(f"Refusing symlinked write: {base / relative}")
    target = base / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_file():
        raise ValueError(f"Refusing non-file output: {target}")
    # Replace only the checked destination; never remove an output directory.
    with tempfile.NamedTemporaryFile(prefix=".pages-write-", dir=target.parent, delete=False) as temporary:
        temporary.write(data)
        temporary_path = Path(temporary.name)
    try:
        temporary_path.chmod(0o644)
        temporary_path.replace(target)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main():
    for script in ("build_handbook.py", "validate_workshop.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT, check=True)
    sources = collect_sources(ROOT)
    archive = build_archive(sources)
    files = {
        path: data for path, data in sources.items()
        if path == PurePosixPath("index.html") or path.parts[0] in {"content", "docs", "static", "scripts"}
    }
    files[PurePosixPath(".nojekyll")] = b""
    files[DOWNLOAD] = archive
    verification = verify_html(files, sources)
    check_output(OUTPUT, files)
    if ARCHIVE.is_symlink() or (ARCHIVE.exists() and not ARCHIVE.is_file()):
        raise ValueError(f"Refusing redirected or non-file ZIP: {ARCHIVE}")
    manifest = {
        "generator": GENERATOR,
        "files": {path.as_posix(): digest(data) for path, data in sorted(files.items())},
    }
    files[MANIFEST] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    for path, data in sorted(files.items(), key=lambda item: (item[0] == MANIFEST, item[0])):
        write_file(OUTPUT, path, data)
    write_file(ROOT.parent, PurePosixPath(ARCHIVE_NAME), archive)
    actual_files, actual_directories = inventory(OUTPUT)
    if actual_files != set(files) or actual_directories != expected_directories(files):
        raise ValueError("Final output inventory differs from the build")
    for path, data in files.items():
        if (OUTPUT / path).read_bytes() != data:
            raise ValueError(f"Written output differs: {path}")
    for path, data in sources.items():
        if not no_symlinks(ROOT, path) or (ROOT / path).read_bytes() != data:
            raise ValueError(f"Source changed during build: {path}; run the builder again")
    if ARCHIVE.read_bytes() != (OUTPUT / DOWNLOAD).read_bytes():
        raise ValueError("Source ZIP and download ZIP differ")
    verify_archive(ARCHIVE.read_bytes(), sources)
    print(json.dumps({
        "status": "PASS", "output": str(OUTPUT), "source_files": len(sources),
        "site_files": len(files), "zip_crc": "PASS", "source_bytes": "PASS",
        "zip_sha256": digest(archive), "archive": str(ARCHIVE),
        "download_url": DOWNLOAD_URL,
        **verification, "publication": "Not performed",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
