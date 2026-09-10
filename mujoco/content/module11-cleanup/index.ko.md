---
title: "11 · 결과 저장과 비용 종료"
weight: 110
---

# 모델을 보존하고 GPU를 끄기

예상 시간: 15분. 내 컴퓨터와 GPU 호스트를 구분하세요. 호스트를 정지하기 전에 필요한 파일을 S3에 올립니다.

## 1. GPU 호스트에서 결과 저장

선택한 실행의 체크포인트, 설정, 로그와 ONNX 묶음만 별도 디렉터리에 모읍니다. 원본 모델 자산이나 인증 파일을 넣지 않습니다. 보관·전달 범위도 이용 권한을 따릅니다.

```bash
aws s3 cp "$WORKSHOP_ROOT/artifacts/"   "s3://$ARTIFACT_BUCKET/runs/my-walk/" --recursive --region "$AWS_REGION"
```

체크포인트는 `$DUCK_REPO/logs/`에 있으므로 필요한 **실제 실행 폴더**를 추가로 저장합니다. 아래 경로는 선택한 값으로 바꾸세요.

```bash
aws s3 cp "$DUCK_REPO/logs/rsl_rl/velocity/실제학습폴더/"   "s3://$ARTIFACT_BUCKET/runs/my-walk/training/" --recursive --region "$AWS_REGION"
aws s3 ls "s3://$ARTIFACT_BUCKET/runs/my-walk/" --recursive --region "$AWS_REGION"
```

## 2. 내 컴퓨터에서 GPU 정지

뷰어·TensorBoard·학습 프로세스를 종료하고 SSM 셸에서 나옵니다. **내 컴퓨터의 교재 폴더**에서:

```bash
python3 scripts/cloud/manage.py stop --region "$AWS_REGION" --stack "$STACK_NAME"
python3 scripts/cloud/manage.py status --region "$AWS_REGION" --stack "$STACK_NAME"
```

EC2가 실제 `stopped`이고 도구가 최종 확인을 마쳤는지 봅니다. 명령을 보낸 것과 정지가 끝난 것은 다릅니다. 정지된 GPU의 컴퓨팅 과금은 멈추지만 EBS·S3 등 남아 있는 리소스 비용은 계속됩니다.

## 3. 더 이상 쓰지 않으면 스택 삭제

루트 EBS는 스택 삭제 때 사라집니다. 필요한 결과의 백업과 버킷 이름을 확인한 뒤 실행합니다.

```bash
python3 scripts/cloud/manage.py destroy --region "$AWS_REGION"   --stack "$STACK_NAME" --confirm-stack-name "$STACK_NAME"
```

이 도구는 대상 워크샵 표식을 확인하고 해당 스택만 삭제합니다. **S3 버킷은 결과 보존을 위해 남습니다.** 버전 관리된 과거 객체와 삭제 마커도 남을 수 있습니다. [클라우드 실행 계약의 수동 정리](../../docs/cloud-contract.md)를 따라 정확한 버킷을 확인한 뒤 필요한 경우 비우고 삭제하세요.

로봇은 제조사 종료 절차에 따라 지지·토크 해제·전원 종료합니다. 학습 GPU를 끈다고 실제 로봇이 자동 정지하지는 않습니다.

**확인:** EC2 종료 상태, 남은 EBS·S3, 결과 보존 위치, 실제 로봇 전원을 각각 확인했습니다.

**기억할 점:** 클라우드와 로봇의 수명 주기는 별개입니다. 둘 다 확인해야 실습이 끝납니다.

[← 실물 배포](../module10-deploy/index.ko.md) · [문제 해결 →](../module12-troubleshooting/index.ko.md)
