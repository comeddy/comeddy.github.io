#!/usr/bin/env python3
"""Validate local workshop structure, HTML links, source fences and distribution."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

from package_workshop import source_files, validate_stage, ROOT

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.ids=[];self.links=[];self.images=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='a':self.links.append(a.get('href',''))
        if tag=='img':self.images.append(a)


def validate():
    errors=[]
    files=source_files()
    for p in files:
        if p.suffix in ('.md','.py','.json','.html','.yaml','.svg','.drawio','.txt'):
            text=p.read_text()
            if '\ufffd' in text:errors.append(f'Invalid replacement character: {p.relative_to(ROOT)}')
        if p.suffix=='.json':json.loads(p.read_text())
        if p.suffix in ('.svg','.drawio'):ET.parse(p)
        if p.suffix=='.py':compile(p.read_text(),str(p),'exec')
    lessons=list((ROOT/'content').rglob('*.ko.md'))
    if len(lessons)!=13:errors.append(f'Expected overview + 12 modules, found {len(lessons)}')
    bash_count=0
    for p in list((ROOT/'content').rglob('*.md'))+list((ROOT/'docs').glob('*.md'))+[ROOT/'README.md']:
        text=p.read_text()
        if len(re.findall(r'^```',text,re.M))%2:errors.append(f'Unclosed code fence: {p}')
        if '{{%' in text:errors.append(f'Unsupported Hugo shortcode: {p}')
        for block in re.findall(r'^```(?:bash|sh)\n(.*?)^```',text,re.S|re.M):
            r=subprocess.run(['bash','-n'],input=block,text=True,capture_output=True)
            bash_count+=1
            if r.returncode:errors.append(f'Shell syntax: {p}: {r.stderr.strip()}')
    page=Page();page.feed((ROOT/'index.html').read_text())
    if len(set(page.ids))!=len(page.ids):errors.append('Duplicate HTML ids')
    for target in page.links:
        if target.startswith('#'):
            if target[1:] not in page.ids:errors.append(f'Broken anchor: {target}')
        elif target and not target.startswith(('http://','https://','mailto:','data:')):
            if not (ROOT/target.split('#')[0]).exists():errors.append(f'Broken link: {target}')
    for img in page.images:
        if not img.get('alt'):errors.append('Missing image alt')
        if not img.get('src','').startswith('data:image/'):errors.append('Handbook image is not embedded')
    if len(page.images)<5:errors.append('Missing explanatory figures')
    scene=(ROOT/'static/visuals/biped-3d.html').read_text()
    if 'https://pollen-robotics-microduck-simulator.hf.space' not in scene:errors.append('Official simulator host missing')
    if 'https://huggingface.co/spaces/pollen-robotics/microduck-simulator' not in scene:errors.append('Official Space fallback missing')
    if '<canvas' in scene or 'ORIGINAL GEOMETRY' in scene:errors.append('Original robot still active in launcher')
    concept=(ROOT/'static/visuals/joint-concepts-3d.html').read_text()
    if '관절을 움직이며 이해하기' not in concept:errors.append('Concept viewer missing')
    if re.search(r'(?:src|href)=["\']https?://',concept):errors.append('Concept viewer must work offline')
    for name in ['_site','_gitbook']:
        try:
            validate_stage(ROOT/name)
        except (ValueError,OSError,KeyError) as exc:
            errors.append(str(exc))
    if errors:
        print('\n'.join(errors),file=sys.stderr);return 1
    print(json.dumps({'lessons':len(lessons),'source_files':len(files),'images':len(page.images),'html_links':len(page.links),'bash_blocks_checked':bash_count,'status':'PASS'},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(validate())
