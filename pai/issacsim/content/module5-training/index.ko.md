---
title: "5. 내 첫 주행 AI 학습"
weight: 60
---

# 5. 12개의 거리 숫자로 주행 판단 배우기

**시간: 40분 · 실행 위치: AWS EC2**

이 모델은 매우 작습니다. Isaac Sim의 가상 세계에는 GPU가 필요하지만
12개 입력을 받는 신경망의 학습과 실제 추론은 CPU에서도 할 수 있습니다.
로봇에 CUDA나 Isaac Sim 전체를 설치할 필요가 없습니다.

:image[그림 5. 가상 주행 데이터를 학습한 뒤 모델 파일을 노트북을 거쳐 실제 로봇에 전달]{src="/static/images/concepts/sim-to-real.png" width=1200}

그림 위쪽의 AWS 영역에서 데이터를 만들고 학습합니다. 아래쪽의 로봇에서는 완성된 가중치를 사용합니다.
파일을 전달하는 경로와 로봇이 실시간으로 판단하는 위치를 구분해서 보세요.

## 5-1. 학습 시작

```bash
cd ~/physical-ai-isaac-aws
ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh \
  static/code/train.py \
  --data /output/dataset.npz \
  --output /output/policy.npz
```

완료되면 다음 파일이 생깁니다.

```bash
ls -lh /opt/isaac-workshop/output/policy.npz
cat /opt/isaac-workshop/output/metrics.json
```

`policy.npz`는 배운 가중치와 입력 규약을 담은 모델 파일입니다.
`metrics.json`은 학습·검증 오차 등 이번 실행의 기록입니다.
출력 숫자는 데이터와 실행 조건에 따라 다릅니다. 교재에 있는 임의의 수치와 맞추지 마세요.

## 5-2. 검증 데이터를 따로 두는 이유

바로 앞 프레임과 다음 프레임은 매우 비슷합니다.
모든 행을 무작위로 섞어서 일부만 검증용으로 쓰면 사실상 본 장면을 다시 맞히게 됩니다.
코드는 **에피소드 전체를 묶어서** 학습용과 검증용으로 나눕니다.

검증 오차가 작다는 것은 교사의 속도 명령을 비슷하게 재현했다는 뜻입니다.
실제 공간에서 충돌하지 않는다는 증명은 아니므로 다음 모듈에서 모델로 직접 주행시킵니다.

## 5-3. 모델을 보관하고 배포용 파일 만들기

모델을 만든 **AWS EC2 호스트**에서 S3로 보관합니다.
버킷 이름은 모듈 2의 CloudFormation Output 값을 넣으세요.

```bash
export ARTIFACT_BUCKET="<스택이 만든 버킷 이름>"
aws s3 cp /opt/isaac-workshop/output/policy.npz \
  "s3://$ARTIFACT_BUCKET/releases/v1/policy.npz"
aws s3 cp /opt/isaac-workshop/output/metrics.json \
  "s3://$ARTIFACT_BUCKET/releases/v1/metrics.json"
cd /opt/isaac-workshop/output
sha256sum policy.npz | sudo tee policy.npz.sha256
```

AWS 명령은 EC2 호스트에서 실행합니다. 컨테이너는 인스턴스 역할의 자격 증명에
접근하도록 설정되어 있지 않습니다.
S3는 팀 간 공유와 버전 보관에 쓰고, 초보 실습의 로봇 전송은 SSH 파일 복사를 사용합니다.
결과 폴더는 컨테이너 사용자가 소유하므로 해시 파일 작성에만 `sudo tee`를 사용합니다.

**내 노트북**에서 워크샵 폴더로 이동하고 결과를 받습니다.

```bash
mkdir -p artifacts
scp -i "$KEY_FILE" \
  "ubuntu@$EC2_IP:/opt/isaac-workshop/output/policy.npz" artifacts/
scp -i "$KEY_FILE" \
  "ubuntu@$EC2_IP:/opt/isaac-workshop/output/policy.npz.sha256" artifacts/
scp -i "$KEY_FILE" \
  "ubuntu@$EC2_IP:/opt/isaac-workshop/output/metrics.json" artifacts/
```

파일을 받은 뒤 크기가 0이 아닌지 확인합니다.
기존 모델을 덮어쓰기 전에 별도로 보관하면 나중에 되돌릴 수 있습니다.

**완료 확인:** 모델, 오차 기록, SHA-256 파일을 노트북에 보관했습니다.

**기억할 점:** 모델 파일만 복사하는 것이 아니라 입력 규약과 실행 코드 버전도 함께 관리합니다.

[이전: 데이터](../module4-data/index.ko.md) · [다음: 가상 검증](../module6-evaluation/index.ko.md)
