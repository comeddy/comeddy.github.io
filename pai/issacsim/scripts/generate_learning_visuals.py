#!/usr/bin/env python3
"""Generate five Korean teaching schematics with stdlib SVG and rsvg-convert.

Run from any directory:
    python3 scripts/generate_learning_visuals.py

No simulator, ROS, NumPy, image library, network access, or external font is
used. Shapes are teaching illustrations, never fabricated execution evidence.
"""

from __future__ import annotations

import argparse
import ast
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "static" / "images" / "concepts"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)

INK = "#15283a"
BLUE = "#075bcb"
TEAL = "#086f73"
ORANGE = "#a3480c"
MUTED = "#526b80"
LINE = "#d7e4ef"
PALE_BLUE = "#f1f7fe"
PALE_TEAL = "#e8f6f4"
PALE_ORANGE = "#fff2e6"
WHITE = "#ffffff"
FONT = "Apple SD Gothic Neo, Noto Sans CJK KR, Noto Sans KR, AppleGothic, sans-serif"


def attrs(values):
    return {key.replace("_", "-"): str(value) for key, value in values.items()}


class SVG:
    def __init__(self, slug, number, section, title, subtitle, description, height=740):
        self.slug = slug
        self.height = height
        self.text_id = 0
        self.root = ET.Element(
            f"{{{NS}}}svg",
            attrs(
                dict(
                    width=1200, height=height, viewBox=f"0 0 1200 {height}",
                    role="img", aria_labelledby="title description",
                    font_family=FONT, fill=INK,
                )
            ),
        )
        ET.SubElement(self.root, f"{{{NS}}}title", id="title").text = title
        ET.SubElement(self.root, f"{{{NS}}}desc", id="description").text = description
        definitions = ET.SubElement(self.root, f"{{{NS}}}defs")
        for name, color in (
            ("blue", BLUE), ("teal", TEAL), ("orange", ORANGE), ("muted", MUTED),
        ):
            marker = ET.SubElement(
                definitions, f"{{{NS}}}marker",
                attrs(dict(id=f"arrow-{name}", viewBox="0 0 10 10",
                           refX=8, refY=5, markerWidth=8, markerHeight=8,
                           orient="auto-start-reverse", markerUnits="userSpaceOnUse")),
            )
            ET.SubElement(marker, f"{{{NS}}}path", d="M 1 1 L 9 5 L 1 9 Z", fill=color)
        self.rect(0, 0, 1200, height, fill=WHITE, radius=0)
        self.text(44, 44, section, 24, BLUE, weight=700)
        self.text(44, 100, title, 42, weight=700)
        self.text(44, 140, subtitle, 26, MUTED)

    def add(self, tag, **values):
        return ET.SubElement(self.root, f"{{{NS}}}{tag}", attrs(values))

    def rect(self, x, y, width, height, *, fill=PALE_BLUE, stroke="none", radius=18, **extra):
        return self.add(
            "rect", x=x, y=y, width=width, height=height, rx=radius,
            fill=fill, stroke=stroke, **extra,
        )

    def circle(self, x, y, radius, *, fill=WHITE, stroke="none", **extra):
        return self.add("circle", cx=x, cy=y, r=radius, fill=fill, stroke=stroke, **extra)

    def text(self, x, y, label, size=24, color=INK, *, anchor="start", weight=500, **extra):
        self.text_id += 1
        node = self.add(
            "text", id=f"text-{self.text_id}", x=x, y=y, font_size=size,
            fill=color, text_anchor=anchor, font_weight=weight, **extra,
        )
        node.text = label
        return node

    def line(self, x1, y1, x2, y2, color=LINE, width=2, **extra):
        return self.add(
            "line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=color,
            stroke_width=width, stroke_linecap="round", **extra,
        )

    def path(self, d, *, color=BLUE, width=3, fill="none", **extra):
        return self.add(
            "path", d=d, fill=fill, stroke=color, stroke_width=width,
            stroke_linecap="round", stroke_linejoin="round", **extra,
        )

    def arrow(self, points, color="blue", *, dashed=False, width=3):
        options = {"marker_end": f"url(#arrow-{color})"}
        if dashed:
            options["stroke_dasharray"] = "7 7"
        return self.path(
            points, color={"blue": BLUE, "teal": TEAL, "orange": ORANGE, "muted": MUTED}[color],
            width=width, **options,
        )

    def card(self, x, y, width, height, fill=PALE_BLUE, **extra):
        return self.rect(x, y, width, height, fill=fill, stroke=LINE, **extra)

    def save(self, destination):
        ET.indent(self.root, space="  ")
        ET.ElementTree(self.root).write(destination, encoding="utf-8", xml_declaration=True)


