---
title: "04 · 공식 시뮬레이션 환경 설치"
weight: 40
---

# 같은 버전으로 같은 출발점 만들기

예상 시간: 30~60분. 실행 위치: **AWS GPU 호스트의 ubuntu 사용자 셸**. 앞 단계에서 교재를 호스트에 풀어 놓았다고 가정합니다.

## 1. 경로와 GPU 확인

새 SSM 셸을 열 때마다 아래 변수를 다시 설정하세요. `실제배포리전`과 버킷 이름은 모듈 3의 출력으로 바꾸고, ONNX 단계로 돌아갈 때는 `CHECKPOINT`와 `POLICY`도 다시 설정합니다. `sudo -iu ubuntu`로 들어왔다면 먼저 홈 위치를 확인합니다.

```bash
export WORKSHOP_ROOT="$HOME/workshops/physical-ai-from-cloud-to-robot"
export DUCK_REPO="$HOME/workshops/microduck_rl"
export PATH="$HOME/.venvs/microduck-tools/bin:$PATH"
export AWS_REGION=실제배포리전
export ARTIFACT_BUCKET=출력의버킷이름
cd "$WORKSHOP_ROOT"
nvidia-smi
python3 --version
```

NVIDIA GPU와 드라이버가 표시되어야 합니다. `nvidia-smi`가 없거나 실패하면 선택한 DLAMI를 확인하고 설치를 멈추세요. 드라이버를 임의로 중복 설치하지 않습니다.

## 2. 설치 도구 준비

```bash
sudo apt-get update
sudo apt-get install -y git unzip python3-venv
python3 -m venv "$HOME/.venvs/microduck-tools"
"$HOME/.venvs/microduck-tools/bin/python" -m pip install uv
export PATH="$HOME/.venvs/microduck-tools/bin:$PATH"
uv --version
```

`uv`는 Python과 패키지를 관리하는 도구입니다. 실제 학습 패키지 버전은 공식 저장소의 `uv.lock`에 고정되어 있습니다. 호스트의 기존 Deep Learning 가상환경과 섞지 않습니다.

## 3. 계획 확인 후 설치

```bash
python3 scripts/workflow.py setup --repo "$DUCK_REPO"
```

`PLAN ONLY`와 고정 커밋이 보입니다. 아직 다운로드하지 않았습니다. [자산 이용 조건](../../docs/asset-licensing.md)에 따른 권한 확인이 완료된 경우에만 다음을 실행합니다.

```bash
python3 scripts/workflow.py setup --repo "$DUCK_REPO"   --asset-permission-confirmed --execute
```

새 폴더에 공식 저장소를 받고 정확한 커밋으로 checkout한 뒤 `uv sync --frozen --python 3.12`를 실행합니다. 이미 같은 폴더가 있으면 덮어쓰지 않고 멈춥니다. 재시도 때는 완료된 단계와 오류를 먼저 확인하세요.

## 4. 완료 확인

```bash
cd "$DUCK_REPO"
git rev-parse HEAD
uv run --frozen python -c 'import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))'
uv run --frozen list-envs
```

커밋은 `53b8971b61baf5b7f3c16d135dd7cac37623de4b`, CUDA 사용 가능은 `True`, 목록에는 `Mjlab-Velocity-Flat-MicroDuck`이 있어야 합니다. 처음 설치는 큰 CUDA 패키지를 받으므로 오래 걸릴 수 있습니다. 디스크 여유도 확인하세요.

```bash
df -h "$DUCK_REPO"
```

**기억할 점:** 버전을 바꾸거나 `uv lock`으로 새 의존성을 해석하면 이 교재의 기준 환경과 달라집니다. 기준을 먼저 실행한 뒤 별도 실험을 만드세요.

[← AWS](../module3-aws/index.ko.md) · [다음: 가상 로봇 보기 →](../module5-simulation/index.ko.md)
