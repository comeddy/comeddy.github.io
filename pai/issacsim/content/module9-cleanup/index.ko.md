---
title: "9. 비용 정리와 다음 도전"
weight: 100
---

# 9. 결과는 보관하고 AWS 비용은 끝내기

**시간: 15분 · 실행 위치: 내 노트북**

실습의 마지막 단계입니다. 브라우저나 SSH 창을 닫는 것만으로 EC2는 종료되지 않습니다.

## 9-1. 결과 보관

워크샵 폴더에서 필요한 결과를 모두 받습니다.
`.npz` 파일은 영상보다 작지만 데이터 크기에 따라 다운로드 전송 비용이 발생할 수 있습니다.

```bash
mkdir -p artifacts
scp -i "$KEY_FILE" -r \
  "ubuntu@$EC2_IP:/opt/isaac-workshop/output/." artifacts/
ls -lh artifacts
```

모델, 평가 JSON, 데이터, 프리뷰를 열어 확인한 뒤 삭제를 진행하세요.
필요한 모델과 해시 파일을 로봇에도 보관합니다.

## 9-2. 삭제 범위 확인

```bash
export AWS_REGION=us-west-2
export STACK_NAME=physical-ai-isaac
aws sts get-caller-identity
bash scripts/cloud/cleanup.sh --plan
```

리전·스택명은 실제 생성한 값으로 맞춥니다.
정리 스크립트는 스택에 속한 EC2를 멈추고 S3 객체를 비운 다음 스택을 삭제합니다.
그 결과 루트 EBS, S3 버킷, VPC와 IAM 역할도 삭제됩니다.

## 9-3. 실제 삭제

이 명령은 AWS의 실습 데이터와 리소스를 삭제합니다. 로컬 백업을 확인한 뒤 실행합니다.

```bash
CONFIRM_DELETE_STACK="$STACK_NAME" \
  bash scripts/cloud/cleanup.sh --delete
```

완료될 때까지 기다립니다. CloudFormation 콘솔에서 스택 삭제를 확인합니다.
삭제에 실패하면 이벤트의 이유를 해결한 뒤 완료까지 확인하세요.
수동으로 켠 S3 버전 관리나 보존 설정 때문에 버킷 삭제가 막힐 수 있습니다.

## 9-4. 남은 것 확인

| 위치 | 확인 |
|---|---|
| EC2 | 해당 인스턴스가 terminated |
| EBS | 실습 루트 볼륨이 남아 있지 않음 |
| S3 | 실습 버킷 삭제 완료 |
| CloudFormation | 스택 삭제 완료 |
| 별도 생성한 항목 | 수동 스냅샷·다른 버킷 복사본은 별도로 판단 |
| 노트북/로봇 | 프리뷰 서버·SSH 터널·정책 노드 종료 |

EC2 SSH 키 페어는 스택 밖에서 만든 리소스여서 남습니다.
다른 실습에서 재사용 중이면 지우지 않습니다.
청구 대시보드의 반영에는 지연이 있을 수 있으므로 리소스 상태도 함께 확인합니다.

## 내가 완성한 것

1. AWS GPU 환경과 Isaac Sim을 구성했다.
2. 가상 센서·행동 데이터를 수집했다.
3. 내 데이터로 작은 정책을 학습하고 새 공간에서 평가했다.
4. 실제 장치에 모델을 배포하고 실제 센서로 추론했다.
5. 바퀴를 띄운 검증과 저속 주행을 수행했다.
6. 결과를 보관하고 AWS 리소스를 정리했다.

장비가 없어 모듈 6까지 수행했다면 완료 범위를 그렇게 기록합니다.
다음 도전은 [장비별 확장](../../docs/hardware-options.md)의 카메라 인식, Nav2, Isaac Lab 과정입니다.

**완료 확인:** 자신의 결과 파일과 실습 기록이 남고 AWS 실습 리소스는 삭제되었습니다.

**기억할 점:** 비용 정리까지가 end-to-end 실습입니다.

[이전: 실물 주행](../module8-real-run/index.ko.md) · [다음: 문제 해결](../troubleshooting/index.ko.md)