def robot_top(s, cx, cy, scale=1.0):
    """Simplified Burger icon. +X/front is to the right; wheels lie at +/-Y."""
    group = s.add("g", transform=f"translate({cx} {cy}) scale({scale})")

    def shape(tag, **values):
        return ET.SubElement(group, f"{{{NS}}}{tag}", attrs(values))

    for wheel_y in (-33, 21):
        shape("rect", x=-18, y=wheel_y, width=32, height=12, rx=4, fill=INK)
        for x in (-10, 0, 10):
            shape("line", x1=x, y1=wheel_y + 2, x2=x, y2=wheel_y + 10,
                  stroke=WHITE, stroke_width=1, opacity=0.5)
    shape("rect", x=-29, y=-22, width=58, height=44, rx=14,
          fill=WHITE, stroke=BLUE, stroke_width=3)
    shape("circle", cx=-7, cy=0, r=14, fill=PALE_TEAL, stroke=TEAL, stroke_width=3)
    shape("circle", cx=-7, cy=0, r=5, fill=TEAL)
    shape("path", d="M 13 -7 L 22 0 L 13 7", fill="none", stroke=BLUE,
          stroke_width=3, stroke_linejoin="round", stroke_linecap="round")


def robot_front(s, cx, cy, scale=1.0, *, lifted=False):
    group = s.add("g", transform=f"translate({cx} {cy}) scale({scale})")

    def shape(tag, **values):
        return ET.SubElement(group, f"{{{NS}}}{tag}", attrs(values))

    for x in (-37, 23):
        shape("rect", x=x, y=1, width=14, height=33, rx=5, fill=INK)
    for y in (-18, 0):
        shape("rect", x=-29, y=y, width=58, height=9, rx=4,
              fill=WHITE, stroke=BLUE, stroke_width=2.5)
    for x in (-21, 21):
        shape("line", x1=x, y1=-14, x2=x, y2=3, stroke=BLUE, stroke_width=3)
    shape("rect", x=-12, y=-35, width=24, height=16, rx=5, fill=TEAL)
    shape("ellipse", cx=0, cy=-35, rx=12, ry=4, fill=PALE_TEAL,
          stroke=TEAL, stroke_width=2)
    if lifted:
        shape("path", d="M -16 10 L -21 47 L 21 47 L 16 10",
              fill=PALE_ORANGE, stroke=ORANGE, stroke_width=2.5)
        shape("path", d="M -48 55 H 48", stroke=LINE, stroke_width=3)
    else:
        shape("path", d="M -48 36 H 48", stroke=LINE, stroke_width=3)


def laptop(s, cx, cy, scale=1.0):
    s.rect(cx - 44 * scale, cy - 32 * scale, 88 * scale, 56 * scale,
           fill=WHITE, stroke=BLUE, radius=6 * scale, stroke_width=3)
    s.path(
        f"M {cx - 55 * scale} {cy + 33 * scale} "
        f"H {cx + 55 * scale} L {cx + 44 * scale} {cy + 24 * scale} "
        f"H {cx - 44 * scale} Z",
        fill=PALE_BLUE, color=BLUE,
    )
    for offset, length in ((-14, 44), (0, 56), (14, 32)):
        s.line(cx - 28 * scale, cy + offset * scale, cx + (length - 28) * scale,
               cy + offset * scale, TEAL, 4)


def shield(s, cx, cy):
    s.path(
        f"M {cx} {cy - 50} L {cx + 44} {cy - 33} V {cy + 2} "
        f"Q {cx + 42} {cy + 35} {cx} {cy + 54} "
        f"Q {cx - 42} {cy + 35} {cx - 44} {cy + 2} V {cy - 33} Z",
        fill=PALE_ORANGE, color=ORANGE, width=3,
    )
    s.path(f"M {cx - 19} {cy} L {cx - 4} {cy + 15} L {cx + 23} {cy - 17}",
           color=ORANGE, width=6)


