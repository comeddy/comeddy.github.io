# 워크샵 설명 그림

모든 그림은 교육용 SVG 도형과 텍스트로 직접 작성했습니다. 실제 Isaac Sim 실행
화면, 로봇 사진 또는 실물 안전 시험의 증거를 대신하지 않습니다.

| 파일 (SVG + PNG) | 삽입 장 | 전달하는 내용 |
|---|---|---|
| [physical-ai-loop.svg](physical-ai-loop.svg) / [PNG](physical-ai-loop.png) | [소개](../../../content/introduction/index.ko.md) | 라이다 → 12개 거리 → 작은 정책 → 독립 정지 검사 → 모터 → 실제 센서 피드백 |
| [sim-arena.svg](sim-arena.svg) / [PNG](sim-arena.png) | [모듈 3: 시뮬레이션](../../../content/module3-simulation/index.ko.md) | 공식 Burger를 사용하는 6×6 m 경기장, 상자 8개·벽 4개, 수평 라이다 |
| [lidar-sectors.svg](lidar-sectors.svg) / [PNG](lidar-sectors.png) | [모듈 4: 데이터](../../../content/module4-data/index.ko.md) | 30°씩 12구역, 전방 11·0번, 구역별 최솟값, 미터와 정규화 |
| [sim-to-real.svg](sim-to-real.svg) / [PNG](sim-to-real.png) | [모듈 5: 학습](../../../content/module5-training/index.ko.md) | 규칙 교사의 실제 시뮬레이션 데이터 → 에피소드 단위 분리 → 모델·해시 → 노트북 → Pi |
| [deployment-stages.svg](deployment-stages.svg) / [PNG](deployment-stages.png) | [모듈 8: 실물 주행](../../../content/module8-real-run/index.ko.md) | preview → 바퀴를 띄운 실행 → 독립 정지 실측 통과 → 30초 바닥 주행 |

## 다시 생성하기

저장소 루트에서:

```bash
python3 scripts/generate_learning_visuals.py
```

생성기는 Python 표준 라이브러리와 이미 설치된 `rsvg-convert`만 사용합니다.
NumPy·ROS·Isaac Sim을 import하지 않으며 패키지를 설치하지 않습니다.
SVG만 필요하면 `--svg-only`를 붙입니다. 출력 경로는 위의 고정된 10개 파일입니다.
교재·HTML 빌더·실행 코드는 수정하지 않습니다.

너비는 모두 1200 px이며 높이는 740 또는 760 px입니다. 모든 보이는 텍스트는
24 px 이상입니다. 흰 배경, 옅은 파랑 카드, `#15283a` 본문, `#075bcb` 파랑,
`#086f73` 청록과 `#a3480c` 주황을 공통으로 사용합니다. PNG의 한글 글꼴은 로컬 Apple SD Gothic Neo로
렌더링했으며, SVG에는 로컬 한글 글꼴 fallback만 지정했습니다. 외부 글꼴·이미지·
스크립트·`foreignObject`는 없습니다. 다른 시스템에서는 설치된 한글 글꼴이 필요합니다.

## 수치와 해석의 근거

- [공통 코어](../../code/workshop_core.py)의 각도 규약:
  `floor((angle % 2π) / (2π / 12))`. 위에서 보면 +X 전방이 오른쪽이고 +Y가 위쪽,
  양의 각도는 반시계입니다. 0번은 `[0°, 30°)`, 11번은 `[330°, 360°)`이며
  두 구역 모두 전방 정지 검사에 사용합니다. 360°는 0°로 돌아옵니다.
  SVG 좌표의 Y축은 아래로 향하므로 광선과 구역을 그릴 때 `y = cy - r·sin(θ)`를
  사용합니다. 라이다 그림의 중심은 로봇 아이콘의 센서와 일치합니다.
