#!/usr/bin/env python3
"""Build the workshop's editable AWS diagram, then gate every export.

Source of truth: static/workshop.yaml, scripts/cloud/README.md, and the
training/device chapters. No AWS API calls or infrastructure changes are made.

Requires the architecture-diagram skill and draw.io Desktop for --export.
The standard single-AZ layout generator supplies the topology and official
AWS shapes; the presentation pass adds the host inset and local model handoff.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static/images/architecture"
WIDTH, HEIGHT = 1600, 1000
FONT = "Amazon Ember, Apple SD Gothic Neo, Noto Sans KR, sans-serif"
NAVY = "#15283A"
MUTED = "#506579"
BLUE = "#075BCB"
TEAL = "#087D7E"


def load_layout(skill: Path):
    spec = importlib.util.spec_from_file_location(
        "aws_layout", skill / "scripts/layout_aws.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def styles(raw: str, **changes) -> str:
    values = {}
    bare = []
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            values[key] = value
        elif part:
            bare.append(part)
    values.update({key: str(value) for key, value in changes.items()})
    return ";".join(bare + [f"{key}={value}" for key, value in values.items()]) + ";"


def generate(skill: Path) -> Path:
    layout = load_layout(skill)
    topology = {
        "title": "AWS 배포 아키텍처",
        "external": [{"id": "laptop", "icon": "client", "label": "참가자 노트북"}],
        "region": {
            "label": "선택한 AWS 리전 1개",
            "vpc": {
                "label": "VPC · 10.42.0.0/16",
                "azs": ["가용 영역 1개 (AZ)"],
                "tiers": [
                    {
                        "name": "퍼블릭 서브넷 · 10.42.1.0/24",
                        "kind": "public",
                        "services": [
                            {"id": "ec2", "icon": "ec2", "label": "Amazon EC2"}
                        ],
                    }
                ],
            },
        },
    }
    cells, parents, _, _ = layout.build(topology)
    document = ET.fromstring(layout.to_xml(cells, parents, WIDTH, HEIGHT))
    model = document.find(".//mxGraphModel")
    model.set("background", "#FFFFFF")
    model.set("defaultFontFamily", FONT)
    graph = model.find("root")
    document.set("agent", "generate_aws_architecture.py")
    document.find("diagram").set("name", "AWS 배포 구성")
    by_id = {cell.get("id"): cell for cell in graph}

    def place(cid, x, y, width, height, parent=None):
        cell = by_id[cid]
        geom = cell.find("mxGeometry")
        geom.attrib.update(
            x=str(x), y=str(y), width=str(width), height=str(height)
        )
        if parent:
            cell.set("parent", parent)
        return cell

    def add(cid, value, x, y, width, height, style, parent="1"):
        cell = ET.SubElement(
            graph, "mxCell",
            id=cid, value=value, style=style, vertex="1", parent=parent,
        )
        ET.SubElement(
            cell, "mxGeometry", x=str(x), y=str(y),
            width=str(width), height=str(height), **{"as": "geometry"},
        )
        by_id[cid] = cell
        return cell

    def text(cid, value, x, y, width, height, size=18, color=NAVY,
             bold=False, align="left", parent="1"):
        size = max(20, size)
        return add(
            cid, value, x, y, width, height,
            f"text;html=0;whiteSpace=wrap;strokeColor=none;fillColor=none;"
            f"align={align};verticalAlign=middle;fontFamily={FONT};"
            f"fontSize={size};fontColor={color};fontStyle={int(bold)};"
            "spacing=0;overflow=hidden;",
            parent,
        )

    def rect(cid, x, y, width, height, fill, stroke="none", parent="1",
             rounded=True):
        return add(
            cid, "", x, y, width, height,
            f"rounded={int(rounded)};arcSize=8;fillColor={fill};"
            f"strokeColor={stroke};strokeWidth=1.5;html=0;",
            parent,
        )

    def group(cid, value, x, y, width, height, icon, stroke, color,
              parent="1", fill="none", dashed=False):
        cell = add(
            cid, value, x, y, width, height,
            styles(
                layout.container_style(icon, stroke, color, fill, int(dashed)),
                fontFamily=FONT, fontSize=20, fontStyle=1,
                spacingTop=8, spacingLeft=40, strokeWidth=1.5, grStroke=1, html=0,
            ),
            parent,
        )
        return cell

    def icon(cid, value, x, y, short, parent="1", size=20):
        size = max(20, size)
        return add(
            cid, value, x, y, 78, 78,
            styles(
                layout.icon_style(short), fontFamily=FONT,
                fontSize=size, fontStyle=1, fontColor=NAVY,
                spacingTop=8, html=0,
            ),
            parent,
        )

    def edge(cid, source, target, exit_x, exit_y, entry_x, entry_y,
             color="#545B64", waypoints=()):
        cell = ET.SubElement(
            graph, "mxCell", id=cid, value="", edge="1", parent="1",
            source=source, target=target,
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;"
                "endArrow=block;endFill=1;endSize=10;strokeWidth=2;"
                f"strokeColor={color};fontFamily={FONT};"
                f"exitX={exit_x};exitY={exit_y};exitDx=0;exitDy=0;"
                f"entryX={entry_x};entryY={entry_y};entryDx=0;entryDy=0;"
            ),
        )
        geom = ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
        if waypoints:
            points = ET.SubElement(geom, "Array", **{"as": "points"})
            for x, y in waypoints:
                ET.SubElement(points, "mxPoint", x=str(x), y=str(y))
        by_id[cid] = cell

    # The canvas is a white export boundary, not an architecture component.
    background = rect("canvas", 0, 0, WIDTH, HEIGHT, "#FFFFFF", rounded=False)
    graph.remove(background)
    graph.insert(2, background)
    title = place("title", 50, 40, 1300, 50)
    title.set(
        "style", styles(title.get("style"), fontSize=34, fontFamily=FONT,
                        fontColor=NAVY, html=0, spacing=0)
    )
    text(
        "subtitle", "실습용 단일 계정 · 단일 리전 · 단일 가용 영역(AZ) 구성",
        50, 100, 1400, 30, size=20, color=MUTED,
    )

    cloud = group(
        "cloud", "AWS Cloud · 내 계정 1개", 450, 160, 1100, 660,
        "group_aws_cloud", "#232F3E", NAVY,
    )
    region = place("region", 30, 140, 1030, 490, parent="cloud")
    region.set(
        "style", styles(region.get("style"), fontFamily=FONT, fontSize=20,
                        fontStyle=1, fontColor=BLUE,
                        spacingTop=8, spacingLeft=40, grStroke=1, html=0)
    )
    vpc = place("vpc", 30, 60, 690, 410, parent="region")
    vpc.set(
        "style", styles(vpc.get("style"), fontFamily=FONT, fontSize=20,
                        fontStyle=1, fontColor=MUTED,
                        spacingTop=8, spacingLeft=40, grStroke=1, html=0)
    )
    # One AZ needs no second outline: the subnet's header states its AZ scope.
    graph.remove(by_id.pop("az_0"))
    subnet = place("subnet_0_0", 30, 90, 630, 300, parent="vpc")
    subnet.set("value", "퍼블릭 서브넷 · 10.42.1.0/24 · AZ 1개")
    subnet.set(
        "style", styles(subnet.get("style"), fontFamily=FONT, fontSize=20,
                        fontStyle=1, fontColor="#245F16",
                        spacingTop=8, spacingLeft=40, grStroke=1, html=0)
    )
    text(
        "route", "인터넷 게이트웨이(IGW) · 기본 경로 0.0.0.0/0",
        40, 50, 610, 30, size=18, color=MUTED, parent="vpc",
    )
    sg = group(
        "security-group", "보안 그룹 · SSH 22: 현재 공인 IP/32",
        30, 50, 570, 210, "group_security_group", "#C7131F", "#C62828",
        parent="subnet_0_0", fill="#FFFFFF",
    )
    ec2 = place("ec2_0", 30, 60, 78, 78, parent="security-group")
    ec2.set(
        "style", styles(ec2.get("style"), fontFamily=FONT,
                        fontSize=20, fontStyle=1, fontColor=NAVY,
                        spacingTop=8, html=0)
    )
    text("instance-type", "g6.4xlarge", 150, 40, 380, 30,
         size=25, bold=True, parent="security-group")
    for number, line in enumerate((
        "16 vCPU · 64 GiB RAM · NVIDIA L4 24 GB",
        "Ubuntu 22.04 · Docker",
        "Isaac Sim 5.1.0 + NumPy 모방학습",
        "데이터 수집 → 학습 → 가상 검증",
    )):
        text(f"host-detail-{number}", line, 150, 80 + number * 30, 400, 25,
             size=18, color=NAVY if number < 3 else TEAL,
             parent="security-group")
    text(
        "ebs", "연결 디스크: Amazon EBS · 암호화 gp3 200 GiB",
        40, 260, 570, 30, size=19, parent="subnet_0_0",
    )

    # IAM is account scoped and therefore sits outside the Region boundary.
    layout.ICONS["iam"] = ("identity_and_access_management", "#C7131F", "#F54749")
    icon("iam", "AWS IAM", 500, 20, "iam", parent="cloud", size=18)
    text("profile-title", "EC2 인스턴스 프로파일로 권한 연결",
         610, 20, 460, 30, size=20, bold=True, parent="cloud")
    text("profile-detail", "이 실습 S3 버킷 읽기·쓰기 / SSM 접속 권한",
         610, 60, 460, 30, size=18, color=MUTED, parent="cloud")
    icon("s3", "Amazon S3", 890, 240, "s3", parent="region", size=21)
    text("s3-title", "비공개 결과 버킷", 780, 360, 240, 30,
         size=21, bold=True, align="center", parent="region")
    text("s3-detail", "데이터 · 모델 · 평가 결과\nVPC 외부 / 저장 시 암호화",
         760, 400, 260, 60, size=18, color=MUTED,
         align="center", parent="region")

    laptop_card = rect(
        "laptop-card", 50, 440, 260, 230, "#F3F6FA", "#DAE3EB"
    )
    laptop = place("laptop", 90, 30, 78, 78, parent="laptop-card")
    laptop.set(
        "style", styles(layout.icon_style("user"),
                        shape="mxgraph.aws4.client", fillColor=NAVY,
                        fontFamily=FONT, fontColor=NAVY,
                        fontSize=22, fontStyle=1, spacingTop=14, html=0)
    )
    text("laptop-detail", "명령 실행 · 결과 확인", 20, 170, 220, 30,
         size=18, color=MUTED, align="center", parent="laptop-card")
    text("external-label", "AWS 밖 · 로컬 실습 환경", 50, 400, 300, 30,
         size=18, color=BLUE, bold=True)

    # Three logical transfers; IAM and network routing remain annotations.
    edge("flow-1", "laptop-card", "ec2_0", 1, 0.5, 0, 0.35,
         waypoints=((380, 555), (380, 588)))
    text("flow-1-label", "① SSH\n코드 복사", 320, 470, 120, 70,
         size=18, color=MUTED, align="center")
    edge("flow-2", "ec2_0", "laptop-card", 0, 0.8, 1, 0.8,
         color=TEAL, waypoints=((380, 624),))
    text("flow-2-label", "② 모델 받기\nSCP", 320, 640, 120, 70,
         size=17, color=TEAL, align="center")
    edge("flow-3", "security-group", "s3", 1, 0.55, 0, 0.5,
         waypoints=((1270, 600), (1270, 569)))
    text("flow-3-label", "③ 선택: 결과 보관\nEC2 호스트에서\nHTTPS 업로드",
         1190, 440, 170, 80, size=17, color=MUTED, align="center")

    text(
        "outbound", "외부 다운로드: HTTPS 443 / HTTP 80  ·  선택 접속: SSM은 EC2의 아웃바운드 HTTPS 사용",
        450, 830, 1100, 40, size=18, color=MUTED,
    )
    handoff = rect("handoff", 50, 890, 1500, 70, "#EDF8F6")
    text("handoff-title", "실물 배포", 20, 10, 160, 30, size=22,
         bold=True, color=TEAL, parent="handoff")
    text("handoff-caption", "로봇은 AWS 밖", 20, 40, 210, 25,
         size=15, color=MUTED, parent="handoff")
    for cid, label, x, width in (
        ("handoff-ec2", "EC2", 250, 100),
        ("handoff-laptop", "노트북", 490, 120),
        ("handoff-robot", "TurtleBot3 Burger", 750, 250),
    ):
        text(cid, label, x, 15, width, 40, size=21, bold=True,
             align="center", parent="handoff")
    edge("flow-4", "handoff-ec2", "handoff-laptop", 1, 0.5, 0, 0.5,
         color=TEAL)
    edge("flow-5", "handoff-laptop", "handoff-robot", 1, 0.5, 0, 0.5,
         color=TEAL)
    text("scp-1", "SCP", 400, 888, 130, 25, size=16,
         color=TEAL, align="center")
    text("scp-2", "SCP", 660, 888, 130, 25, size=16,
         color=TEAL, align="center")
    text("local-inference", "로봇 내부 추론 · 센서 → AI → 모터\nRaspberry Pi 4 · ROS 2 Humble",
         1070, 900, 430, 50, size=18, color=NAVY)

    # Parents precede children and arrows precede their labels in document order.
    original = list(graph)
    ordered = original[:2] + [background]
    pending = [cell for cell in original[2:] if cell is not background]
    while pending:
        known = {cell.get("id") for cell in ordered}
        ready = [cell for cell in pending if cell.get("parent") in known]
        if not ready:
            raise ValueError("Missing parent or a cycle in the diagram")
        ordered.extend(ready)
        pending = [cell for cell in pending if cell not in ready]
    graph[:] = ordered
    edges = [cell for cell in graph if cell.get("edge") == "1"]
    assert len(edges) == 5
    assert by_id["s3"].get("parent") == "region"
    assert by_id["iam"].get("parent") == "cloud"
    assert by_id["laptop-card"].get("parent") == "1"
    assert by_id["handoff"].get("parent") == "1"
    assert by_id["ec2_0"].get("parent") == "security-group"
    assert not any(
        cell.get("source") == "ec2_0" and cell.get("target") == "handoff-robot"
        for cell in edges
    )

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "aws-deployment.drawio"
    ET.indent(document, space="  ")
    ET.ElementTree(document).write(target, encoding="utf-8", xml_declaration=True)
    return target


def gate(skill: Path, target: Path) -> dict:
    subprocess.run(
        [sys.executable, str(skill / "scripts/snap_grid.py"),
         str(target), "--in-place"],
        check=True,
    )
    validation = subprocess.run(
        [sys.executable, str(skill / "scripts/validate_drawio.py"), str(target)],
        check=True, capture_output=True, text=True,
    )
    print(validation.stdout, end="")
    lint = subprocess.run(
        [sys.executable, str(skill / "scripts/lint_layout.py"),
         str(target), "--json"],
        check=True, capture_output=True, text=True,
    )
    result = json.loads(lint.stdout)
    if result["score"] < 80:
        raise ValueError("Layout gate failed")
    print(lint.stdout, end="")
    return {
        "validation": validation.stdout.strip().replace(str(ROOT) + "/", ""),
        "layout": result,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-dir", type=Path,
        default=Path.home() / ".agents/skills/architecture-diagram",
    )
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()
    target = generate(args.skill_dir)
    report = gate(args.skill_dir, target)
    report["canvas"] = {"width": WIDTH, "height": HEIGHT, "png_scale": 2}
    report["sources"] = [
        "static/workshop.yaml",
        "scripts/cloud/README.md",
        "content/module5-training/index.ko.md",
        "content/module7-device/index.ko.md",
    ]
    report["icons"] = "Official AWS architecture shapes from draw.io mxgraph.aws4"
    report["visual_review"] = "pending"
    if args.export:
        drawio = shutil.which("drawio")
        if not drawio:
            raise SystemExit("drawio Desktop CLI is required for --export")
        for extension in ("svg", "png"):
            command = [
                drawio, "-x", "-f", extension, "-o",
                str(target.with_suffix(f".{extension}")),
            ]
            if extension == "png":
                command.extend(["-s", "2"])
            subprocess.run(command + [str(target)], check=True)
    (OUT / "aws-deployment.validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Generated: {target}")


if __name__ == "__main__":
    main()
