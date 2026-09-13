#!/usr/bin/env python3
"""Original Korean educational SVGs. Standard library only; no external assets."""
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'static/images'
C={'ink':'#143F43','muted':'#536B6C','paper':'#F5F6F0','yellow':'#F0D160','line':'#D6E1DB','soft':'#E9F1ED','white':'#FFFFFF'}

def txt(x,y,s,size=22,fill=None,weight=400,anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill or C["ink"]}" text-anchor="{anchor}">{escape(s)}</text>'
def lines(x,y,ss,size=22,gap=34,fill=None,weight=400):return ''.join(txt(x,y+i*gap,s,size,fill,weight) for i,s in enumerate(ss))
def rect(x,y,w,h,fill=None,stroke=None,r=20):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill or C["white"]}" stroke="{stroke or C["line"]}"/>'
def path(d,arrow=False,color=None,width=3,dash=False):return f'<path d="{d}" fill="none" stroke="{color or C["ink"]}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'+(' stroke-dasharray="7 8"' if dash else '')+(' marker-end="url(#arrow)"' if arrow else '')+'/>'
def badge(x,y,n):return f'<circle cx="{x}" cy="{y}" r="23" fill="{C["yellow"]}"/>'+txt(x,y+7,n,20,weight=700,anchor='middle')
def base(name,title,subtitle,height=940):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="{height}" viewBox="0 0 1440 {height}" role="img" aria-labelledby="title desc" lang="ko">
<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>
<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto-start-reverse"><path d="M0 0 L9 4.5 L0 9 Z" fill="{C['ink']}"/></marker></defs>
<rect width="1440" height="{height}" fill="{C['paper']}"/>
<g font-family="Pretendard, Apple SD Gothic Neo, Noto Sans KR, Noto Sans CJK KR, sans-serif">
{txt(64,61,'PHYSICAL AI   /   '+name,16,weight=700)}
{txt(64,130,title,44,weight=750)}
{txt(64,180,subtitle,22,C['muted'])}
'''
def finish(body,filename,footer,height=940):
    body+=path(f'M64 {height-88} H1376',width=1,color=C['line'])+txt(64,height-47,footer,17,C['muted'])+'</g></svg>'
    (OUT/filename).write_text(body,encoding='utf-8')

s=base('01  LEARN BY TRYING','강화학습: 행동하고, 결과에서 배웁니다','한 스텝의 경험을 모아 PPO가 정책을 업데이트합니다. 이 과정은 클라우드 시뮬레이션 안에서 반복됩니다.')
# Four readable stages and a distinct, slower update lane.
xs=[64,414,764,1114];ws=[290,290,290,262]
heads=['관측 o(t)','정책 πθ','행동 a(t)','시뮬레이터']
labels=[['현재 상태를 숫자로','관절각 · 관절 속도','몸의 방향 · 목표 속도'],['신경망이 관측을 읽고','다음 행동을 제안','지금의 파라미터 θ 사용'],['예: 관절 목표값','제어기 입력의 의미는','환경 설정으로 확인'],['MuJoCo Warp','가상 로봇이 한 스텝','새 관측 · 보상 · 종료']]
for i,(x,w,h,ls) in enumerate(zip(xs,ws,heads,labels)):
    s+=rect(x,310,w,268)+badge(x+39,352,str(i+1))+txt(x+25,418,h,29,weight=700)+lines(x+25,465,ls,20,32)
    if i<3:s+=path(f'M{x+w+10} 445 H{xs[i+1]-13}',True)
s+=path('M1244 302 V247 H204 V301',True)+rect(521,227,392,42,C['paper'],C['paper'],10)+txt(717,256,'다음 관측 o(t+1)로 반복',19,weight=600,anchor='middle')
s+=rect(760,648,616,136,C['soft'])+txt(791,692,'경험 모으기 · Rollout',27,weight=700)+lines(791,730,['관측·행동·보상·종료 여부를 기록','여러 병렬 환경에서 일정 길이만큼 수집'],21,31)
s+=rect(64,648,616,136,'#FFF6D2','#E2CB70')+txt(94,692,'PPO 업데이트',27,weight=700)+lines(94,730,['수집한 경험으로 정책 θ를 조정','보상은 학습 신호이며 안전 보증이 아닙니다'],21,31)
s+=path('M1244 589 V636',True)+path('M748 716 H692',True)+path('M209 636 V610 H559 V590',True)
s+=txt(290,638,'갱신한 정책으로 다시 수집',17,C['muted'])
finish(s,'learning-loop.svg','교육용 개념도 · 관측·행동·보상 정의와 PPO 설정은 선택한 환경의 실제 코드를 기준으로 확인합니다.')

s=base('02  CHECK BEFORE TRANSFER','Sim → Real: 단계마다 통과 조건이 있습니다','시뮬레이션에서 좋은 결과를 얻어도 바로 모터를 움직이지 않습니다. 검증 결과를 확인하며 다음 단계로 진행합니다.')
xs=[64,400,736,1072]
content=[('번들 무결성',['파일 목록과 버전','manifest · ONNX','checkpoint 출처','SHA-256 일치']),('입출력 계약',['관절 이름과 순서','각도·속도 단위','정규화·스케일','제어 주기와 제한']),('시뮬레이션 검증',['내보낸 정책 평가','관측·행동 값 점검','목표와 실패 조건','실제 실행 설정 비교']),('실기 실행 승인',['운영자 점검·승인','지지 상태에서 시작','비상정지 준비·확인','로컬 50Hz 제어'])]
for i,(x,(title,ls)) in enumerate(zip(xs,content)):
    s+=rect(x,293,304,374)+badge(x+41,338,f'{i+1:02}')+txt(x+25,408,title,28,weight=700)
    for j,line in enumerate(ls):
        s+=f'<circle cx="{x+30}" cy="{457+j*41}" r="3.5" fill="{C["ink"]}"/>'+txt(x+47,464+j*41,line,20)
    s+=rect(x+24,620,256,29,C['soft'],C['soft'],8)+txt(x+152,640,'통과 후 다음 단계',15,weight=600,anchor='middle')
    if i<3:s+=path(f'M{x+311} 486 H{x+329}',True,width=2)
s+=rect(64,712,1312,102,C['ink'],C['ink'])+txt(95,755,'하나라도 실패하면 STOP',27,C['yellow'],700)+txt(95,789,'원인을 수정하고 해당 단계부터 다시 검증합니다. 클라우드는 실시간 모터 루프에 참여하지 않습니다.',21,'#FFFFFF')
finish(s,'sim-to-real-gates.svg','개념적 점검 흐름 · SHA-256 일치는 파일 무결성 확인이며 모델의 안전성·성능 인증이 아닙니다.')

s=base('03  READ THE ROBOT','관절각은 관측의 한 부분입니다','각도 q는 “어디에 있는가”, 각속도 q̇는 “얼마나 빠르게 움직이는가”를 나타냅니다.')
s+=rect(64,250,556,554)+txt(94,297,'한쪽 다리의 단순 기하 모형',25,weight=700)
s+=path('M127 733 H557',width=2,color='#A6BBB3')+path('M268 356 V710',color='#A6BBB3',dash=True,width=2)
s+=rect(224,339,106,74,C['ink'],C['ink'],10)
s+=path('M277 420 L358 548 L281 700',width=44,color='#74998E')+path('M277 420 L358 548',width=29,color='#CADBD1')
s+=rect(247,686,142,34,C['ink'],C['ink'],7)
for x,y in [(277,420),(358,548),(281,700)]:s+=f'<circle cx="{x}" cy="{y}" r="17" fill="{C["yellow"]}" stroke="{C["ink"]}" stroke-width="3"/>'
s+=path('M277 468 A48 48 0 0 0 303 459',color=C['ink'],width=2)+path('M333 514 A42 42 0 0 0 339 586',color=C['ink'],width=2)
s+=path('M300 420 H416',color='#68817A',width=1.5)+txt(428,426,'q₁ 고관절',21,weight=600)
s+=path('M379 548 H416',color='#68817A',width=1.5)+txt(428,555,'q₂ 무릎',21,weight=600)
s+=path('M301 680 H416',color='#68817A',width=1.5)+txt(428,687,'q₃ 발목',21,weight=600)
s+=txt(94,775,'치수·축·가동 범위는 실제 로봇 사양이 아닙니다.',18,C['muted'])
s+=rect(660,250,716,168,'#FFF6D2','#E2CB70')+txt(694,294,'q / q̇ 를 함께 읽기',27,weight=700)+lines(694,336,['같은 각도에서도 멈춘 상태와 움직이는 상태는 다릅니다.','q̇는 시간에 따른 q의 변화입니다. 실제 단위·부호를 확인하세요.'],21,34)
s+=rect(660,450,716,214)+txt(694,494,'관측 벡터 o(t)에 담을 수 있는 값',27,weight=700)+lines(694,538,['[ 관절각 q, 관절 속도 q̇, 몸의 방향, 목표 속도, … ]','환경에 따라 IMU·이전 행동·접촉 정보 등이 추가됩니다.','정확한 길이·순서·정규화는 manifest와 환경 설정을 대조합니다.'],20,39)
s+=rect(660,696,716,108,C['ink'],C['ink'])+txt(694,739,'관측 o(t) → 정책 → 행동 a(t)',25,C['yellow'],700)+txt(694,777,'행동은 예: 관절 목표값. 슬라이더는 기하 자세만 바꿉니다.',20,'#FFFFFF')
finish(s,'observation-action.svg','독자 제작 교육용 도식 · 실제 Microduck의 형상·질량·관절축·관측 텐서·동역학을 재현하거나 검증하지 않았습니다.')
print('Wrote 3 original educational SVGs')