- 벽 거리 예시는 벽까지 X방향 1.5 m, 광선 0°·20°·28°입니다.
  `1.5 / cos(θ)`는 약 1.5·1.6·1.7 m이고 모두 0번 구역입니다.
  대표 거리는 최솟값인 1.5 m입니다. 저장 단위는 m이며, 모델 입력만
  `clip(거리, 0, 3.5) / 3.5`로 정규화합니다. 따라서 1.5 m는 약 0.43입니다.
  잘못된 샘플·누락 구역은 0 처리 및 무효 스캔 정지 대상으로 표시했습니다.
- 수집 시 운전자는 **규칙 기반 교사**입니다.
  [수집 코드](../../code/sim/run_sim.py)는 실제 PhysX 스캔의 `observations` N×12(m),
  교사의 요청 `actions` N×2(m/s·rad/s), 정수 `episodes` N개를 저장합니다.
  [학습 코드](../../code/train.py)는 에피소드 전체를 묶어 학습·검증으로 나눕니다.
  검증용 행이 정책 학습에 섞인다는 의미로 그리지 않았습니다.
- `policy.npz`와 `policy.npz.sha256`은 EC2 → 노트북 → Pi 순서로 `scp` 전송하며
  Pi에서 SHA-256을 확인합니다. 그림의 두 파일은 모델·해시를 뜻합니다.
  교재의 `metrics.json` 전송 및 S3 보관은 핵심 흐름을 단순화하기 위해 생략했습니다.
  클라우드에서 학습하고 실시간 추론·정지 검사·모터 명령은 Pi에서 처리합니다.
- [실물 노드](../../code/device/ros_policy_node.py)는 `--arm`이 없으면
  `/workshop/cmd_vel_preview`에만 발행합니다. 첫 실제 실행의 전진 제한은
  `--arm --max-linear 0.05`입니다. 전방 ≤0.35 m 또는 스캔 나이 ≥0.5 s 등의
  오류에 정지를 고정하며, 원인을 해결하고 노드를 다시 시작해야 합니다.
  센서 만료 검사는 0.05 s 주기이지만 OS 스케줄링 때문에 0.55 s 정지를 보장하지 않습니다.
- [bringup 보완](../../code/device/workshop_cmd_vel_watchdog.hpp)은 마지막 명령에서
  0.5 s 이상 지나면 heartbeat 전송을 중단합니다. 이어서 OpenCR 통신 timeout이
  작동하므로 두 지연을 합쳐 실물에서 확인해야 합니다.
  정책 SIGKILL 후 **bringup은 계속 실행 중인 상태에서 실측 정지 ≤1.5 s**가
  [모듈 8](../../../content/module8-real-run/index.ko.md)의 교육용 통과 조건입니다.
  펌웨어나 Python 코드의 보장값이 아닙니다. bringup 종료와 통신 단절도 각각
  확인하며 2~3단계에서 바퀴는 계속 띄웁니다. 하나라도 실패하면 바닥 주행을 금지합니다.
  OpenCR PUSH SW1/SW2를 비상 정지 버튼으로 그리지 않았습니다.
- [경기장 설정](../../code/sim/scene_math.py)은 안쪽 6×6 m, 벽 4개와
  0.45×0.45×0.50 m 상자 8개입니다. 경기장 그림은 설명용 배치이며 seed 실행의
  재현 화면이 아닙니다. 로봇은 확대하고 360개 중 일부 광선만 표시합니다.
  설명용 광선은 그려진 벽·상자에서 끝나거나 입력 최대거리 3.5 m에서 끝납니다.
  옆모습은 `base_footprint` 기준 약 0.182 m 높이의 수평 스캔을 표현합니다.

생성 시 공통 코어·실물 노드·경기장 상수와 그림이 일치하는지 검사하고, SVG 구조,
12개 구역, 8개 상자·4개 벽, 최소 글꼴 크기, PNG 해상도를 확인합니다.
실제 Isaac Sim GPU 실행이나 실물 주행 시험은 그림 생성의 검증 범위에 포함하지 않습니다.