def physical_ai_loop():
    s = SVG(
        "physical-ai-loop", 1, "센서에서 행동까지",
        "거리 숫자가 바퀴의 움직임이 되기까지",
        "작은 신경망은 속도를 제안하고, 별도의 정지 검사가 출력을 확인합니다",
        "2D 라이다, 12개 구역의 최소 거리(m), 작은 정책, 독립 정지 검사, "
        "모터 순서. 거리와 수신 시각은 정지 검사에도 직접 전달된다. "
        "실물의 움직임은 다시 센서 관측으로 돌아온다. 전방 최소 거리 0.35 m 이하, "
        "스캔 나이 0.5 s 이상 또는 무효 입력이면 정지 고정. 원인 해결 후 노드 재시작.",
    )
    columns = [(44, 184), (268, 184), (492, 184), (716, 212), (968, 188)]
    titles = ["2D 라이다", "12개 거리", "작은 정책", "독립 정지 검사", "모터 · 바퀴"]
    details = [
        ("주변 거리 측정", "360° 스캔"), ("구역별 최솟값", "거리 단위 m"),
        ("전진 · 회전", "속도 두 개 제안"), ("이상이면 0", "정지를 유지"),
        ("명령을 실행", "로봇이 이동"),
    ]
    for i, ((x, w), title, detail) in enumerate(zip(columns, titles, details)):
        s.card(x, 198, w, 262, PALE_ORANGE if i == 3 else PALE_BLUE)
        s.text(x + w / 2, 240, title, 27, anchor="middle", weight=700)
        s.text(x + w / 2, 398, detail[0], 24, anchor="middle")
        s.text(x + w / 2, 434, detail[1], 24, MUTED, anchor="middle")
        if i < 4:
            s.arrow(f"M {x + w + 7} 321 H {columns[i + 1][0] - 8}")
    robot_top(s, 136, 314, 1.05)
    for angle in range(0, 360, 45):
        a = math.radians(angle)
        s.line(136 + 45 * math.cos(a), 314 - 45 * math.sin(a),
               136 + 67 * math.cos(a), 314 - 67 * math.sin(a), TEAL, 3)
    for row in range(3):
        for col in range(4):
            s.rect(306 + col * 28, 273 + row * 31, 22, 24,
                   fill=BLUE if (row + col) % 3 else TEAL, radius=5)
    layers = [[(538, 290), (538, 322), (538, 354)],
              [(582, 276), (582, 306), (582, 336), (582, 366)],
              [(630, 306), (630, 338)]]
    for left, right in zip(layers, layers[1:]):
        for a in left:
            for b in right:
                s.line(*a, *b, "#b9cfe8", 2)
    for layer in layers:
        for x, y in layer:
            s.circle(x, y, 9, fill=BLUE if x < 630 else TEAL)
    shield(s, 822, 318)
    robot_front(s, 1062, 318, 1.18)
    s.arrow("M 360 460 V 492 H 822 V 464", "orange", dashed=True)
    s.text(591, 530, "거리 · 최신 수신 시각", 24, ORANGE, anchor="middle")
    s.arrow("M 1062 460 V 572 H 136 V 467", "teal", width=4)
    s.text(600, 610, "실제 로봇이 움직이면, 센서로 다시 관측합니다", 28, TEAL, anchor="middle")
    s.card(44, 635, 1112, 79, PALE_ORANGE)
    s.text(600, 667, "전방 ≤ 0.35 m 또는 스캔 나이 ≥ 0.5 s → 정지 고정",
           27, ORANGE, anchor="middle", weight=700)
    s.text(600, 700, "정지 후에는 원인을 해결하고 노드를 재시작", 24, anchor="middle")
    return s


def polar(cx, cy, radius, degrees):
    angle = math.radians(degrees)
    # SVG +Y points down; negate sine to keep ROS positive angles CCW.
    return cx + radius * math.cos(angle), cy - radius * math.sin(angle)


