---
title: "3. Isaac Sim 시작"
weight: 40
---

# 3. 첫 가상 로봇 실행

**시간: 50분 · 실행 위치: AWS EC2**

먼저 1개의 짧은 에피소드만 실행합니다.
에피소드는 “새로운 공간에서 로봇을 출발시킨 한 번의 실험”입니다.

## 3-1. NVIDIA 라이선스와 버전

이 교재는 `nvcr.io/nvidia/isaac-sim:5.1.0`에 맞춰 작성했습니다.
[NVIDIA 라이선스](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/NVIDIA_Omniverse_License_Agreement.html)를
읽고 동의한 경우에만 아래 명령의 `ACCEPT_EULA=Y`를 사용하세요.

```bash
cd ~/physical-ai-isaac-aws
ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh --check
```

최초 컨테이너 다운로드와 셰이더 캐시 생성에는 시간이 걸립니다.
몇 분 동안 출력이 조용해도 로그와 GPU 상태를 먼저 확인합니다.
호환성 검사에 문제가 있으면 데이터 수집으로 넘어가지 않습니다.

## 3-2. 디스플레이 없이 실행하는 이유

여기서 쓰는 headless는 “시뮬레이션을 실행하되 서버에 모니터 창을 띄우지 않는다”는 뜻입니다.
물리 계산과 센서 계산은 실행됩니다. 결과 파일과 프리뷰로 상태를 확인합니다.
기본 과정에 원격 데스크톱이나 WebRTC 설정이 필요하지 않습니다.

시뮬레이션은 장애물 상자를 배치한 공간에 이동로봇을 놓고 거리 센서를 읽습니다.
코드의 로봇 모델과 센서 근사는 [시뮬레이터 설명](../../static/code/sim/README.md)을 확인하세요.
실제 센서의 반사·미검출·바닥 마찰을 모두 재현하는 디지털 트윈은 아닙니다.

:image[그림 3. 6m × 6m 가상 실습장과 수평 라이다를 보여주는 설명용 3D 렌더링]{src="/static/images/concepts/sim-arena-3d.png" width=1200}

[3D 실습장 회전·확대해서 보기](../../static/visuals/arena-3d.html)

마우스로 드래그해 돌려 보고, 스크롤로 확대합니다. **위에서 보기**로 장애물 배치를,
**로봇 확대**로 센서와 바퀴 위치를 확인하세요. 라이다 광선과 벽도 켜고 끌 수 있습니다.
HTML 교재에서는 창 안에 뷰어가 열립니다. GitBook에서는 링크의 HTML을 내려받아 브라우저로 여세요.

벽 4개와 상자 8개, 출발 위치는 실습 코드의 `seed=42` 배치를 사용합니다.
보이는 광선은 센서 방향을 설명하기 위해 일부만 표시한 것입니다.
이 장면은 단순화한 로봇의 **설명용 3D 모델**이며 실제 Isaac Sim 실행 화면이 아닙니다.
물리 시뮬레이션과 AI 주행을 실행하지 않으므로 직접 실행한 장면은 모듈 3-4의 `smoke.png`로 확인합니다.

## 3-3. 짧게 한 번 실행

```bash
ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh \
  static/code/sim/run_sim.py \
  --mode collect --episodes 1 --steps 120 --seed 42 \
  --output /output/smoke.npz --preview /output/smoke.png
```

컨테이너의 `/output`은 EC2의 `/opt/isaac-workshop/output`과 연결되어 있습니다.
노트북이나 로봇의 폴더와 혼동하지 마세요.

```bash
ls -lh /opt/isaac-workshop/output
```

`smoke.npz`가 있고, 실행이 에러 없이 끝났는지 확인합니다.
파일이 있다는 사실만으로 실물이 안전하게 움직인다고 판단하지 않습니다.

## 3-4. 가상 공간을 눈으로 확인

위 명령은 `/output/smoke.png`에 첫 장면의 RGB 프리뷰를 저장합니다. 실행 궤적 등 추가 파일은
[시뮬레이터 설명](../../static/code/sim/README.md)에 나와 있습니다.
실행 결과를 비교할 수 있도록 실제 GPU 카메라 프리뷰를 함께 제공합니다.

:image[그림 3-1. Isaac Sim 5.1.0 · NVIDIA L4에서 저장한 실제 GPU 카메라 프리뷰 (seed 42)]{src="/static/images/execution/isaac-smoke.png" width=960}

2026-09-09에 `g6.4xlarge`의 NVIDIA L4에서 위 명령으로 저장한 원본 PNG입니다.
1개 에피소드·120스텝에서 이동 거리 약 1.788m, 충돌 0회, 유효 스캔 120개를 확인했습니다.
앞의 회전형 Three.js 장면은 배치와 센서를 설명하는 모델이고, 이 이미지는 실제 Isaac Sim의 카메라 출력입니다.
자신의 `smoke.png`에서 로봇·상자·벽의 배치를 이 참고 화면과 비교해 보세요.

**AWS EC2**의 별도 터미널에서:

```bash
cd ~/physical-ai-isaac-aws
bash scripts/cloud/serve-preview.sh
```

**내 노트북**의 새 터미널에서 기존의 키 경로와 EC2 주소를 다시 설정한 뒤:

```bash
ssh -i "$KEY_FILE" -N -L 8000:127.0.0.1:8000 "ubuntu@$EC2_IP"
```

브라우저로 `http://localhost:8000`을 엽니다.
`smoke.png`를 열어 로봇과 장애물 위치를 확인하고, 궤적 파일이 생성된 경우 함께 확인합니다.
두 터미널의 서버/터널은 확인 후 각각 `Ctrl+C`로 종료합니다.

## 완료 확인

- Isaac Sim 5.1.0이 GPU 환경에서 종료 코드 0으로 실행되었습니다.
- 가상 주행에서 얻은 `.npz` 파일이 생겼습니다.
- 프리뷰로 실험 공간과 주행을 확인했습니다.

**기억할 점:** 처음부터 긴 학습을 돌리지 않고 작은 시뮬레이션부터 검증합니다.

[이전: AWS](../module2-aws/index.ko.md) · [다음: 데이터](../module4-data/index.ko.md)
