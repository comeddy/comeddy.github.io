#!/usr/bin/env python3
"""Add a descriptive accessible title and remove draw.io's export-help link.
Run after each draw.io SVG export. No drawing elements or embedded metadata change.
"""
from pathlib import Path
import re
from html import escape
p=Path(__file__).resolve().parents[2]/'static/images/aws-architecture.svg'
s=p.read_text()
s=re.sub(r'<switch><g requiredFeatures="http://www.w3.org/TR/SVG11/feature#Extensibility"[^>]*/><a[^>]*xlink:href="https://www.drawio.com/doc/faq/svg-export-text-problems".*?</a></switch>','',s,flags=re.S)
s=re.sub(r'<title id="architecture-title">.*?</title><desc id="architecture-desc">.*?</desc>','',s,flags=re.S)
s=re.sub(r' role="img"| aria-labelledby="architecture-title architecture-desc"','',s,count=2)
start=s.index('<svg');end=s.index('>',start)
s=s[:end]+' role="img" aria-labelledby="architecture-title architecture-desc"'+s[end:]
end=s.index('>',s.index('<svg'))
text='<title id="architecture-title">클라우드에서 학습하고 로봇 곁에서 실행하는 AWS 아키텍처</title><desc id="architecture-desc">학습자가 브라우저와 AWS CLI로 IAM 권한과 SSM 세션을 사용합니다. 단일 리전의 VPC와 공용 서브넷에 있는 L4 GPU EC2에서 DLAMI Ubuntu, MuJoCo Warp, mjlab PPO로 학습합니다. SSH 인바운드 없이 TCP 80/443 아웃바운드를 사용합니다. SSM은 HTTPS, Ubuntu apt 미러는 HTTP를 사용할 수 있습니다. VPC 외부의 비공개 S3에 checkpoint, ONNX, workshop-manifest와 SHA-256을 보관합니다. 운영자가 번들을 내려받아 검증하고 승인한 뒤 Microduck 로컬 런타임에 배치합니다. 50Hz 모터 제어는 로컬에서 수행하며 클라우드는 실시간 모터 루프에 참여하지 않습니다.</desc>'
s=s[:end+1]+text+s[end+1:]
p.write_text(s)
print('Added accessible architecture description; removed export-help hyperlink')
