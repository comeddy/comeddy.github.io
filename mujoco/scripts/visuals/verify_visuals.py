#!/usr/bin/env python3
"""Check workshop diagrams and the offline official-simulator launcher.
Live provider integration is tested separately by scripts/verify_site.py --live.
Requires Playwright + Chromium. Does not replace historical viewer evidence.
"""
from pathlib import Path
import argparse
import json
import re
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    def check(name, condition):
        if not condition: raise AssertionError(name)
        checks.append(name)
    for name in ['learning-loop.svg', 'sim-to-real-gates.svg', 'observation-action.svg', 'aws-architecture.svg']:
        content = (ROOT/'static/images'/name).read_text()
        check(name+' parses', ET.fromstring(content).tag.endswith('svg'))
        check(name+' has no remote image', not re.search(r'(?:href|src)=["\']https?://', content))
    cells = {e.get('id'): e for e in ET.parse(ROOT/'static/images/aws-architecture.drawio').findall('.//mxCell')}
    check('GPU inside public subnet', cells['gpu_0'].get('parent') == 'subnet_0_0')
    check('No cloud-to-motor edge', all(c.get('source') == 'operator' for c in cells.values() if c.get('target') == 'runtime'))
    check('S3 outside VPC', cells['s3'].get('parent') not in ['vpc', 'az_0', 'subnet_0_0'])
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            ctx = browser.new_context(offline=True, viewport={'width':1360,'height':1000})
            page = ctx.new_page(); errors = []; requests = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url) if r.url.startswith(('http:', 'https:')) else None)
            page.goto((ROOT/'static/visuals/biped-3d.html').as_uri())
            check('No original geometric robot', page.locator('canvas,input[type=range]').count() == 0)
            check('Explicit launch only', page.locator('iframe').count() == 0)
            check('Official fallback destination', page.get_by_role('link', name='공식 Space 새 탭').get_attribute('href') == 'https://huggingface.co/spaces/pollen-robotics/microduck-simulator')
            page.get_by_role('button', name='시뮬레이터 실행').click()
            check('Offline explanation', '현재 오프라인' in page.get_by_role('status').inner_text())
            check('Offline skips external iframe', page.locator('iframe').count() == 0)
            page.screenshot(path=str(args.output/'launcher-desktop.png'))
            page.set_viewport_size({'width':390, 'height':844})
            check('Mobile has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.screenshot(path=str(args.output/'launcher-mobile.png'), full_page=True)
            check('No launcher JavaScript errors', not errors)
            check('No automatic network requests', not requests)
            ctx.close()
            ctx = browser.new_context(java_script_enabled=False, offline=True)
            page = ctx.new_page(); page.goto((ROOT/'static/visuals/biped-3d.html').as_uri())
            check('No-JavaScript direct link', page.get_by_role('link', name='공식 Space 새 탭에서 열기').is_visible())
            ctx.close()
        finally: browser.close()
    report = {'status':'PASS', 'scope':'Diagrams and launcher only; no live provider, AWS, or hardware verification', 'checks':checks}
    (args.output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status':'PASS', 'checks':len(checks), 'output':str(args.output)}, ensure_ascii=False))

if __name__ == '__main__': main()
