#!/usr/bin/env python3
"""Build a self-contained Korean handbook plus static/GitBook staging."""
from __future__ import annotations
import base64
from datetime import date
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
from datetime import datetime, timezone
from package_workshop import source_files, write_stage_inventory
import sys

import markdown
from markdown.extensions.toc import slugify_unicode
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENE = 'static/visuals/biped-3d.html'
CONCEPT_SCENE = 'static/visuals/joint-concepts-3d.html'


def read_page(path):
    text = path.read_text()
    meta = {}
    match = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if match:
        meta = yaml.safe_load(match[1])
        text = text[match.end():]
    title = meta.get('title') or re.search(r'^# (.+)$', text, re.M)[1]
    return {'path': path, 'text': text, 'title': title, 'weight': meta.get('weight', 1000),
            'id': re.sub(r'[^a-zA-Z0-9-]', '-', str(path.relative_to(ROOT)))}


def pages():
    main = sorted((read_page(p) for p in (ROOT/'content').rglob('*.ko.md')), key=lambda p:p['weight'])
    docs = sorted((read_page(p) for p in (ROOT/'docs').glob('*.md')), key=lambda p:p['title'])
    return main + docs


def render(page, by_path):
    page_id = page['id']
    markup = markdown.markdown(page['text'], extensions=['fenced_code','tables','sane_lists','toc'],
        extension_configs={'toc': {'slugify': lambda value, sep: page_id + '--' + slugify_unicode(value, sep)}})
    def link(m):
        url = html.unescape(m[1])
        if url.startswith(('https://','http://','mailto:','#')):
            return m[0]
        path_text, _, fragment = url.partition('#')
        target = (ROOT / path_text.lstrip('/') if path_text.startswith('/') else page['path'].parent/path_text).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError(f'Link escapes workshop: {url}')
        if target in by_path:
            new = '#' + by_path[target]['id']
            if fragment:
                new += '--' + fragment
        else:
            if not target.exists():
                raise FileNotFoundError(f'{page["path"]}: {url}')
            new = target.relative_to(ROOT).as_posix() + ('#'+fragment if fragment else '')
        return 'href="' + html.escape(new, quote=True) + '"'
    markup = re.sub(r'href="([^"]+)"', link, markup)
    def figure(m):
        tag = m[1]
        src = html.unescape(re.search(r'src="([^"]+)"',tag)[1])
        alt_match = re.search(r'alt="([^"]*)"',tag)
        alt = html.unescape(alt_match[1]) if alt_match else ''
        image_path = (page['path'].parent/src).resolve()
        if not image_path.is_relative_to(ROOT/'static/images'):
            raise ValueError(f'Only original local workshop images can be embedded: {src}')
        mime = {'.svg':'image/svg+xml','.png':'image/png'}[image_path.suffix]
        uri = 'data:' + mime + ';base64,' + base64.b64encode(image_path.read_bytes()).decode()
        return f'<figure><button class="zoom" aria-label="{html.escape(alt,quote=True)} 확대"><img src="{uri}" alt="{html.escape(alt,quote=True)}" loading="lazy"></button><figcaption>{html.escape(alt)}</figcaption></figure>'
    markup = re.sub(r'<p>(<img\b[^>]+>)</p>',figure,markup)
    markup = re.sub(r'<(/?)h([1-5])(\b[^>]*)>',lambda m:f'<{m[1]}h{int(m[2])+1}{m[3]}>',markup)
    return markup

