#!/usr/bin/env python3
"""Structural checks plus real Chromium interaction/offline/fallback checks.
Run with a Python environment that already has Playwright and Chromium installed.
No server is started; all browser checks use file:// or sandboxed srcdoc.
"""
from pathlib import Path
import json
import argparse
import re
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
OUT=args.output
OUT.mkdir(parents=True,exist_ok=True)
html=(ROOT/'static/visuals/joint-concepts-3d.html').read_text()
results=[]
def check(name,condition,detail=None):
    if not condition:raise AssertionError(name+': '+str(detail))
    results.append({'check':name,'result':'PASS',**({'detail':detail} if detail is not None else {})})

for filename in ['learning-loop.svg','sim-to-real-gates.svg','observation-action.svg','biped-poster.svg','aws-architecture.svg']:
    content=(ROOT/'static/images'/filename).read_text()
    svg=ET.fromstring(content)
    check(filename+' is parseable SVG',svg.tag.endswith('svg'))
    check(filename+' contains no remote image',not re.search(r'(?:href|src)=["\']https?://',content))
check('No replacement glyphs in owned sources',not any('\ufffd' in p.read_text() for p in (ROOT/'scripts/visuals').glob('*') if p.suffix in ['.mjs','.html','.py']))
check('Standalone inline CSS and JavaScript',html.count('<script>')==1 and html.count('<style>')==1 and not re.search(r'<(?:script|link|iframe|img)[^>]+(?:src|href)=',html))
check('No runtime network or parent navigation APIs',not re.search(r'\bfetch\s*\(|XMLHttpRequest|WebSocket|window\.(?:parent|top|location)|postMessage|location\.(?:assign|replace)|<a\b',html))
check('Explicit conceptual limitations',all(t in html for t in ['임의의 비검증 치수','정확한 동역학','정책 재생','실제 Microduck']))
root=ET.parse(ROOT/'static/images/aws-architecture.drawio')
cells={e.get('id'):e for e in root.findall('.//mxCell')}
check('One VPC, AZ, public subnet and GPU instance',all(x in cells for x in ['vpc','az_0','subnet_0_0','gpu_0']) and len([x for x in cells if x.startswith('subnet_')])==1)
check('GPU is inside public subnet',cells['gpu_0'].get('parent')=='subnet_0_0')
check('No cloud-to-motor edge',all(c.get('source')=='operator' for c in cells.values() if c.get('target')=='runtime'))
check('S3 outside the VPC',cells['s3'].get('parent') not in ['vpc','az_0','subnet_0_0'])
check('Exactly six meaningful architecture edges',len([e for e in cells.values() if e.get('edge')=='1'])==6)

