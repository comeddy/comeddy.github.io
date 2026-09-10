#!/usr/bin/env python3
"""Generate and verify GitBook staging without changing workshop source files.

Run from the workshop root:
    python3 scripts/build_gitbook.py
    python3 scripts/build_gitbook.py --check

Uses only the standard library. The existing sibling ZIP is copied, never rebuilt.
The output directory is a standalone GitBook space root; this tool does not publish.
"""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import struct
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "gitbook"
ARCHIVE = ROOT.parent / "physical-ai-isaac-aws.zip"
ASSETS = Path(".gitbook/assets")
IMAGE = re.compile(r'^:image\[([^\]]+)\]\{src="([^"]+)"(?: width=(\d+))?\}$')
LINK = re.compile(r'(!?\[[^\]\n]+\]\()([^)\n]+)(\))')
REFERENCE = re.compile(r'^(\[[^\]]+\]:\s+)(\S+)(.*)$')
INLINE_CODE = re.compile(r"(`+).*?\1")
FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
CONFIG = "root: ./\n\nstructure:\n  readme: README.md\n  summary: SUMMARY.md\n"
DOCS = (
    "device-setup", "hardware-options", "facilitator", "sources", "verification",
    "illustrations", "implementation-contract", "robot-evidence", "aws-evidence",
)
OFFICIAL_REFERENCES = [
    "https://gitbook.com/docs/docs-as-code/git-sync/content-configuration",
    "https://gitbook.com/docs/create-content/blocks/mermaid-blocks",
    "https://gitbook.com/docs/create-content/blocks/insert-files",
    "https://gitbook.com/docs/create-content/blocks/insert-images",
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_body(path):
    text = path.read_text(encoding="utf-8")
    front = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    weight, navigation = 1000, None
    if front:
        title = re.search(r'^title: "([^"\n]+)"$', front[1], re.M)
        order = re.search(r"^weight: (\d+)$", front[1], re.M)
        if not title or not order:
            raise ValueError(f"Unsupported source front matter: {path}")
        navigation, weight = title[1], int(order[1])
        text = text[front.end():]
    text = text.strip() + "\n"
    prose = "".join(part for is_code, part in sections(text) if not is_code)
    headings = re.findall(r"^# (.+)$", prose, re.M)
    if len(headings) != 1:
        raise ValueError(f"Expected one existing H1: {path}")
    return headings[0], navigation or headings[0], weight, text


def sections(text):
    """Keep fenced code byte-for-byte while transforming only surrounding prose."""
    lines, index = text.splitlines(keepends=True), 0
    while index < len(lines):
        opening = FENCE.match(lines[index].rstrip("\n"))
        if not opening:
            yield False, lines[index]
            index += 1
            continue
        start, marker = index, opening[1]
        index += 1
        while index < len(lines):
            closing = re.fullmatch(re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*", lines[index])
            index += 1
            if closing:
                break
        else:
            raise ValueError("Unclosed Markdown code fence")
        yield True, "".join(lines[start:index])


def prose_links(line, rewrite):
    def apply(part):
        reference = REFERENCE.fullmatch(part.rstrip("\n"))
        if reference:
            return reference[1] + rewrite(reference[2]) + reference[3] + ("\n" if part.endswith("\n") else "")
        return LINK.sub(lambda m: m[1] + rewrite(m[2]) + m[3], part)

    result, start = [], 0
    for match in INLINE_CODE.finditer(line):
        result.extend((apply(line[start:match.start()]), match[0]))
        start = match.end()
    result.append(apply(line[start:]))
    return "".join(result)


def relative(target, page):
    return Path(os.path.relpath(target, page.parent)).as_posix()


class GitBookBuild:
    def __init__(self):
        content = sorted(ROOT.glob("content/**/index.ko.md"), key=lambda p: source_body(p)[2])
        if len(content) != 12:
            raise ValueError(f"Expected 12 workshop pages, found {len(content)}")
        self.pages = {}
        for index, source in enumerate(content):
            destination = Path("README.md") if index == 0 else Path("chapters") / f"{index - 1:02d}-{source.parent.name}.md"
            self.pages[source] = destination
        for name in DOCS:
            self.pages[ROOT / f"docs/{name}.md"] = Path(f"appendices/{name}.md")
        self.pages[ROOT / "static/code/sim/README.md"] = Path("appendices/simulator.md")
        self.pages[ROOT / "scripts/cloud/README.md"] = Path("appendices/cloud-tools.md")
        self.pages[ROOT / "scripts/visuals/README.md"] = Path("appendices/3d-visuals.md")
        self.files = {}
        self.assets = {}
        self.figures = []
        self.page_records = []
        self.local_links = 0
        self.archive_files = 0

    def asset(self, source):
        if source != ARCHIVE and not source.is_relative_to(ROOT):
            raise ValueError(f"Asset outside workshop: {source}")
        destination = ASSETS / source.name
        previous = self.assets.get(destination)
        if previous is not None and previous != source:
            raise ValueError(f"Asset filename collision: {source} / {previous}")
        data = source.read_bytes()
        if len(data) >= 100_000_000:
            raise ValueError(f"Asset exceeds GitBook file size limit: {source}")
        self.assets[destination] = source
        self.files[destination] = data
        return destination

    def target(self, target, source, destination):
        parsed = urlsplit(target)
        if parsed.scheme in ("https", "http", "mailto") or target.startswith("#"):
            return target
        if parsed.scheme or parsed.netloc or parsed.query:
            raise ValueError(f"Unsupported local link: {target}")
        path = ((ROOT / parsed.path.lstrip("/")) if parsed.path.startswith("/static/")
                else (source.parent / unquote(parsed.path))).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f"Missing or out-of-root link: {source}: {target}")
        if path.suffix == ".md":
            if path not in self.pages:
                raise ValueError(f"Markdown page lacks navigation mapping: {path}")
            converted = self.pages[path]
        else:
            converted = self.asset(path)
        return relative(converted, destination) + (f"#{parsed.fragment}" if parsed.fragment else "")

    def convert(self, source, destination):
        title, navigation, _, body = source_body(source)
        converted, restored, code = [], [], []
        reverse_targets = {}

        def rewrite(target):
            result = self.target(target, source, destination)
            if result in reverse_targets and reverse_targets[result] != target:
                raise ValueError(f"Ambiguous reverse link in {source}: {target}")
            reverse_targets[result] = target
            return result

        for is_code, part in sections(body):
            if is_code:
                converted.append(part)
                restored.append(part)
                code.append(part)
                continue
            image = IMAGE.fullmatch(part.rstrip("\n"))
            if image:
                target = rewrite(image[2])
                caption = html.escape(image[1])
                figure = (f'<figure><img src="{html.escape(target, quote=True)}" alt="{caption}">'
                          f'<figcaption><p>{caption}</p></figcaption></figure>\n')
                converted.append(figure)
                restored.append(part)
                self.figures.append({"page": destination.as_posix(), "src": target, "alt": image[1]})
            else:
                result = prose_links(part, rewrite)
                converted.append(result)
                restored.append(prose_links(result, lambda t: reverse_targets.get(t, t)))
        if "".join(restored) != body:
            raise ValueError(f"Prose changed during conversion: {source}")
        rendered = "".join(converted)
        if [part for is_code, part in sections(rendered) if is_code] != code:
            raise ValueError(f"Code changed during conversion: {source}")
        if destination == Path("README.md"):
            archive = relative(self.asset(ARCHIVE), destination)
            download = (
                "## 실습 코드 다운로드\n\n"
                "인프라 템플릿, 시뮬레이터·학습·로봇 실행 코드, 로컬 테스트와 오프라인 HTML 교재를 "
                "한 번에 받습니다. 압축을 풀면 `physical-ai-isaac-aws` 폴더가 생깁니다.\n\n"
                f'{{% file src="{archive}" %}}\n'
                "전체 실습 코드와 오프라인 교재 ZIP\n"
                "{% endfile %}\n\n"
                "실제 주행 데이터와 학습된 모델은 실습에서 생성합니다. "
                "[전날 준비](chapters/01-module1-preflight.md)의 노트북·장비 확인부터 진행하세요.\n\n"
            )
            anchor = "## 따라오는 방법\n"
            if rendered.count(anchor) != 1:
                raise ValueError("Homepage download insertion anchor changed")
            rendered = rendered.replace(anchor, download + anchor, 1)
        self.files[destination] = rendered.encode("utf-8")
        self.page_records.append({
            "source": source.relative_to(ROOT).as_posix(),
            "destination": destination.as_posix(),
            "title": title,
            "navigation_title": navigation,
            "source_sha256": digest(source.read_bytes()),
            "output_sha256": digest(self.files[destination]),
            "code_blocks": len(code),
            "code_blocks_sha256": digest("".join(code).encode()),
            "body_round_trip": "PASS",
        })

    def verify_archive(self):
        with zipfile.ZipFile(ARCHIVE) as archive:
            if archive.testzip():
                raise ValueError("Download ZIP failed CRC validation")
            names = archive.namelist()
            required = ["README.md", "static/workshop.yaml", "static/code/train.py",
                        "static/code/sim/run_sim.py", "static/code/device/ros_policy_node.py",
                        "static/code/device/apply_bringup_watchdog.py", "tests/test_policy.py",
                        "static/images/execution/isaac-smoke.png",
                        "static/images/execution/isaac-smoke.provenance.json"]
            for name in required:
                if f"{ROOT.name}/{name}" not in names:
                    raise ValueError(f"Download ZIP is missing {name}")
            for name in names:
                parts = Path(name).parts
                if not parts or parts[0] != ROOT.name or ".." in parts:
                    raise ValueError(f"Unexpected ZIP entry: {name}")
                if "gitbook" in parts or name.lower().endswith(".zip"):
                    raise ValueError(f"Recursive staging/ZIP entry: {name}")
                if name.endswith("/"):
                    continue
                source = ROOT.joinpath(*parts[1:])
                if not source.is_file() or archive.read(name) != source.read_bytes():
                    raise ValueError(f"Download ZIP is stale: {name}; refresh it separately")
                self.archive_files += 1

    def build(self):
        self.verify_archive()
        for source, destination in self.pages.items():
            self.convert(source, destination)
        summary = ["# 목차\n"]
        for index, record in enumerate(self.page_records):
            if index == 1:
                summary.append("\n## 실습 과정\n")
            elif index == 12:
                summary.append("\n## 부록과 운영 자료\n")
            label = record["title"]
            nav = record["navigation_title"]
            title = " " + json.dumps(nav, ensure_ascii=False) if label != nav else ""
            summary.append(f'\n* [{label}]({record["destination"]}{title})\n')
        self.files[Path("SUMMARY.md")] = "".join(summary).encode("utf-8")
        self.files[Path(".gitbook.yaml")] = CONFIG.encode("utf-8")
        self.validate()
        report = {
            "status": "PASS: local source conversion and integrity checks",
            "publication": "Not performed by this generator",
            "live_gitbook_rendering": "Not verified by this generator",
            "regenerate": "python3 scripts/build_gitbook.py",
            "check": "python3 scripts/build_gitbook.py --check",
            "space_root": "gitbook/",
            "workshop_pages": 12,
            "appendix_pages": len(self.pages) - 12,
            "navigation_pages": len(self.pages),
            "local_links_checked": self.local_links,
            "inline_png_figures": len(self.figures),
            "mermaid_blocks_preserved": sum(
                data.count(b"```mermaid\n") for path, data in self.files.items() if path.suffix == ".md"
            ),
            "download_archive": {
                "source": "../physical-ai-isaac-aws.zip",
                "asset": (ASSETS / ARCHIVE.name).as_posix(),
                "bytes": ARCHIVE.stat().st_size,
                "sha256": digest(ARCHIVE.read_bytes()),
                "crc": "PASS",
                "entries_equal_current_workshop": self.archive_files,
                "nested_staging_or_zip": False,
            },
            "equivalence": {
                "all_source_prose_round_trips": True,
                "all_fenced_code_preserved_byte_for_byte": True,
                "front_matter": "Removed title/weight; existing single H1 retained",
                "intentional_addition": "Homepage download section only",
                "source_or_runtime_files_modified": False,
            },
            "official_gitbook_references": OFFICIAL_REFERENCES,
            "pages": self.page_records,
            "figures": self.figures,
            "assets": [
                {"destination": path.as_posix(),
                 "source": os.path.relpath(source, ROOT),
                 "bytes": len(self.files[path]), "sha256": digest(self.files[path])}
                for path, source in sorted(self.assets.items())
            ],
        }
        self.files[Path("build-report.json")] = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
        return report

    def validate(self):
        if len(self.figures) != 7:
            raise ValueError(f"Expected seven inline figures; found {len(self.figures)}")
        page_paths = set(self.pages.values())
        for path, data in self.files.items():
            if path.suffix == ".png":
                if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
                    raise ValueError(f"Invalid PNG: {path}")
                if min(struct.unpack(">II", data[16:24])) < 300:
                    raise ValueError(f"Insufficient PNG resolution: {path}")
            elif path.suffix == ".svg":
                ET.fromstring(data)
            elif path.suffix == ".md":
                text = data.decode("utf-8")
                if "\ufffd" in text or ":image[" in text:
                    raise ValueError(f"Unconverted or corrupt text in {path}")
                prose = "".join(part for is_code, part in sections(text) if not is_code)
                if len(re.findall(r"^# ", prose, re.M)) != 1:
                    raise ValueError(f"Expected one H1: {path}")
                for is_code, part in sections(text):
                    if is_code:
                        continue
                    self.validate_links(part, path, page_paths)
        summary = self.files[Path("SUMMARY.md")].decode()
        navigation = re.findall(r'\]\(([^ )]+)(?: "[^"]*")?\)', summary)
        if len(navigation) != len(page_paths) or {Path(p) for p in navigation} != page_paths:
            raise ValueError("Navigation does not cover each page exactly once")
        if set(p for p in self.assets if p.suffix == ".png") != {
            Path(os.path.normpath(str(Path(f["page"]).parent / f["src"]))) for f in self.figures
        }:
            raise ValueError("PNG assets and inline figures differ")

    def validate_links(self, part, path, page_paths):
        def check(target):
            target = re.sub(r'\s+"[^"]*"$', "", target)
            parsed = urlsplit(html.unescape(target))
            if parsed.scheme in ("http", "https", "mailto"):
                return target
            if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
                raise ValueError(f"Invalid generated link in {path}: {target}")
            destination = Path(os.path.normpath(str(path.parent / unquote(parsed.path)))) if parsed.path else path
            if destination not in self.files:
                raise ValueError(f"Missing generated target in {path}: {target}")
            if destination.suffix == ".md" and destination not in page_paths:
                raise ValueError(f"Link to page outside navigation: {destination}")
            if parsed.fragment and destination.suffix == ".md":
                headings = re.findall(r"^#{1,6} (.+)$", self.files[destination].decode(), re.M)
                slugs = [re.sub(r"[^\w\s-]", "", h.lower()).replace(" ", "-") for h in headings]
                if unquote(parsed.fragment) not in slugs:
                    raise ValueError(f"Unresolved heading anchor: {path}: {target}")
            self.local_links += 1
            return target
        prose_links(part, check)
        for target in re.findall(r'\bsrc="([^"]+)"', part):
            check(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify staging matches current sources; write nothing")
    args = parser.parse_args()
    build = GitBookBuild()
    report = build.build()
    if args.check:
        for path, data in build.files.items():
            if not (OUTPUT / path).is_file() or (OUTPUT / path).read_bytes() != data:
                raise ValueError(f"Missing or stale staging file: {path}; regenerate staging")
        expected_markdown = {p for p in build.files if p.suffix == ".md"}
        actual_markdown = {p.relative_to(OUTPUT) for p in OUTPUT.rglob("*.md")}
        if actual_markdown != expected_markdown:
            raise ValueError("Unexpected Markdown pages in staging; review them before publishing")
    else:
        for path, data in build.files.items():
            target = OUTPUT / path
            if target.is_symlink() or not target.resolve().is_relative_to(OUTPUT.resolve()):
                raise ValueError(f"Refusing redirected output path: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print(json.dumps({
        "status": report["status"], "mode": "check" if args.check else "build",
        "pages": report["navigation_pages"], "figures": report["inline_png_figures"],
        "assets": len(build.assets), "links_checked": report["local_links_checked"],
        "code_blocks_preserved": sum(p["code_blocks"] for p in report["pages"]),
        "zip_files_checked": report["download_archive"]["entries_equal_current_workshop"],
        "report": str(OUTPUT / "build-report.json"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