def lidar_sectors():
    s = SVG(
        "lidar-sectors", 2, "거리 센서 읽기",
        "한 바퀴를 12칸으로, 한 칸은 가장 가까운 거리",
        "전방은 +X · 0 rad, 각도는 위에서 볼 때 반시계(CCW)로 증가합니다",
        "각도는 +X 전방에서 반시계 방향. 0번은 [0,30)도, 11번은 [330,360)도로 "
        "두 구역 모두 전방 정지 검사에 사용한다. 360도는 0도로 돌아온다. "
        "유효한 한 구역 안에서는 최소 거리를 선택하며, 미터로 저장한다. "
        "모델 입력만 clip(거리,0,3.5)/3.5로 정규화한다. "
        "오른쪽 벽의 예시는 같은 구역의 1.5, 약 1.6, 약 1.7 m를 1.5 m로 요약한다.",
        height=760,
    )
    s.card(44, 178, 532, 510)
    cx, cy, radius = 292, 418, 168
    for sector in range(12):
        start, end = sector * 30, (sector + 1) * 30
        ax, ay = polar(cx, cy, radius, start)
        bx, by = polar(cx, cy, radius, end)
        s.path(
            f"M {cx} {cy} L {ax:.4f} {ay:.4f} "
            f"A {radius} {radius} 0 0 0 {bx:.4f} {by:.4f} Z",
            fill=PALE_TEAL if sector in (0, 11) else WHITE,
            color=TEAL if sector in (0, 11) else LINE, width=2,
            id=f"sector-{sector}", data_sector=sector,
            data_start_deg=start, data_end_deg=end,
        )
        tx, ty = polar(cx, cy, 132, start + 15)
        s.text(round(tx, 3), round(ty + 10, 3), str(sector), 30,
               TEAL if sector in (0, 11) else MUTED, anchor="middle", weight=700)
    s.arrow("M 351 418 H 548", "blue")
    s.text(516, 452, "+X", 26, BLUE, anchor="middle", weight=700)
    s.text(516, 484, "0 rad", 24, BLUE, anchor="middle")
    s.arrow("M 292 351 V 225", "muted")
    s.text(292, 212, "+Y · 왼쪽", 24, MUTED, anchor="middle")
    s.text(89, 429, "180°", 24, MUTED, anchor="middle")
    s.text(292, 624, "270°", 24, MUTED, anchor="middle")
    ax, ay = polar(cx, cy, 199, 20)
    bx, by = polar(cx, cy, 199, 69)
    s.arrow(f"M {ax:.3f} {ay:.3f} A 199 199 0 0 0 {bx:.3f} {by:.3f}", "teal")
    s.text(486, 260, "CCW", 24, TEAL, anchor="middle", weight=700)
    s.circle(cx, cy, 52, fill=WHITE, stroke=LINE, stroke_width=2)
    robot_top(s, cx + 7 * 1.1, cy, 1.1)
    s.text(310, 667, "전방 = 11번과 0번", 28, TEAL, anchor="middle", weight=700)
    s.card(600, 178, 556, 161, PALE_TEAL)
    s.text(624, 217, "전방은 두 구역의 경계", 28, weight=700)
    s.text(632, 265, "0번  ·  [0°, 30°)", 28, TEAL, weight=700)
    s.text(632, 308, "11번 ·  [330°, 360°)", 28, TEAL, weight=700)
    s.text(1118, 272, "360°", 24, MUTED, anchor="end")
    s.text(1118, 308, "= 0°", 24, MUTED, anchor="end")
    s.card(600, 355, 556, 211)
    s.text(624, 393, "구역 안의 거리 → 최솟값", 28, weight=700)
    # A wall at x=1.5 m and rays at 0/20/28 degrees all belong to sector 0.
    # The lengths are 1.5/cos(theta), rounded to one decimal place below.
    ox, oy, wall_x = 641, 536, 791
    s.rect(wall_x, 443, 10, 106, fill=ORANGE, radius=3)
    s.text(wall_x + 5, 428, "벽", 24, ORANGE, anchor="middle")
    for angle in (28, 20, 0):
        ey = oy - (wall_x - ox) * math.tan(math.radians(angle))
        distance = 1.5 / math.cos(math.radians(angle))
        s.line(ox, oy, wall_x, ey, TEAL, 3)
        s.circle(wall_x, ey, 4, fill=ORANGE)
        s.text(817, ey + 8, f"{distance:.1f} m", 24, MUTED)
    s.circle(ox, oy, 7, fill=TEAL)
    s.arrow("M 902 504 H 945", "blue")
    s.text(1050, 507, "1.5 m", 40, BLUE, anchor="middle", weight=700)
    s.text(1050, 544, "대표 거리", 24, anchor="middle")
    s.card(600, 584, 556, 104, PALE_TEAL)
    s.text(624, 621, "정규화 = clip(거리, 0, 3.5) ÷ 3.5", 26, weight=700)
    s.text(624, 661, "1.5 m → 약 0.43  ·  모델 입력은 0~1", 24, TEAL)
    s.text(44, 730, "거리는 m로 저장합니다. 무효·누락 구역은 0으로 처리하고 정지합니다.",
           24, MUTED)
    return s