STYLE = r'''
:root{--ink:#123d38;--muted:#536865;--paper:#f4f5ef;--yellow:#f2ce55;--line:#d4ded6;--white:#fff;--code:#112b29;--focus:#0a78ae;color-scheme:light}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:#183b36;font:16px/1.8 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR",sans-serif}a{color:#0a6b66;text-underline-offset:4px}button,input{font:inherit}button{cursor:pointer}.skip{position:fixed;top:-80px;z-index:50;background:white;padding:10px}.skip:focus{top:0}:focus-visible{outline:3px solid var(--focus);outline-offset:4px}aside{position:fixed;inset:0 auto 0 0;width:280px;background:var(--ink);color:#e9f1eb;padding:35px 22px;overflow:auto}aside .brand{font-size:25px;line-height:1.25;font-weight:780;letter-spacing:-1px}aside .tiny{color:#b4cec2;font-size:12px;letter-spacing:1.3px}aside p{font-size:13px;color:#c7d8cc}aside a{color:#e3eee7;text-decoration:none;display:block;padding:8px 12px;font-size:13px;border-left:2px solid transparent;border-radius:4px}aside a:hover,aside a.active{background:#23534c;border-color:var(--yellow)}aside input{width:100%;padding:9px 12px;margin:15px 0;background:#214e47;border:1px solid #5a7b69;border-radius:6px;color:#fff}aside input::placeholder{color:#bdd0c4}.nav-label{font-size:11px;letter-spacing:1.5px;color:#abc4b3;margin:24px 12px 7px}main{margin-left:280px;max-width:1330px;padding:38px 50px 80px}.eyebrow{font-size:12px;letter-spacing:2px;font-weight:750;color:#50776b}.hero{position:relative;background:#e4ede1;border:1px solid #c8d8ca;border-radius:22px;padding:45px;margin-bottom:32px;overflow:hidden}.hero>*{position:relative;z-index:1}.hero:after{z-index:0;content:"";position:absolute;width:220px;height:220px;border:38px solid #ccd9a8;border-radius:50%;right:-85px;top:-100px;pointer-events:none;opacity:.6}.hero h1{font-size:clamp(34px,4.7vw,64px);line-height:1.1;letter-spacing:-2.2px;margin:16px 0 24px;max-width:710px}.hero .lead{max-width:680px;font-size:18px}.pills{display:flex;flex-wrap:wrap;gap:8px;margin:25px 0}.pill{background:#fff9;border:1px solid #c0d2c0;border-radius:20px;padding:4px 13px;font-size:12px}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px}.actions a{padding:11px 17px;border-radius:7px;text-decoration:none;background:var(--ink);color:white;font-weight:650}.actions .secondary{background:var(--yellow);color:var(--ink)}.flow-strip{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #b9cdb8;margin-top:35px;padding-top:22px;gap:15px}.flow-strip small{display:block;color:#5b7967;font-size:11px;letter-spacing:1px}.flow-strip b{font-size:14px}.notice{font-size:13px;background:#fff8dd;border-left:4px solid #d5b347;padding:14px 18px;margin:22px 0;border-radius:0 7px 7px 0}article{background:white;border:1px solid var(--line);border-radius:15px;padding:34px 40px;margin:24px 0;box-shadow:0 3px 14px #0f3b2504;overflow:hidden}article h2{font-size:28px;line-height:1.45;letter-spacing:-.7px;margin:9px 0 25px}article h3{font-size:21px;line-height:1.55;margin-top:34px;border-top:1px solid #e8eee6;padding-top:25px}article h4{font-size:17px;margin:22px 0 12px}.chapter-top{display:flex;align-items:center;justify-content:space-between;gap:15px}.chapter-top span{font-size:11px;letter-spacing:1.4px;color:#6c8070}.done{font-size:12px;border:1px solid #c4d7c3;background:#f0f6ec;padding:4px 10px;border-radius:5px;color:var(--ink)}.done[aria-pressed=true]{background:var(--ink);color:white}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;margin:22px 0;font-size:14px}th{background:#edf4e9;text-align:left;color:#315744}td,th{border-bottom:1px solid #dce5d8;padding:11px 13px;vertical-align:top}code{font:13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;background:#edf2e9;border-radius:4px;padding:2px 5px;overflow-wrap:anywhere}pre{background:var(--code);color:#e6f5e9;overflow:auto;padding:22px 20px;border-radius:8px;font-size:13px;line-height:1.7;position:relative}pre code{background:none;padding:0;white-space:pre;color:inherit;overflow-wrap:normal}.code-wrap{position:relative;margin:24px 0}.copy{position:absolute;right:8px;top:8px;z-index:1;background:#2e5751;color:#e4eee4;border:1px solid #648575;border-radius:5px;font-size:11px;padding:3px 8px}.code-wrap pre{padding-top:41px}figure{margin:28px 0;background:#f8faf5;border:1px solid #e2e9dc;border-radius:12px;padding:10px}.zoom{display:block;width:100%;background:transparent;border:0;padding:0}.zoom img{width:100%;height:auto;display:block;max-height:630px;object-fit:contain}figcaption{font-size:12px;color:#62736c;padding:8px 12px 4px}blockquote{border-left:4px solid var(--yellow);margin:20px 0;padding:4px 20px;background:#fffcef}li{margin:6px 0}hr{border:0;border-top:1px solid var(--line);margin:35px 0}footer{font-size:12px;color:#6b7d70;padding:20px 4px}dialog{border:1px solid #a9beaa;border-radius:12px;padding:0;width:min(1200px,95vw);max-width:95vw;background:#fff}dialog::backdrop{background:#071b19b8}.dialog-bar{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:#f2f6ee;border-bottom:1px solid #d3dfd0}.dialog-bar button{border:1px solid #c2cec0;background:white;border-radius:6px;padding:5px 12px}.dialog-body{overflow:auto;max-height:82vh;padding:12px}.dialog-body img{display:block;width:100%;height:auto}.dialog-body iframe{width:100%;height:76vh;border:0}#mobile-toggle{display:none}.hidden{display:none!important}
@media(min-width:1700px){main{margin-left:calc(280px + (100vw - 1700px)/2)}}@media(max-width:1050px){aside{width:230px}main{margin-left:230px;padding:25px}.hero{padding:30px}article{padding:28px}.hero h1{font-size:43px}}@media(max-width:760px){aside{position:relative;width:auto;padding:20px}aside .brand{font-size:22px}aside nav,aside input,aside .nav-label,aside .side-note{display:none}aside.open nav,aside.open input,aside.open .nav-label{display:block}#mobile-toggle{display:block;position:absolute;right:20px;top:20px;background:#f2ce55;border:0;border-radius:5px;padding:6px 10px;font-size:12px}main{margin-left:0;padding:18px 12px 40px}.hero{padding:25px 20px;border-radius:12px}.hero h1{font-size:37px}.hero .lead{font-size:16px}.flow-strip{grid-template-columns:repeat(2,1fr)}article{padding:24px 18px;border-radius:10px}article h2{font-size:24px}table{font-size:12px}td,th{padding:9px}.actions a{font-size:13px}pre{font-size:12px}figure{margin-left:-8px;margin-right:-8px}.dialog-body{padding:0}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{aside,.actions,.done,.copy,dialog{display:none!important}main{margin:0;padding:0;max-width:none}.hero,article{break-inside:avoid;border:0;box-shadow:none}pre{white-space:pre-wrap}pre code{white-space:pre-wrap}body{font-size:11pt}article{padding:10px 0}a{color:inherit}}
'''
SCRIPT = r'''
const navLinks=[...document.querySelectorAll('nav a')];
document.getElementById('search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();navLinks.forEach(a=>a.classList.toggle('hidden',!a.textContent.toLowerCase().includes(q)))});
document.getElementById('mobile-toggle').addEventListener('click',()=>{const side=document.querySelector('aside');side.classList.toggle('open');document.getElementById('mobile-toggle').setAttribute('aria-expanded',side.classList.contains('open'))});
navLinks.forEach(a=>a.addEventListener('click',()=>document.querySelector('aside').classList.remove('open')));
const obs=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){navLinks.forEach(a=>a.classList.toggle('active',a.hash==='#'+e.target.id))}})},{rootMargin:'-10% 0px -65% 0px'});document.querySelectorAll('article').forEach(a=>obs.observe(a));
document.querySelectorAll('pre').forEach(pre=>{const wrap=document.createElement('div');wrap.className='code-wrap';pre.replaceWith(wrap);wrap.append(pre);const b=document.createElement('button');b.type='button';b.className='copy';b.textContent='명령 복사';wrap.append(b);b.onclick=async()=>{try{await navigator.clipboard.writeText(pre.querySelector('code')?.textContent||pre.textContent);b.textContent='복사됨'}catch{const range=document.createRange();range.selectNodeContents(pre);const sel=getSelection();sel.removeAllRanges();sel.addRange(range);b.textContent='선택됨 · Ctrl/Cmd+C'}setTimeout(()=>b.textContent='명령 복사',1600)}});
document.querySelectorAll('table').forEach(table=>{const wrap=document.createElement('div');wrap.className='table-wrap';table.replaceWith(wrap);wrap.append(table)});
let saved={};try{saved=JSON.parse(localStorage.getItem('microduck-workshop-progress')||'{}')}catch{};document.querySelectorAll('.done').forEach(b=>{const id=b.dataset.page;b.setAttribute('aria-pressed',!!saved[id]);b.textContent=saved[id]?'읽음 ✓':'읽음 표시';b.onclick=()=>{saved[id]=!saved[id];b.setAttribute('aria-pressed',saved[id]);b.textContent=saved[id]?'읽음 ✓':'읽음 표시';try{localStorage.setItem('microduck-workshop-progress',JSON.stringify(saved))}catch{}}});
let disposeSimulator = null;
const dialog=document.getElementById('viewer'),body=dialog.querySelector('.dialog-body'),caption=document.getElementById('viewer-title');document.getElementById('close-viewer').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});dialog.addEventListener('close',()=>{if(disposeSimulator){disposeSimulator();disposeSimulator=null}body.replaceChildren()});
document.querySelectorAll('.zoom').forEach(b=>b.onclick=()=>{const img=b.querySelector('img');caption.textContent=img.alt;body.replaceChildren(img.cloneNode(true));dialog.showModal()});
document.querySelectorAll('a[href="static/visuals/biped-3d.html"]').forEach(a=>a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();caption.textContent='공식 Microduck 시뮬레이터 · 온라인';dialog.showModal();disposeSimulator=mountMicroduck(body,{autoStart:true})}));
document.querySelectorAll('a[href="static/visuals/joint-concepts-3d.html"]').forEach(a=>a.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();caption.textContent='관절을 움직이며 이해하기 · 오프라인 개념 뷰어';const frame=document.createElement('iframe');frame.title='관절을 움직이며 이해하기';frame.setAttribute('sandbox','allow-scripts');frame.srcdoc=JSON.parse(document.getElementById('concept-scene-data').textContent);body.replaceChildren(frame);dialog.showModal()}));


'''


