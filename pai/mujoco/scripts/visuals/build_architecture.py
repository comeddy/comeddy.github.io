#!/usr/bin/env python3
"""Generate the VPC skeleton with the architecture-diagram skill, then compose the
managed-service and offline handoff panels that its VPC spec does not yet support.
Only the spec's one Region / VPC / AZ / public subnet / EC2 is instantiated.
"""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SKILL = Path(os.environ.get('ARCHITECTURE_SKILL', Path.home()/'.agents/skills/architecture-diagram'))
spec = importlib.util.spec_from_file_location('aws_layout', SKILL/'scripts/layout_aws.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)
with tempfile.TemporaryDirectory(prefix='physical-ai-architecture-') as td:
    seed = Path(td)/'seed.drawio'
    subprocess.run([sys.executable, str(SKILL/'scripts/layout_aws.py'), str(HERE/'aws-architecture.spec.json'), '-o', str(seed)], check=True)
    tree = ET.parse(seed)
model = tree.find('.//mxGraphModel')
model.set('pageWidth', '1960'); model.set('pageHeight', '1240'); model.set('background', '#FFFFFF')
root = model.find('root')
byid = {e.get('id'): e for e in root.findall('mxCell')}
FONT = 'Amazon Ember'
TEAL = '#143F43'

def style(**kw):
    return ';'.join(f'{k}={v}' for k,v in kw.items())+';'

def cell(id, value, x,y,w,h, sty, parent='1'):
    e = ET.SubElement(root,'mxCell',id=id,value=value,style=sty,vertex='1',parent=parent)
    ET.SubElement(e,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    byid[id]=e
    return e

def text(id,value,x,y,w,h,size=16,bold=False,color=TEAL,align='left',parent='1',fill='none'):
    return cell(id,value,x,y,w,h,style(text='',html=1,whiteSpace='wrap',overflow='hidden',strokeColor='none',fillColor=fill,align=align,verticalAlign='middle',fontSize=size,fontStyle=int(bold),fontColor=color,fontFamily=FONT,spacing=0),parent)

def box(id,value,x,y,w,h,fill='#F4F7F5',stroke='#D9E3DF',parent='1'):
    return cell(id,value,x,y,w,h,style(rounded=1,arcSize=5,html=1,whiteSpace='wrap',strokeColor=stroke,fillColor=fill,fontFamily=FONT,fontSize=16,fontColor=TEAL,verticalAlign='top',align='left',spacing=20),parent)

def setgeo(id,x,y,w,h,parent=None):
    e=byid[id];g=e.find('mxGeometry')
    for k,v in dict(x=x,y=y,width=w,height=h).items():g.set(k,str(v))
    if parent:e.set('parent',parent)

def service(id,label,x,y,icon,parent='1'):
    sty=layout.icon_style(icon).replace('fontSize=10;', 'fontSize=16;')+'labelWidth=250;spacingTop=10;labelBackgroundColor=#FFFFFF;'
    if icon in ('identity_and_access_management', 'systems_manager'):
        sty=sty.replace('#D05C17','#C7131F').replace('#F78E04','#F34482')
    return cell(id,label,x,y,78,78,sty,parent)

def edge(id,src,dst,kind='sync',label='',points=(),anchors=(1,.5,0,.5)):
    ex,ey,ix,iy=anchors
    sty=layout.edge_style(kind,f'exitX={ex};exitY={ey};entryX={ix};entryY={iy};exitPerimeter=0;entryPerimeter=0;')
    sty=sty.replace('fontSize=9;', 'fontSize=14;')+'labelBackgroundColor=#FFFFFF;'
    if kind=='mgmt':sty+='strokeColor=#879196;strokeWidth=1;dashed=1;dashPattern=4 4;opacity=60;'
    if kind=='sync':sty+='strokeWidth=1.5;'
    e=ET.SubElement(root,'mxCell',id=id,value=label,style=sty,edge='1',parent='1',source=src,target=dst)
    g=ET.SubElement(e,'mxGeometry',relative='1',attrib={'as':'geometry'})
    if points:
        a=ET.SubElement(g,'Array',attrib={'as':'points'})
        for x,y in points:ET.SubElement(a,'mxPoint',x=str(x),y=str(y))
    return e

# Reuse generated structural cells and official styles; compose a wider editorial layout.
for e in list(root):
    if e.get('id') not in {'0','1','learner','region','vpc','az_0','subnet_0_0','gpu_0'}:root.remove(e)
# The Cloud container must render behind the generated descendants.
cloud=cell('cloud','AWS Cloud',350,190,1070,850,layout.container_style('group_aws_cloud','#232F3E','#232F3E'))
root.remove(cloud);root.insert(2,cloud)
setgeo('region',40,210,990,610,'cloud')
setgeo('vpc',40,190,540,410,'region')
setgeo('az_0',30,90,480,260,'vpc')
setgeo('subnet_0_0',30,30,420,200,'az_0')
setgeo('gpu_0',170,40,78,78,'subnet_0_0')
byid['gpu_0'].set('value','GPU EC2 · NVIDIA L4<br>DLAMI Ubuntu<br>MuJoCo Warp / mjlab PPO')
byid['gpu_0'].set('style',layout.icon_style('ec2').replace('fontSize=10;','fontSize=16;')+'labelWidth=300;spacingTop=10;')
for id in ['cloud','region','vpc','az_0','subnet_0_0']:
    byid[id].set('style',byid[id].get('style').replace('fontSize=12;','fontSize=16;').replace('grStroke=0;', 'grStroke=1;'))
setgeo('learner',140,460,78,78)
byid['learner'].set('style',layout.icon_style('user').replace('fontSize=10;','fontSize=16;')+'labelWidth=260;spacingTop=10;')
byid['learner'].set('value','학습자<br>브라우저 + AWS CLI')
text('eyebrow','WORKSHOP ARCHITECTURE  /  01',60,40,1300,30,16,True)
text('title','클라우드에서 학습하고, 로봇 곁에서 실행합니다',60,80,1820,60,34,True)
text('subtitle','학습 결과는 검증할 수 있는 파일 번들로 전달합니다. 모터를 제어하는 50Hz 루프는 로컬에 있습니다.',60,145,1800,30,19,color='#536B6C')
text('phase1','01  권한 확인과 세션 접속',70,380,260,40,18,True)
service('iam','AWS IAM<br>사용자 권한 · EC2 역할',100,50,'identity_and_access_management',parent='cloud')
text('iam-note','Global service<br>최소 권한으로 접속·S3 접근 허용',570,240,620,70,17,color='#536B6C')
service('ssm','AWS Systems Manager<br>Session Manager',250,50,'systems_manager',parent='region')
text('ssm-note','02  관리 세션<br>SSM Agent가 HTTPS 연결 시작<br>SSH 인바운드 규칙 없음',780,450,450,80,17,True)
# IGW is a VPC-boundary resource; it is described at the boundary rather than
# routed as a motor/control edge. Public IPv4 plus its default route supply egress.
text('igw','Internet Gateway (IGW)',470,630,300,30,15,True)
text('egress','Public IPv4 · 0.0.0.0/0 → IGW · TCP 80/443 아웃바운드',470,960,460,30,13,color='#536B6C')
service('s3','Amazon S3 · 비공개 버킷',790,320,'s3',parent='region')
text('artifact-title','03  학습 결과 보관',1090,610,280,40,18,True)
text('artifacts','checkpoints / ONNX<br>workshop-manifest / SHA-256<br><br>Block Public Access<br>VPC 밖의 리전 서비스',1080,850,280,130,16,color='#536B6C',align='center')
box('local','','1490',400,400,640,fill='#F4F7F5')
text('local-head','로컬 현장 · 운영자 책임 구간',1520,425,340,40,19,True)
text('local-desc','AWS 클라우드 밖',1520,470,320,30,15,color='#536B6C')
box('operator','',1530,660,320,140,fill='#FFF7D6',stroke='#E2C653')
text('op-title','04  운영자 다운로드·검증',1550,680,280,30,18,True)
text('op-desc','해시 확인 → 입출력 계약 확인<br>시뮬레이션·실기 승인 후 배치',1550,720,280,60,16)
box('runtime','',1530,870,320,130,fill='#143F43',stroke='#143F43')
text('runtime-title','05  Microduck 로컬 런타임',1550,885,280,30,18,True,color='#FFFFFF')
text('runtime-desc','관측 → 정책 추론 → 모터 명령<br>50Hz 제어 · 1회 주기 20ms',1550,925,280,55,16,color='#FFFFFF')
edge('auth','learner','iam','mgmt','IAM 인증·인가',[(280,499),(280,279)])
edge('permission','learner','ssm','mgmt','SSM 접속',[(300,499),(300,489)])
edge('session','ssm','gpu_0','mgmt','',[(679,610),(860,610),(860,740),(726,740)],(.5,1.7,.85,0))
edge('upload','gpu_0','s3','highlight','번들 업로드',[(1000,789),(1000,759)])
edge('download','s3','operator','sync','HTTPS 다운로드',[(1450,759),(1450,730)])
edge('handoff','operator','runtime','sync','승인한 번들 배치',[],(.5,1,.5,0))
box('boundary','',60,1090,1830,100,fill='#143F43',stroke='#143F43')
text('boundary-title','경계 원칙',90,1110,170,30,18,True,color='#EED35B')
text('boundary-copy','클라우드는 학습·보관을 담당합니다. 클라우드에서 모터로 가는 실시간 제어 경로는 없습니다.',270,1110,1530,30,21,True,color='#FFFFFF')
text('legend','실선: 번들 전송·배치   /   주황 실선: 학습 결과 업로드   /   회색 점선: 권한·관리 관계 (패킷 경로를 단순화한 개념도)',270,1150,1530,25,15,color='#D7E5E0')
out=ROOT/'static/images/aws-architecture.drawio'
ET.indent(tree,space='  ');tree.write(out,encoding='utf-8',xml_declaration=True)
for tool in ['snap_grid.py','validate_drawio.py','lint_layout.py']:
    args=[sys.executable,str(SKILL/'scripts'/tool),str(out)]
    if tool=='snap_grid.py':args.append('--in-place')
    subprocess.run(args,check=True)
print(out)
