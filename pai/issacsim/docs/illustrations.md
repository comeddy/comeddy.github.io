# 교재 이미지 안내

설명용 그림 6개와 실제 Isaac Sim 실행 참고 화면 1개, 총 7개를 본문의 해당 설명 바로 옆에 배치했습니다.
HTML은 PNG를 파일 안에 내장하므로 이미지 폴더를 따로 옮기지 않아도 그림이 보입니다.
Workshop Studio 원고는 `/static/images/` 아래의 PNG를 참조합니다.

| 그림 | 설명 | 교재 위치 | 원본 |
|---|---|---|---|
| 1. 센서 → 판단 → 행동 | 거리 측정, 정책, 정지 검사, 바퀴의 반복 과정 | 개념 소개 | [PNG](../static/images/concepts/physical-ai-loop.png) · [SVG](../static/images/concepts/physical-ai-loop.svg) |
| 2. AWS 배포 아키텍처 | 실제 CloudFormation의 네트워크·GPU·저장소와 접근 경로 | 모듈 2 | [PNG](../static/images/architecture/aws-deployment.png) · [SVG](../static/images/architecture/aws-deployment.svg) · [draw.io](../static/images/architecture/aws-deployment.drawio) |
| 3. 가상 실습장 3D | 6m × 6m 공간, 벽 4개, 상자 8개, 수평 라이다 | 모듈 3 | [PNG](../static/images/concepts/sim-arena-3d.png) · [SVG](../static/images/concepts/sim-arena-3d.svg) · [3D 뷰어](../static/visuals/arena-3d.html) |
| 3-1. 실제 Isaac Sim GPU 카메라 | Isaac Sim 5.1.0 · L4의 seed 42 smoke 실행 원본 | 모듈 3-4 | [PNG](../static/images/execution/isaac-smoke.png) · [공개 출처 기록](../static/images/execution/isaac-smoke.provenance.json) |
| 4. 거리 센서 12구역 | 30도씩 나누고 구역별 최솟값을 선택하는 방법 | 모듈 4 | [PNG](../static/images/concepts/lidar-sectors.png) · [SVG](../static/images/concepts/lidar-sectors.svg) |
| 5. 가상에서 실물로 | 데이터·학습·에피소드 검증·모델 파일 전송 | 모듈 5 | [PNG](../static/images/concepts/sim-to-real.png) · [SVG](../static/images/concepts/sim-to-real.svg) |
| 6. 실제 주행 확인 순서 | 그림자 실행 → 받침 테스트 → 독립 정지 확인 → 저속 주행 | 모듈 8 | [PNG](../static/images/concepts/deployment-stages.png) · [SVG](../static/images/concepts/deployment-stages.svg) |

## 이미지의 의미

AWS 그림은 이 워크샵의 CloudFormation 템플릿을 설명하는 구성도입니다.
VPC 경계 밖에 있는 S3와, 클라우드 밖에서 로컬 추론하는 실제 로봇을 구분합니다.
그림 3은 실습 코드의 `seed=42` 배치를 3D 도형으로 구성한 설명용 렌더링입니다.
로봇 형상은 단순화했으며 물리 계산이나 AI 주행을 실행하지 않습니다.
HTML 교재의 3D 링크를 누르면 같은 장면을 회전·확대하고 라이다와 벽을 켜고 끌 수 있습니다.
독립 HTML 뷰어와 교재에 3D 코드가 내장되어 있으므로 CDN이나 인터넷 연결이 필요하지 않습니다.
WebGL을 지원하는 브라우저가 필요합니다. GitBook에서는 HTML 파일을 내려받아 여세요.

그림 3-1은 2026-09-09에 Isaac Sim 5.1.0을 `g6.4xlarge`의 NVIDIA L4와 드라이버 580.178.04로
실행하여 저장한 실제 GPU 카메라 출력입니다. `seed=42`, 1개 에피소드·120스텝에서 이동 거리 약 1.788m,
충돌 0회, 유효 스캔 120개를 확인한 실행의 원본 PNG를 변경 없이 포함했습니다.
공개 출처 기록에는 실행 날짜·버전·호스트 타입·GPU·드라이버·seed와 PNG SHA-256만 담았습니다.

그림 1~6은 원리와 절차를 설명하는 도식과 모델입니다.
참가자는 직접 생성한 `smoke.png`를 그림 3-1과 비교하고,
주행 궤적은 CSV에서 생성한 `evaluation.svg`로 확인합니다.

## 다시 만들기

2D 학습 그림은 `scripts/generate_learning_visuals.py`로 생성합니다.
3D 장면의 생성 방법은 [3D 제작 안내](../scripts/visuals/README.md)를 확인하세요.
PNG 변환에는 `rsvg-convert`가 필요합니다. 일반 교재 읽기와 HTML 재생성에는 필요하지 않습니다.
AWS 그림은 포함된 draw.io 원본으로 수정할 수 있습니다.
실행 참고 PNG를 갱신할 때는 실제 Isaac Sim 실행 산출물을 바이트 그대로 복사하고 공개 출처 기록의
SHA-256을 함께 갱신합니다. 이 화면에는 그림 생성기나 SVG 변환을 적용하지 않습니다.

이미지를 바꾼 다음 HTML을 다시 생성하고 파일 경로와 구문을 검사합니다.

```bash
python3 scripts/build_handbook.py
python3 scripts/validate_workshop.py
```

실행 검증의 범위는 [검증 기록](verification.md)에 있습니다.