with sync_playwright() as pw:
    browser=pw.chromium.launch()
    try:
        ctx=browser.new_context(viewport={'width':1380,'height':1180},offline=True,reduced_motion='reduce',device_scale_factor=1)
        page=ctx.new_page();errors=[];net=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:net.append(req.url) if req.url.startswith(('http:','https:','ws:','wss:')) else None)
        page.add_init_script('window.__rafCalls=0;const oldRAF=window.requestAnimationFrame;window.requestAnimationFrame=function(...a){window.__rafCalls++;return oldRAF.apply(this,a)};')
        page.goto((ROOT/'static/visuals/joint-concepts-3d.html').as_uri(),wait_until='load')
        page.wait_for_function("document.querySelector('#scene').width>0 && !document.querySelector('#scene').hidden")
        check('Canvas enabled, six native sliders',page.locator('#scene').is_visible() and page.locator('input[type=range]').count()==6)
        check('All sliders labelled',page.locator('input[type=range]').evaluate_all('(els)=>els.every(e=>document.querySelector(`label[for="${e.id}"]`))'))
        check('Initial canvas has rendered pixels',page.locator('#scene').evaluate('(c)=>c.getContext("2d").getImageData(c.width/2,c.height/2,1,1).data[3]')==255)
        before=page.locator('#scene').evaluate('(c)=>c.toDataURL()')
        page.locator('#leftKnee').focus();page.keyboard.press('ArrowRight')
        check('Keyboard changes joint angle',page.locator('#leftKnee').input_value()=='17' and page.locator('#leftKnee-value').inner_text()=='17°')
        check('Joint change redraws geometry',page.locator('#scene').evaluate('(c)=>c.toDataURL()')!=before)
        page.locator('#reset').click()
        check('Reset restores default pose',page.locator('#leftKnee').input_value()=='16')
        page.locator('#scene').focus();page.keyboard.press('ArrowRight')
        check('Arrow key orbits camera',page.locator('#scene').evaluate('(c)=>c.toDataURL()')!=before)
        page.keyboard.press('Home')
        check('Home restores default camera',page.locator('#scene').evaluate('(c)=>c.toDataURL()')==before)
        b=page.locator('#scene').bounding_box()
        page.mouse.move(b['x']+b['width']*.55,b['y']+b['height']*.45);page.mouse.down();page.mouse.move(b['x']+b['width']*.65,b['y']+b['height']*.55,steps=5);page.mouse.up()
        check('Pointer drag orbits camera',page.locator('#scene').evaluate('(c)=>c.toDataURL()')!=before)
        page.locator('#front').click();front=page.locator('#scene').evaluate('(c)=>c.toDataURL()')
        page.locator('#side').click();check('View buttons change camera',page.locator('#scene').evaluate('(c)=>c.toDataURL()')!=front)
        page.locator('#zoom-in').click();check('Zoom button announces scale','110' in page.locator('#status').inner_text())
        page.locator('#pose-bend').click();check('Preset is a static pose',page.locator('#leftKnee').input_value()=='44')
        page.locator('#labels').uncheck();page.locator('#reset').click()
        check('Reset restores labels',page.locator('#labels').is_checked())
        check('Reduced motion: no animations or RAF loop',page.evaluate('matchMedia("(prefers-reduced-motion: reduce)").matches && document.getAnimations().length===0 && window.__rafCalls===0'))
        check('Desktop has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(OUT/'viewer-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_function('document.documentElement.scrollWidth<=innerWidth')
        check('390px mobile has no horizontal overflow',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        page.screenshot(path=str(OUT/'viewer-mobile.png'),full_page=True)
        check('No browser errors',not errors,errors)
        check('No network requests while offline',not net,net)
        ctx.close()
        # A realistic embedding context: opaque origin, only allow-scripts, no
        # same-origin, popups, forms, downloads, or parent-navigation capability.
        ctx=browser.new_context(viewport={'width':1380,'height':1180},offline=True)
        page=ctx.new_page();page.set_content('<iframe title="기하 개념 모형" sandbox="allow-scripts" style="width:100%;height:1000px;border:0"></iframe>')
        page.locator('iframe').evaluate('(e,content)=>e.srcdoc=content',html)
        frame=page.frame_locator('iframe')
        frame.locator('#scene').wait_for(state='visible')
        frame.locator('#pose-bend').click()
        check('sandbox=allow-scripts srcdoc works',frame.locator('#leftKnee').input_value()=='44')
        check('Embedding does not navigate parent',page.url=='about:blank')
        page.screenshot(path=str(OUT/'viewer-srcdoc.png'),full_page=True);ctx.close()
        for reason in ['no-javascript','no-canvas']:
            ctx=browser.new_context(java_script_enabled=reason!='no-javascript',offline=True,viewport={'width':1000,'height':1100})
            if reason=='no-canvas':ctx.add_init_script('HTMLCanvasElement.prototype.getContext=()=>null')
            page=ctx.new_page();page.goto((ROOT/'static/visuals/joint-concepts-3d.html').as_uri())
            check(reason+' static fallback visible',page.locator('#fallback').is_visible() and not page.locator('#scene').is_visible())
            check(reason+' controls remain disabled',page.locator('#leftKnee').is_disabled() and page.locator('#reset').is_disabled())
            if reason=='no-canvas':page.screenshot(path=str(OUT/'viewer-fallback.png'),full_page=True)
            ctx.close()
    finally:browser.close()
report={'checks':len(results),'passed':len(results),'results':results,'scope':'Visual structure and Chromium browser behavior; not robotics, dynamics, training or deployment validation.'}
(OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({"status":"PASS","checks":len(results),"output":str(OUT)},ensure_ascii=False))
