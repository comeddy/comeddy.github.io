#!/usr/bin/env python3
"""Optional real Chromium integration check; requires Playwright + Chromium."""
from pathlib import Path
import argparse
import json
import re
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

def verify_live(browser, output, check):
    ctx=browser.new_context(viewport={'width':1440,'height':1100})
    try:
        page=ctx.new_page(); errors=[]; requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto((ROOT/'index.html').as_uri())
        check('Online handbook does not preload provider',not requests)
        page.locator('a.secondary').click()
        iframe=page.locator('dialog iframe')
        check('Official host embedded directly',iframe.get_attribute('src')=='https://pollen-robotics-microduck-simulator.hf.space')
        check('Provider iframe has limited sandbox',iframe.get_attribute('sandbox')=='allow-scripts allow-same-origin allow-pointer-lock')
        frame=page.frame_locator('dialog iframe')
        frame.get_by_role('button',name='Waddle in').wait_for(timeout=60000)
        frame.get_by_role('button',name='Waddle in').click()
        frame.get_by_text(re.compile(r'FPS [1-9][0-9]*')).wait_for(timeout=60000)
        canvas=frame.locator('canvas').first
        canvas.wait_for(state='visible')
        check('Official WebGL canvas rendered',canvas.evaluate('(c)=>c.width>0&&c.height>0&&c.dataset.engine.startsWith("three.js")'))
        canvas.click(position={'x':180,'y':240})
        page.keyboard.down('ArrowUp')
        try:
            frame.get_by_text(re.compile(r'ODO (?:0\.[1-9]|[1-9][0-9]*\.)')).wait_for(timeout=15000)
        finally:
            page.keyboard.up('ArrowUp')
        check('Arrow key moves simulated robot','ODO 0.0M' not in frame.locator('body').inner_text())
        metrics=frame.locator('body').inner_text()
        page.screenshot(path=str(output/'official-simulator-running.png'))
        check('Official app has no JavaScript errors',not errors)
        check('Provider assets loaded from remote',any(u.startswith('https://pollen-robotics-microduck-simulator.hf.space/') for u in requests))
        page.locator('[data-sim-stop]').click()
        check('Stop removes external app',page.locator('dialog iframe').count()==0)
        page.locator('[data-sim-start]').click()
        check('Restart creates a fresh iframe',page.locator('dialog iframe').count()==1)
        page.locator('#close-viewer').click()
        page.locator('dialog iframe').wait_for(state='detached')
        check('Close detaches external browsing context',len(page.frames)==1)
        page.set_viewport_size({'width':390,'height':844});page.evaluate('scrollTo(0,0)')
        # Simulate unreachable hosting separately; this is fallback verification, not a live-app success.
        page.route('https://pollen-robotics-microduck-simulator.hf.space/**',lambda route:route.abort())
        page.locator('a.secondary').click()
        check('Mobile dialog has no horizontal overflow',page.locator('dialog').evaluate('(d)=>d.scrollWidth<=d.clientWidth'))
        check('Failed-host fallback link remains available',page.locator('dialog a[target="_blank"]').is_visible())
        page.screenshot(path=str(output/'handbook-mobile-simulator-fallback.png'))
        page.locator('#close-viewer').click()
        (output/'live-provider.json').write_text(json.dumps({'status':'PASS','observed_hud':metrics,'provider_request_count':len(requests),'page_errors':errors,'scope':'Browser demo loading and keyboard movement only; not workshop training or physical robot verification'},ensure_ascii=False,indent=2)+'\n')
    finally:
        ctx.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--live',action='store_true',help='Also exercise the real external app; requires internet')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        try:
            ctx=browser.new_context(viewport={'width':1440,'height':1000},offline=True,reduced_motion='reduce')
            page=ctx.new_page();errors=[];requests=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda req:requests.append(req.url) if req.url.startswith(('http:','https:')) else None)
            page.goto((ROOT/'index.html').as_uri());page.wait_for_selector('article')
            check('Korean document',page.locator('html').get_attribute('lang')=='ko')
            check('13 lessons plus references',page.locator('article').count()>=20)
            check('Commands have copy controls',page.locator('.copy').count()>=35)
            page.locator('.zoom img').evaluate_all('(imgs)=>imgs.forEach(i=>i.loading="eager")')
            page.wait_for_function('Array.from(document.querySelectorAll(".zoom img")).every(i=>i.complete&&i.naturalWidth>0)')
            check('Images render offline',page.locator('.zoom img').evaluate_all('(imgs)=>imgs.length>=5&&imgs.every(i=>i.complete&&i.naturalWidth>0)'))
            check('No horizontal overflow desktop',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.screenshot(path=str(args.output/'handbook-desktop.png'))
            page.locator('a.secondary').click();page.wait_for_selector('dialog[open] .microduck-embed')
            check('Official simulator offline fallback', '현재 오프라인' in page.get_by_role('status').inner_text())
            check('Offline has direct Space link',page.locator('dialog a[target="_blank"]').get_attribute('href')=='https://huggingface.co/spaces/pollen-robotics/microduck-simulator')
            check('Offline does not create iframe',page.locator('dialog iframe').count()==0)
            page.screenshot(path=str(args.output/'handbook-simulator-offline.png'))
            page.locator('#close-viewer').click()
            page.locator('dialog .microduck-embed').wait_for(state='detached')
            check('Close removes simulator mount',page.locator('dialog .microduck-embed').count()==0)
            concept=page.locator('a[href="static/visuals/joint-concepts-3d.html"]').first
            check('Concept viewer linked inside lessons',concept.count()==1)
            concept.click();page.wait_for_selector('dialog[open] iframe')
            check('Concept iframe stays sandboxed',page.locator('dialog iframe').get_attribute('sandbox')=='allow-scripts')
            frame=page.frame_locator('dialog iframe')
            frame.locator('#leftKnee').wait_for()
            check('Concept viewer has six joints',frame.locator('input[type=range]').count()==6)
            frame.locator('#leftKnee').focus();page.keyboard.press('ArrowRight')
            check('Concept slider changes angle',frame.locator('#leftKnee').input_value()=='17')
            page.screenshot(path=str(args.output/'handbook-joint-concepts.png'))
            page.locator('#close-viewer').click();page.locator('dialog iframe').wait_for(state='detached')
            check('Concept close removes iframe',len(page.frames)==1)
            check('Eight teaching figures embedded',page.locator('.zoom img').count()==8)
            for article_id, name in [('content-module1-concepts-index-ko-md','joints'),('content-module6-training-index-ko-md','policy'),('content-module9-robot-index-ko-md','transfer')]:
                figure=page.locator('#'+article_id+' .zoom').last
                figure.click()
                check(name+' 3D figure zooms',page.locator('dialog[open] img').is_visible())
                page.screenshot(path=str(args.output/('figure-'+name+'.png')))
                page.locator('#close-viewer').click()
            page.locator('#search').fill('ONNX')
            check('Search filters navigation',page.locator('nav a:visible').count()<page.locator('nav a').count())
            page.locator('#search').fill('')
            first=page.locator('.done').first;first.click();check('Reading progress toggle',first.get_attribute('aria-pressed')=='true')
            page.locator('.zoom').first.click();check('Image zoom opens',page.locator('dialog[open] img').count()==1);page.keyboard.press('Escape')
            page.set_viewport_size({'width':390,'height':844});page.evaluate('scrollTo(0,0)')
            page.screenshot(path=str(args.output/'handbook-mobile.png'))
            check('No horizontal overflow mobile',page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.locator('#mobile-toggle').click();check('Mobile navigation opens',page.locator('aside').get_attribute('class')=='open')
            check('No JavaScript errors',not errors);check('No external resource requests',not requests)
            ctx.close()
            if args.live:
                verify_live(browser,args.output,check)
        finally:browser.close()
    (args.output/'site-checks.json').write_text(json.dumps({'status':'PASS','live_provider_tested':args.live,'checks':checks},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS','checks':len(checks),'output':str(args.output)},ensure_ascii=False))

if __name__=='__main__':main()