def build():
    all_pages=pages(); by_path={p['path'].resolve():p for p in all_pages}
    nav=[]; articles=[]
    for p in all_pages:
        nav.append(f'<a href="#{p["id"]}">{html.escape(p["title"])}</a>')
        kind='LESSON' if p['path'].is_relative_to(ROOT/'content') else 'REFERENCE'
        articles.append(f'<article id="{p["id"]}"><div class="chapter-top"><span>{kind} / MICRODUCK</span><button class="done" data-page="{p["id"]}" aria-pressed="false">읽음 표시</button></div>{render(p,by_path)}</article>')
    embed_script=re.sub(r'^export ', '', (ROOT/'scripts/visuals/microduck-embed.mjs').read_text(), flags=re.M)
    embed_style=(ROOT/'scripts/visuals/microduck-embed.css').read_text()
    concept_json=json.dumps((ROOT/CONCEPT_SCENE).read_text(),ensure_ascii=False).replace('<','\\u003c')
    doc='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="AWS GPU에서 Microduck 시뮬레이션과 강화학습, ONNX 검증, 실제 로봇 배포까지 배우는 한국어 워크샵"><title>Physical AI: From Cloud to Robot · Microduck</title><style>'''+STYLE+embed_style+'''</style></head><body><a class="skip" href="#main">본문으로 이동</a><aside><div class="tiny">HANDS-ON WORKSHOP / 01</div><div class="brand">Physical AI<br>from cloud<br>to robot.</div><p>Microduck · MuJoCo · AWS</p><button id="mobile-toggle" aria-expanded="false" aria-controls="navigation">목차</button><label class="nav-label" for="search">YOUR LEARNING PATH</label><input id="search" type="search" placeholder="목차 검색" aria-label="목차 검색"><nav id="navigation" aria-label="워크샵 목차">'''+''.join(nav)+'''</nav><p class="side-note">교재·관절 개념 뷰어는 오프라인에서도 열립니다.<br>공식 3D 시뮬레이터는 인터넷이 필요합니다.<br>실제 실습에는 별도 환경과 이용 권한이 필요합니다.</p></aside><main id="main"><header class="hero"><div class="eyebrow">CLOUD COMPUTE. REAL MOVEMENT.</div><h1>가상에서 연습하고,<br>현실로 한 걸음.</h1><p class="lead">AWS에서 작은 이족 로봇의 보행을 학습하고,<br>검증한 모델을 실제 Microduck으로 옮기는 여정.</p><div class="pills"><span class="pill">한국어 · 단계별 실습</span><span class="pill">AWS GPU + MuJoCo</span><span class="pill">PPO → ONNX → Robot</span></div><div class="actions"><a href="#content-module1-concepts-index-ko-md">첫 단계 시작</a><a class="secondary" href="static/visuals/biped-3d.html">공식 Microduck 3D 실행 ↗</a></div><div class="flow-strip"><div><small>01 / SIMULATE</small><b>가상 로봇을 만나다</b></div><div><small>02 / LEARN</small><b>움직임을 학습하다</b></div><div><small>03 / VERIFY</small><b>증거로 확인하다</b></div><div><small>04 / DEPLOY</small><b>실제 로봇으로 옮기다</b></div></div></header><div class="notice"><strong>실습 전 확인</strong> · 공식 3D 모델은 CC BY-SA-NC 조건입니다. 교재의 그림은 자체 제작이며, 3D 체험은 공식 외부 시뮬레이터를 연결합니다. 로봇 자산은 배포본에 포함하지 않습니다. 실제 자산 이용 권한과 각 단계의 검증 상태를 확인하고 시작하세요.</div>'''+''.join(articles)+'''<footer>자료 기준 2026-09-10 · 자체 제작 교육 자료 · Pollen Robotics 또는 AWS의 공식 인증/승인을 의미하지 않습니다.<br>교재의 읽음 표시는 학습 진행 기록이며, 실행 검증이나 실물 시험 승인을 뜻하지 않습니다.</footer></main><dialog id="viewer" aria-labelledby="viewer-title"><div class="dialog-bar"><strong id="viewer-title">그림 보기</strong><button id="close-viewer" autofocus>닫기 ×</button></div><div class="dialog-body"></div></dialog><script type="application/json" id="concept-scene-data">'''+concept_json+'''</script><script>'''+embed_script+SCRIPT+'''</script></body></html>'''
    (ROOT/'index.html').write_text(doc)
    # Publish from one validated byte inventory into fresh directories. Old outputs
    # are moved to ignored history, never merged into a new release.
    payloads={p.relative_to(ROOT).as_posix():p.read_bytes() for p in source_files()}
    site_payloads={**payloads, '.nojekyll':b''}
    book_payloads=dict(payloads)
    summary=['# Summary','']
    for p in all_pages:
        relative=p['path'].relative_to(ROOT).as_posix()
        book_payloads[relative]=p['text'].encode()
        summary.append(f'- [{p["title"]}]({relative})')
    book_payloads['SUMMARY.md']=('\n'.join(summary)+'\n').encode()
    book_payloads['README.md']='# Physical AI: From Cloud to Robot\n\n[교재 시작](content/index.ko.md)\n'.encode()
    build_root=ROOT/'artifacts'/'build'
    build_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='staging-',dir=build_root) as scratch:
        pending=Path(scratch)
        for name,data in [('_site',site_payloads),('_gitbook',book_payloads)]:
            destination=pending/name;destination.mkdir()
            write_stage_inventory(destination,data)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        for name in ['_site','_gitbook']:
            destination=ROOT/name
            if destination.is_symlink():
                raise ValueError(f'Refusing symlink output: {destination}')
            if destination.exists():
                history=ROOT/'artifacts'/'build-history'/stamp
                history.mkdir(parents=True,exist_ok=True)
                destination.rename(history/name)
            (pending/name).rename(destination)
    report={'pages':len(all_pages),'html_bytes':len(doc.encode()),'simulator_launcher':SCENE,'concept_viewer':CONCEPT_SCENE,'external_publish':False}
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    build()