def sim_to_real():
    s = SVG(
        "sim-to-real", 3, "가상에서 실물로",
        "가상에서 배우고, 실제 로봇 안에서 판단해요",
        "가상 주행 데이터 → 학습·검증 → 모델 파일 복사 → 로봇의 로컬 추론",
        "AWS EC2의 실제 Isaac Sim 주행에서 규칙 기반 교사가 운전하여 dataset.npz를 수집한다. "
        "observations는 Nx12 미터, actions는 Nx2 m/s·rad/s, episodes는 N개 정수 ID. "
        "에피소드 단위로 학습용과 검증용을 분리한다. NumPy 정책은 CPU에서도 학습 가능하다. "
        "policy.npz와 policy.npz.sha256을 scp로 EC2에서 노트북에 받고 노트북에서 Pi에 보낸다. "
        "Pi에서 SHA-256을 확인한 뒤 센서, 정책, 정지 검사, 모터의 로컬 루프를 실행한다. "
        "AWS는 실시간 모터 제어 루프에 참여하지 않는다.",
    )
    s.card(44, 177, 1112, 312)
    s.text(68, 215, "AWS EC2 · 실제 Isaac Sim 주행 + NumPy 학습", 28, BLUE, weight=700)
    s.card(68, 238, 314, 227, WHITE)
    s.text(90, 276, "규칙 교사가 운전", 27, weight=700)
    s.text(90, 318, "dataset.npz", 29, BLUE, weight=700)
    s.text(90, 359, "관측 N×12 · 거리(m)", 25)
    s.text(90, 398, "행동 N×2 · m/s, rad/s", 25)
    s.text(90, 437, "episodes · 각 행의 실험 ID", 24)
    s.arrow("M 389 348 H 412")
    s.card(422, 238, 340, 227, WHITE)
    s.text(444, 276, "에피소드 통째로 분리", 28, weight=700)
    s.rect(444, 299, 296, 60, fill=PALE_BLUE, radius=12)
    s.text(592, 338, "학습용 → 정책 학습", 27, BLUE, anchor="middle", weight=700)
    s.rect(444, 375, 296, 60, fill=PALE_TEAL, radius=12)
    s.text(592, 414, "검증용 → 오차 확인", 27, TEAL, anchor="middle", weight=700)
    s.arrow("M 770 348 H 796")
    s.card(806, 238, 326, 227, WHITE)
    s.text(830, 276, "배운 결과를 파일로", 28, weight=700)
    s.path("M 836 305 H 867 L 887 325 V 382 H 836 Z", fill=PALE_BLUE, color=BLUE)
    s.path("M 867 305 V 325 H 887", color=BLUE)
    s.line(846, 344, 876, 344, TEAL, 3)
    s.line(846, 359, 869, 359, TEAL, 3)
    s.text(903, 340, "policy.npz", 30, BLUE, weight=700)
    s.text(903, 379, "+ SHA-256", 25, TEAL, weight=700)
    s.text(830, 437, "모델 + 해시 파일", 25)
    s.arrow("M 970 466 V 513 H 246 V 550")
    s.rect(415, 497, 340, 33, fill=WHITE, radius=6)
    s.text(585, 523, "scp · EC2 → 노트북", 25, BLUE, anchor="middle", weight=700)
    s.card(68, 557, 352, 131)
    laptop(s, 134, 620, 0.85)
    s.text(198, 602, "내 노트북", 29, weight=700)
    s.text(198, 646, "두 파일 전달", 25, MUTED)
    s.arrow("M 429 622 H 489")
    s.text(459, 606, "scp", 24, BLUE, anchor="middle", weight=700)
    s.card(500, 549, 632, 139, PALE_TEAL)
    robot_top(s, 558, 600, 0.75)
    s.text(615, 586, "Raspberry Pi · 로컬 추론", 28, TEAL, weight=700)
    s.text(615, 623, "SHA-256 확인 후 모델 읽기", 25)
    s.text(816, 666, "센서 → 정책 → 정지 검사 → 모터", 26, TEAL, anchor="middle", weight=700)
    s.text(600, 725, "AWS에서 실시간 모터 명령을 보내지 않습니다.", 27, BLUE, anchor="middle")
    return s


