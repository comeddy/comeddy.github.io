#!/usr/bin/env python3
"""Build the workshop's offline handbook using only the Python standard library."""
import html
import base64
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIRECTIVE = re.compile(r'^:image\[([^\]]+)\]\{src="([^"]+)"(?: width=(\d+))?\}$')
IMAGES_USED = set()
SCENE_PATH = "static/visuals/arena-3d.html"


def metadata(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if match:
        title = re.search(r'^title:\s*"?([^"\n]+)"?$', match[1], re.M)
        weight = re.search(r"^weight:\s*(\d+)", match[1], re.M)
        return title[1], int(weight[1]) if weight else 100, text[match.end():]
    title = re.search(r"^# (.+)", text, re.M)
    return title[1] if title else path.stem, 1000, text


def anchor(path):
    return "page-" + re.sub(r"[^a-zA-Z0-9-]", "-", str(path.relative_to(ROOT)))


def inline(text, source):
    tokens = []

    def keep(value):
        tokens.append(value)
        return f"\x00{len(tokens) - 1}\x00"

    def link(match):
        label, target = match.groups()
        if not re.match(r"^(https?://|mailto:|#)", target):
            path = (source.parent / target.split("#")[0]).resolve()
            target = "#" + anchor(path) if path in PAGES else str(path.relative_to(ROOT))
        external = ' target="_blank" rel="noopener noreferrer"' if target.startswith("http") else ""
        scene = ' class="scene-open" aria-haspopup="dialog"' if target == SCENE_PATH else ""
        return keep(f'<a href="{html.escape(target, quote=True)}"{external}{scene}>{html.escape(label)}</a>')

    text = re.sub(r"`([^`]+)`", lambda m: keep("<code>" + html.escape(m[1]) + "</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: tokens[int(m[1])], text)


def image_figure(match, source):
    alt, target, _ = match.groups()
    path = (ROOT / target.lstrip("/") if target.startswith("/static/") else source.parent / target).resolve()
    if not path.is_relative_to(ROOT / "static" / "images") or path.suffix.lower() != ".png":
        raise ValueError(f"Expected a local PNG in static/images: {target}")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Invalid PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    encoded = base64.b64encode(data).decode("ascii")
    description = html.escape(alt, quote=True)
    IMAGES_USED.add(path.relative_to(ROOT).as_posix())
    return (
        '<figure class="workshop-figure">'
        f'<button class="figure-zoom" type="button" aria-label="{description} — 확대해서 보기">'
        f'<img src="data:image/png;base64,{encoded}" alt="{description}" '
        f'width="{width}" height="{height}" loading="lazy" decoding="async">'
        '</button>'
        f'<figcaption>{html.escape(alt)} <span>그림을 누르면 크게 볼 수 있습니다.</span></figcaption>'
        '</figure>'
    )


def render(text, source):
    lines = text.splitlines()
    output, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        image = IMAGE_DIRECTIVE.fullmatch(line)
        if image:
            output.append(image_figure(image, source))
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            if language == "mermaid":
                output.append('<div class="flow" role="img" aria-label="AWS 가상 공간에서 데이터를 수집하고 모델을 학습하여 실제 로봇에 배포합니다">'
                              '<div><small>01 / SIMULATE</small><b>AWS 가상 로봇</b><span>Isaac Sim · GPU</span></div>'
                              '<i aria-hidden="true">→</i><div><small>02 / LEARN</small><b>내가 만든 AI</b><span>데이터 · 학습 · 검증</span></div>'
                              '<i aria-hidden="true">→</i><div><small>03 / DEPLOY</small><b>실제 로봇</b><span>센서 · 판단 · 바퀴</span></div></div>')
            else:
                output.append('<div class="codebox"><div class="codebar"><span>' +
                              html.escape(language or "text") +
                              '</span><button class="copy" type="button">복사</button></div><pre><code>' +
                              html.escape("\n".join(block)) + "</code></pre></div>")
            index += 1
            continue
        heading = re.match(r"^(#{1,6}) (.+)", line)
        if heading:
            level = min(len(heading[1]) + 1, 6)
            output.append(f"<h{level}>{inline(heading[2], source)}</h{level}>")
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[: -]+", cell) for cell in row):
                    rows.append(row)
                index += 1
            table = '<div class="tablewrap"><table><thead><tr>'
            table += "".join("<th>" + inline(cell, source) + "</th>" for cell in rows[0])
            table += "</tr></thead><tbody>"
            for row in rows[1:]:
                table += "<tr>" + "".join("<td>" + inline(cell, source) + "</td>" for cell in row) + "</tr>"
            output.append(table + "</tbody></table></div>")
            continue
        if re.match(r"^(- |\d+\. )", line):
            ordered = bool(re.match(r"^\d+\.", line))
            tag = "ol" if ordered else "ul"
            output.append("<" + tag + ">")
            pattern = r"^\d+\. (.*)" if ordered else r"^- (.*)"
            while index < len(lines) and (match := re.match(pattern, lines[index])):
                item = match[1]
                index += 1
                while index < len(lines) and lines[index].startswith("  ") and lines[index].strip():
                    item += " " + lines[index].strip()
                    index += 1
                output.append("<li>" + inline(item, source) + "</li>")
            output.append("</" + tag + ">")
            continue
        if line.startswith("> "):
            output.append('<aside class="note">' + inline(line[2:], source) + "</aside>")
            index += 1
            continue
        paragraph = [line]
        index += 1
        while index < len(lines) and lines[index].strip() and not re.match(r"^(#|```|\||- |\d+\. |> |:image\[)", lines[index]):
            paragraph.append(lines[index])
            index += 1
        output.append("<p>" + inline(" ".join(paragraph), source) + "</p>")
    return "\n".join(output)


PAGES = sorted(ROOT.glob("content/**/index.ko.md"), key=lambda p: metadata(p)[1])
PAGES += [ROOT / "docs" / name for name in
          ("device-setup.md", "hardware-options.md", "facilitator.md", "sources.md", "verification.md")]
PAGES = [path.resolve() for path in PAGES if path.exists()]

STYLE = """
:root{--ink:#15283a;--muted:#506579;--line:#dae3eb;--accent:#075bcb;--paper:#fff;--bg:#f3f6fa}
*{box-sizing:border-box}[hidden]{display:none!important}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;font:16px/1.8 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif;color:var(--ink);background:var(--bg)}
a{color:var(--accent);text-underline-offset:3px}button,input{font:inherit}
.sidebar{position:fixed;inset:0 auto 0 0;width:286px;padding:32px 22px;background:#12283c;color:#d6e2f0;overflow:auto}
.brand{font-size:22px;line-height:1.35;font-weight:750;color:#fff;margin-bottom:12px}.eyebrow{font-size:11px;letter-spacing:2px;color:#8ac9ee;font-weight:700}
.sidebar p{font-size:13px;color:#afc3d7}.sidebar input[type=search]{width:100%;border:1px solid #496074;background:#203a50;color:#fff;border-radius:8px;padding:8px 10px;margin:12px 0}
.sidebar input::placeholder{color:#bad0e2}.sidebar a{display:block;color:#d6e2f0;text-decoration:none;font-size:14px;line-height:1.5;padding:9px 10px;border-radius:6px;margin:2px 0}
.sidebar a:hover,.sidebar a:focus{background:#284b67;color:#fff}.sidebar a.done::after{content:" ✓";color:#76e5b2}
main{max-width:1370px;margin-left:286px;padding:48px 6vw 80px}.hero{padding-bottom:25px}
h1{font-size:clamp(28px,4vw,48px);line-height:1.23;letter-spacing:-1.4px;margin:12px 0 20px}
.lead{font-size:19px;max-width:750px;color:var(--muted)}.chips{display:flex;flex-wrap:wrap;gap:8px}
.hero-actions{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
.hero-actions a{display:inline-block;padding:10px 16px;border:1px solid var(--accent);border-radius:8px;text-decoration:none;font-weight:700}
.hero-actions a:first-child{background:var(--accent);color:#fff}
.hero-actions a:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
.chip{background:#e2ecf7;border:1px solid #cfdfef;font-size:12px;font-weight:700;padding:4px 10px;border-radius:99px}
.chapter{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:34px 40px;margin:30px 0;box-shadow:0 8px 26px #18334805}
.chapter h2{font-size:29px;line-height:1.35;letter-spacing:-.6px;margin:0 0 20px}.chapter h3{font-size:21px;margin:36px 0 12px}.chapter h4{font-size:18px;margin-top:28px}
p{margin:14px 0}li{margin:6px 0}code{background:#edf2f7;color:#25445f;border-radius:4px;padding:2px 5px;font-size:.88em}
.codebox{border:1px solid #314960;border-radius:10px;overflow:hidden;margin:20px 0;background:#14283a;color:#e5edf6}
.codebar{display:flex;justify-content:space-between;align-items:center;background:#20394e;padding:7px 14px;font-size:12px;color:#c0d1e2}
.copy{border:1px solid #597187;background:transparent;color:#fff;border-radius:4px;padding:2px 10px;font-size:12px;cursor:pointer}
pre{padding:18px;margin:0;overflow-x:auto;font-size:13px;line-height:1.65}pre code{background:none;color:inherit;padding:0;font-size:inherit}
.tablewrap{overflow:auto;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eef4f9;font-weight:700}
.flow{display:flex;gap:12px;align-items:center;margin:28px 0}.flow div{flex:1;background:#eff6fb;border:1px solid #cddfec;border-radius:10px;padding:18px 14px}
.flow small,.flow b,.flow span{display:block}.flow small{font-size:10px;color:#0c68a0;letter-spacing:1px}.flow b{font-size:17px;margin:8px 0}.flow span{font-size:12px;color:#506579}.flow i{color:#5a84a4;font-style:normal}
.note{background:#fff7df;border-left:4px solid #d4a328;padding:16px;margin:20px 0}
.workshop-figure{margin:28px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}
.figure-zoom{display:block;width:100%;padding:0;border:0;background:#fff;cursor:zoom-in}
.figure-zoom:focus-visible{outline:3px solid var(--accent);outline-offset:-3px}
.workshop-figure img{display:block;width:100%;height:auto}
.workshop-figure figcaption{padding:12px 16px;background:#f6f9fc;color:var(--muted);font-size:13px;line-height:1.6}
.workshop-figure figcaption span{display:block;font-size:12px;margin-top:3px}
.image-viewer{border:1px solid var(--line);border-radius:12px;padding:0;width:min(96vw,1680px);max-width:96vw;max-height:94vh}
.image-viewer::backdrop{background:#10283be0}.viewer-bar{position:sticky;top:0;display:flex;justify-content:space-between;gap:20px;align-items:center;background:#fff;padding:12px 18px;border-bottom:1px solid var(--line);z-index:1}
.viewer-bar p{margin:0;font-size:14px}.viewer-close{border:1px solid var(--line);border-radius:6px;background:#eef4f9;padding:4px 12px;white-space:nowrap;cursor:pointer}
.viewer-canvas{overflow:auto;max-height:calc(94vh - 76px);background:#fff}.viewer-canvas img{display:block;width:100%;height:auto;min-width:960px}
.scene-open{display:inline-block;padding:10px 16px;border-radius:8px;background:#075bcb;color:#fff;font-weight:700;text-decoration:none}
.scene-open:focus-visible{outline:3px solid #075bcb;outline-offset:3px}
.scene-viewer{height:92vh;max-height:92vh;width:min(96vw,1600px)}
.scene-viewer[open]{display:flex;flex-direction:column}.scene-viewer .viewer-bar{flex:none}
.scene-canvas{flex:1;min-height:0}.scene-canvas iframe{display:block;width:100%;height:100%;border:0;background:#eef3f8}
.check{border-top:1px solid var(--line);margin-top:30px;padding-top:18px;font-size:14px;color:var(--muted)}.check input{width:18px;height:18px;vertical-align:middle;accent-color:#087d63}
.footer{font-size:13px;color:var(--muted)}.skip{position:absolute;top:-60px;left:300px}.skip:focus{top:10px;background:#fff;padding:8px}
@media(max-width:1000px){main{padding:32px}.chapter{padding:25px}.sidebar{width:245px}main{margin-left:245px}.flow{flex-direction:column;align-items:stretch}.flow i{text-align:center;transform:rotate(90deg)}}
@media(max-width:700px){.sidebar{position:static;width:auto;padding:24px}.sidebar nav{max-height:210px;overflow:auto}.sidebar p{margin:8px 0}main{margin:0;padding:22px 14px}.chapter{padding:24px 18px;border-radius:10px}.chapter h2{font-size:25px}th,td{min-width:110px}.hero{padding:10px}}
@media print{.sidebar,.copy,.check,.skip,.image-viewer{display:none}main{margin:0;padding:0}.chapter{box-shadow:none;break-before:page;border:0;padding:0}pre{white-space:pre-wrap}body{background:#fff}.hero{break-after:page}a{color:inherit}.workshop-figure{break-inside:avoid}.workshop-figure figcaption span{display:none}}
"""
nav, chapters = [], []
for page in PAGES:
    title, _, body = metadata(page)
    page_id = anchor(page)
    nav.append(f'<a href="#{page_id}" data-title="{html.escape(title, quote=True)}">{html.escape(title)}</a>')
    chapters.append(f'<section class="chapter" id="{page_id}" aria-label="{html.escape(title, quote=True)}">' +
                    render(body, page) +
                    f'<div class="check"><label><input type="checkbox" data-page="{page_id}"> 이 단계를 읽고 완료 확인을 마쳤습니다</label></div></section>')

SCRIPT = """
const storeKey="physical-ai-workshop-v1";
let done={};try{done=JSON.parse(localStorage.getItem(storeKey)||"{}")}catch(e){}
function progress(){let count=0;document.querySelectorAll("[data-page]").forEach(x=>{x.checked=!!done[x.dataset.page];if(x.checked)count++;const a=document.querySelector('nav a[href="#'+x.dataset.page+'"]');if(a)a.classList.toggle("done",x.checked)});document.getElementById("progress").textContent=count+" / "+document.querySelectorAll("[data-page]").length+" 단계 확인"}
document.querySelectorAll("[data-page]").forEach(x=>x.addEventListener("change",()=>{done[x.dataset.page]=x.checked;try{localStorage.setItem(storeKey,JSON.stringify(done))}catch(e){}progress()}));progress();
document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.toLowerCase();document.querySelectorAll("nav a").forEach(a=>a.hidden=!a.dataset.title.toLowerCase().includes(q))});
document.querySelectorAll(".copy").forEach(button=>button.addEventListener("click",async()=>{const text=button.closest(".codebox").querySelector("pre").textContent;try{await navigator.clipboard.writeText(text);button.textContent="복사됨"}catch(e){const area=document.createElement("textarea");area.value=text;document.body.appendChild(area);area.select();const ok=document.execCommand("copy");area.remove();button.textContent=ok?"복사됨":"직접 선택해서 복사"}setTimeout(()=>button.textContent="복사",1800)}));
const viewer=document.getElementById("image-viewer");
document.querySelectorAll(".figure-zoom").forEach(button=>button.addEventListener("click",()=>{
  const image=button.querySelector("img"),large=viewer.querySelector("img");
  large.src=image.src;large.alt=image.alt;
  document.getElementById("viewer-caption").textContent=image.alt;
  viewer.showModal();
}));
document.getElementById("viewer-close").addEventListener("click",()=>viewer.close());
viewer.addEventListener("click",event=>{if(event.target===viewer)viewer.close()});
viewer.addEventListener("close",()=>viewer.querySelector("img").removeAttribute("src"));
const sceneViewer=document.getElementById("scene-viewer");
document.querySelectorAll(".scene-open").forEach(link=>link.addEventListener("click",event=>{
  if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  if(typeof sceneViewer.showModal!=="function")return;
  event.preventDefault();
  const frame=document.createElement("iframe");
  frame.title="가상 실습장 3D 둘러보기";
  frame.setAttribute("sandbox","allow-scripts");
  frame.srcdoc=JSON.parse(document.getElementById("scene-document").textContent);
  sceneViewer.querySelector(".scene-canvas").replaceChildren(frame);
  sceneViewer.showModal();
}));
document.getElementById("scene-close").addEventListener("click",()=>sceneViewer.close());
sceneViewer.addEventListener("click",event=>{if(event.target===sceneViewer)sceneViewer.close()});
sceneViewer.addEventListener("close",()=>sceneViewer.querySelector(".scene-canvas").replaceChildren());
window.addEventListener("message",event=>{
  const frame=sceneViewer.querySelector("iframe");
  if(frame&&event.source===frame.contentWindow&&event.data?.type==="physical-ai-scene-close")sceneViewer.close();
});
"""
# Escape '<' so the embedded document cannot terminate the JSON script element.
scene_json = json.dumps((ROOT / SCENE_PATH).read_text(encoding="utf-8"), ensure_ascii=False).replace("<", "\\u003c")
document = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Physical AI Workshop — Isaac Sim on AWS</title><meta name="description" content="AWS 가상 로봇에서 실제 TurtleBot3 배포까지, 한국어 초보자 실습 워크샵.">
<style>""" + STYLE + """</style></head><body><a class="skip" href="#main">본문으로 이동</a>
<aside class="sidebar"><div class="eyebrow">HANDS-ON WORKSHOP</div><div class="brand">Physical AI<br>from cloud to robot.</div>
<p>Isaac Sim on AWS<br>가상 실습장에서 실제 바퀴까지</p><label for="search" class="eyebrow">CONTENTS</label><input id="search" type="search" placeholder="목차 검색" aria-label="목차 검색">
<nav aria-label="워크샵 목차">""" + "".join(nav) + """</nav><p id="progress" aria-live="polite"></p><p>인터넷 없이 교재를 읽을 수 있습니다.<br>설치·AWS 실습에는 인터넷이 필요합니다.</p></aside>
<main id="main"><header class="hero"><div class="eyebrow" style="color:#086aa6">SIMULATE / LEARN / DEPLOY</div>
<h1>가상에서 배우고,<br>현실에서 움직입니다.</h1><p class="lead">AWS에서 내 첫 로봇 AI를 만들고 실제 디바이스에 배포하는 과정을, 작은 성공 단계로 따라가세요.</p>
<div class="chips"><span class="chip">한국어 · 초급</span><span class="chip">사전 준비 + 7시간</span><span class="chip">Isaac Sim 5.1.0</span><span class="chip">TurtleBot3 Burger</span></div>
<div class="hero-actions"><a href="https://comeddy.github.io/pai/issacsim/downloads/physical-ai-isaac-aws.zip">실습 코드 ZIP 받기</a><a href="https://github.com/comeddy/comeddy.github.io/tree/master/pai/issacsim" target="_blank" rel="noopener noreferrer">GitHub 소스 보기</a></div></header>""" + "".join(chapters) + """
<footer class="footer">자료 기준: 2026-09-09 · 실물 실행 전 검증 기록과 운영자 리허설을 확인하세요.</footer></main>
<dialog class="image-viewer" id="image-viewer" aria-labelledby="viewer-caption"><div class="viewer-bar"><p id="viewer-caption">그림 크게 보기</p><button class="viewer-close" id="viewer-close" type="button" autofocus>닫기 ×</button></div><div class="viewer-canvas"><img alt=""></div></dialog>
<dialog class="image-viewer scene-viewer" id="scene-viewer" aria-labelledby="scene-caption"><div class="viewer-bar"><p id="scene-caption">가상 실습장 · 3D 둘러보기</p><button class="viewer-close" id="scene-close" type="button" autofocus>닫기 ×</button></div><div class="scene-canvas"></div></dialog>
<script type="application/json" id="scene-document">""" + scene_json + "</script><script>" + SCRIPT + "</script></body></html>"
(ROOT / "index.html").write_text(document, encoding="utf-8")
print(json.dumps({"output": str(ROOT / "index.html"), "pages": len(PAGES), "images": len(IMAGES_USED), "bytes": len(document.encode())}, ensure_ascii=False))