def deployment_stages():
    s = SVG(
        "deployment-stages", 4, "실물 배포의 순서",
        "바닥에 놓기 전에, 세 번의 문을 통과해요",
        "앞 단계가 통과해야 다음 단계로 · 실패하면 진행을 중단합니다",
        "시작 전 명령 만료 패치 설치, 재빌드, bringup 재시작, 모터 명령 publisher 0 확인, "
        "물리 전원 차단 준비가 필요하다. 1: --arm 없이 preview만 발행하고 /cmd_vel에는 발행하지 않는다. "
        "2: 바퀴를 띄워 --arm --max-linear 0.05로 실행, 0.35 m 이내 전방 장애물에서 정지 고정 확인. "
        "3: 바퀴를 계속 띄우고 bringup을 유지한 채 정책을 SIGKILL하여 실제 바퀴 정지가 1.5 s "
        "이내인지 측정한다. bringup 종료와 통신 단절도 각각 별도로 시험한다. "
        "4: 모두 통과한 뒤 정책을 종료하고 바닥에 내려놓아 최대 0.05 m/s로 30초 주행한다. "
        "1.5 s는 교육용 실측 통과 기준이며 보장값이 아니다. Python 스캔 만료는 0.5 s, "
        "검사 주기는 0.05 s. bringup 명령 만료 0.5 s와 OpenCR heartbeat timeout은 연속 작동. "
        "OpenCR PUSH SW1/SW2는 주행 테스트 버튼이며 물리 비상 정지 버튼이 아니다.",
        height=760,
    )
    s.card(44, 170, 1112, 80, PALE_ORANGE)
    s.text(66, 203, "시작 조건 · 명령 만료 패치 설치 → 재빌드 → bringup 재시작",
           26, ORANGE, weight=700)
    s.text(66, 237, "정책 시작 전 /cmd_vel 발행자 0 · 물리 전원 차단 준비", 24)
    s.text(596, 279, "2~3단계는 바퀴를 계속 띄워 둡니다", 24, TEAL, anchor="middle")
    columns = [(44, 244), (326, 244), (608, 258), (904, 252)]
    titles = ["그림자 실행", "바퀴를 띄워 실행", "독립 정지 시험", "바닥에서 30초"]
    for i, ((x, w), title) in enumerate(zip(columns, titles)):
        s.card(x, 289, w, 327, PALE_TEAL if i == 3 else PALE_BLUE)
        s.circle(x + 29, 311, 18, fill=TEAL if i == 3 else BLUE)
        s.text(x + 29, 320, str(i + 1), 24, WHITE, anchor="middle", weight=700)
        s.text(x + w / 2, 356, title, 27, anchor="middle", weight=700)
        if i < 3:
            s.arrow(f"M {x + w + 6} 416 H {columns[i + 1][0] - 7}", "teal", width=4)
    laptop(s, 166, 414, 0.7)
    s.text(166, 485, "--arm 없음", 26, BLUE, anchor="middle", weight=700)
    s.text(166, 529, "/cmd_vel 발행 없음", 24, anchor="middle")
    s.text(166, 570, "preview만 확인", 25, MUTED, anchor="middle")
    robot_front(s, 448, 403, 0.83, lifted=True)
    s.text(448, 484, "--arm · ≤0.05 m/s", 25, BLUE, anchor="middle", weight=700)
    s.text(448, 529, "전방 ≤0.35 m 정지", 24, anchor="middle")
    s.text(448, 568, "상자를 치워도", 24, MUTED, anchor="middle")
    s.text(448, 601, "자동 재개 없음", 24, ORANGE, anchor="middle", weight=700)
    s.circle(737, 411, 32, fill=WHITE, stroke=ORANGE, stroke_width=3)
    s.rect(728, 368, 18, 9, fill=ORANGE, radius=3)
    s.line(737, 411, 737, 392, ORANGE, 4)
    s.line(737, 411, 753, 418, ORANGE, 4)
    s.text(737, 471, "bringup 유지 상태에서", 24, anchor="middle")
    s.text(737, 504, "정책 강제 종료", 25, anchor="middle", weight=700)
    s.text(737, 543, "실측 정지 ≤1.5 s", 29, ORANGE, anchor="middle", weight=700)
    s.text(737, 578, "bringup 종료·통신 단절", 24, anchor="middle")
    s.text(737, 607, "각각 정지 확인", 24, anchor="middle")
    robot_front(s, 1030, 412, 0.85)
    s.rect(923, 464, 214, 38, fill=WHITE, radius=10)
    s.text(1030, 491, "모든 정지 시험 통과", 24, TEAL, anchor="middle", weight=700)
    s.text(1030, 537, "정책을 끈 뒤", 24, anchor="middle")
    s.text(1030, 570, "바닥에 내려놓기", 24, anchor="middle")
    s.text(1030, 604, "≤0.05 m/s 유지", 25, TEAL, anchor="middle", weight=700)
    s.card(44, 636, 1112, 72, PALE_ORANGE)
    s.text(66, 667, "미통과 → 바닥 주행 금지", 28, ORANGE, weight=700)
    s.text(66, 697, "1.5초는 실측 통과 기준이며, 코드나 펌웨어의 보장 시간이 아닙니다.", 24)
    s.text(44, 745, "센서 만료 0.5 s · 검사 0.05 s / bringup 명령 만료 0.5 s → OpenCR 통신 timeout",
           24, MUTED)
    return s


def ray_rectangle_distance(origin, angle, rectangles, maximum):
    """Clip decorative rays to drawn walls/boxes; never creates training data."""
    direction = (math.cos(angle), math.sin(angle))
    result = maximum
    for x, y, w, h in rectangles:
        near, far = 0.0, maximum
        for position, delta, low, high in zip(origin, direction, (x, y), (x + w, y + h)):
            if abs(delta) < 1e-12:
                if not low <= position <= high:
                    far = -1.0
                    break
            else:
                a, b = sorted(((low - position) / delta, (high - position) / delta))
                near, far = max(near, a), min(far, b)
        if near <= far:
            result = min(result, near)
    return result


def sim_arena():
    s = SVG(
        "sim-arena", 5, "가상 실험실 살펴보기",
        "로봇이 연습할 작은 방을 위에서 보면",
        "개념도 · 실제 Isaac Sim 실행 화면이 아닙니다",
        "공식 TurtleBot3 Burger를 사용하는 가상 경기장의 교육용 평면도. "
        "안쪽 6x6 m, 벽 4개, 0.45x0.45x0.50 m 상자 8개. "
        "그림의 배치는 설명용이며 실제 seed의 실행 결과가 아니다. "
        "실제 시뮬레이터는 base_footprint 기준 높이 약 0.182 m에서 "
        "360개의 수평 PhysX ray로 같은 벽·상자의 충돌 형상을 측정한다. "
        "이 그림의 광선은 일부만 표시하고 로봇 아이콘은 확대했다.",
        height=760,
    )
    s.root.find(f"{{{NS}}}text[@id='text-3']").set("fill", ORANGE)
    left, top, side, scale = 95, 217, 432, 72
    s.rect(left, top, side, side, fill=PALE_BLUE, radius=0)
    for i in range(1, 6):
        s.line(left + i * scale, top, left + i * scale, top + side, LINE, 1)
        s.line(left, top + i * scale, left + side, top + i * scale, LINE, 1)
    s.line(left, 184, left + side, 184, MUTED)
    for x in (left, left + side):
        s.line(x, 177, x, 194, MUTED)
    s.rect(252, 163, 119, 35, fill=WHITE, radius=0)
    s.text(311, 189, "안쪽 6 m", 26, MUTED, anchor="middle")
    s.line(61, top, 61, top + side, MUTED)
    for y in (top, top + side):
        s.line(54, y, 70, y, MUTED)
    s.rect(44, 370, 34, 125, fill=WHITE, radius=0)
    s.text(68, 433, "안쪽 6 m", 26, MUTED, anchor="middle", transform="rotate(-90 68 433)")
    walls = [(-3.2, -3.2, 0.2, 6.4), (3.0, -3.2, 0.2, 6.4),
             (-3.0, -3.2, 6.0, 0.2), (-3.0, 3.0, 6.0, 0.2)]
    centers = [(-2.0, 1.9), (-0.5, 2.0), (1.8, 1.8), (-1.7, 0.15),
               (0.5, 0.7), (2.0, -0.3), (-1.8, -1.9), (0.8, -1.7)]
    boxes = [(x - 0.225, y - 0.225, 0.45, 0.45) for x, y in centers]

    def pixel(x, y):
        return left + (x + 3) * scale, top + (3 - y) * scale

    origin = (-0.5, -0.4)
    ox, oy = pixel(*origin)
    for angle in range(0, 360, 15):
        a = math.radians(angle)
        distance = ray_rectangle_distance(origin, a, walls + boxes, 3.5)
        ex, ey = pixel(origin[0] + distance * math.cos(a), origin[1] + distance * math.sin(a))
        s.line(ox, oy, round(ex, 3), round(ey, 3), TEAL, 2, opacity=0.45,
               data_ray_deg=angle)
        s.circle(round(ex, 3), round(ey, 3), 3, fill=TEAL)
    for i, (x, y, w, h) in enumerate(walls):
        px, py = pixel(x, y + h)
        s.rect(px, py, w * scale, h * scale, fill=INK, radius=2, id=f"wall-{i + 1}")
    for i, (x, y, w, h) in enumerate(boxes):
        px, py = pixel(x, y + h)
        s.rect(px, py, w * scale, h * scale, fill=PALE_ORANGE, stroke=ORANGE,
               radius=4, stroke_width=2, id=f"box-{i + 1}")
        s.text(px + w * scale / 2, py + 25, str(i + 1), 24, ORANGE,
               anchor="middle", weight=700)
    # Align the ray origin with the offset LDS dot in the enlarged robot icon.
    robot_top(s, ox + 7 * 0.8, oy, 0.8)
    s.text(311, 697, "위에서 본 모습 · 배치는 설명용", 25, MUTED, anchor="middle")
    s.card(603, 178, 553, 154)
    s.text(627, 217, "공식 TurtleBot3 Burger 사용", 28, weight=700)
    robot_front(s, 668, 276, 0.9)
    s.text(733, 268, "두 바퀴로 이동", 27, BLUE, weight=700)
    s.text(733, 309, "PhysX가 주행·접촉 계산", 25)
    s.card(603, 351, 553, 143)
    s.text(627, 390, "상자 8개 + 벽 4개", 28, weight=700)
    s.rect(628, 414, 42, 42, fill=PALE_ORANGE, stroke=ORANGE, radius=5, stroke_width=2)
    s.text(690, 430, "상자: 0.45 × 0.45 × 0.50 m", 25)
    s.text(690, 471, "배치·출발 자세는 seed로 변경", 24)
    s.card(603, 513, 553, 177, PALE_TEAL)
    s.text(627, 552, "라이다는 바닥과 수평", 28, TEAL, weight=700)
    s.line(627, 660, 1127, 660, MUTED, 2)
    s.rect(1008, 572, 50, 88, fill=PALE_ORANGE, stroke=ORANGE, radius=3, stroke_width=2)
    # Side elevation: 0.182 m laser height vs. a 0.50 m box (176 px/m).
    laser_y = 660 - 0.182 * 176
    s.rect(646, 641, 69, 9, fill=WHITE, stroke=BLUE, radius=3, stroke_width=2)
    for x in (658, 703):
        s.circle(x, 650, 10, fill=INK)
    s.line(680, 640, 680, laser_y, BLUE, 4)
    s.rect(669, laser_y - 6, 22, 12, fill=TEAL, radius=4)
    s.arrow(f"M 694 {laser_y:.3f} H 1004", "teal", width=3)
    s.text(837, 605, "높이 약 0.182 m", 26, TEAL, anchor="middle", weight=700)
    s.text(627, 682, "360개 수평 ray", 24, MUTED)
    s.text(44, 739, "광선은 일부만 표시 · 로봇 아이콘 확대 · 벽과 상자의 충돌 형상을 측정합니다.",
           24, MUTED)
    return s


def source_contract():
    """Read literal constants without importing runtime or its dependencies."""
    def constants(relative):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        result = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                try:
                    result[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    pass
        return result

    expected = {
        "static/code/workshop_core.py": {
            "NUM_SECTORS": 12, "MAX_RANGE": 3.5, "STOP_DISTANCE": 0.35,
            "SCAN_TIMEOUT": 0.5, "FRONT_SECTORS": (11, 0),
        },
        "static/code/device/ros_policy_node.py": {
            "WATCHDOG_PERIOD": 0.05, "DEFAULT_MAX_LINEAR": 0.05,
            "PREVIEW_TOPIC": "/workshop/cmd_vel_preview", "COMMAND_TOPIC": "/cmd_vel",
        },
        "static/code/sim/scene_math.py": {"ARENA_HALF_SIZE": 3.0, "OBSTACLE_HEIGHT": 0.50},
    }
    for path, values in expected.items():
        actual = constants(path)
        for key, value in values.items():
            if actual.get(key) != value:
                raise ValueError(f"{path}: {key} changed; review diagram labels before regenerating")


def validate(svg):
    """Check the portable SVG contract and geometry data before export."""
    for node in svg.root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in {"foreignObject", "script", "image", "style"}:
            raise ValueError(f"{svg.slug}: unsupported element {tag}")
        if tag == "text" and float(node.get("font-size", 0)) < 24:
            raise ValueError(f"{svg.slug}: text is smaller than 24 px")
        for key, value in node.attrib.items():
            if key.endswith("href") or "url(" in value and not value.startswith("url(#"):
                raise ValueError(f"{svg.slug}: external resource")
    if svg.slug == "lidar-sectors":
        bins = [node for node in svg.root.iter() if "data-sector" in node.attrib]
        if len(bins) != 12:
            raise ValueError("The lidar diagram must contain exactly 12 bins")
        for i, node in enumerate(bins):
            if (node.get("data-sector"), node.get("data-start-deg"), node.get("data-end-deg")) != (
                str(i), str(i * 30), str((i + 1) * 30),
            ):
                raise ValueError("Incorrect lidar bin ordering")
    if svg.slug == "sim-arena":
        ids = [node.get("id", "") for node in svg.root.iter()]
        if sum(i.startswith("box-") for i in ids) != 8 or sum(i.startswith("wall-") for i in ids) != 4:
            raise ValueError("The arena requires eight boxes and four walls")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg-only", action="store_true", help="Skip the PNG export")
    args = parser.parse_args()
    converter = shutil.which("rsvg-convert")
    if not args.svg_only and converter is None:
        parser.error("rsvg-convert is required for PNG export; no dependencies are installed automatically")
    source_contract()
    figures = [factory() for factory in (
        physical_ai_loop, lidar_sectors, sim_to_real, deployment_stages, sim_arena,
    )]
    for figure in figures:
        validate(figure)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="physical-ai-visuals-") as cache:
        env = {**os.environ, "XDG_CACHE_HOME": cache}
        for figure in figures:
            svg_path = OUTPUT / f"{figure.slug}.svg"
            figure.save(svg_path)
            if not args.svg_only:
                png_path = svg_path.with_suffix(".png")
                subprocess.run(
                    [converter, "--format=png", "--output", str(png_path), str(svg_path)],
                    check=True, env=env,
                )
                header = png_path.read_bytes()[:24]
                if header[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", header[16:24]) != (1200, figure.height):
                    raise ValueError(f"{png_path}: unexpected PNG dimensions")
            print(f"{figure.slug}: 1200 × {figure.height} · SVG" + ("" if args.svg_only else " + PNG"))


if __name__ == "__main__":
    main()
