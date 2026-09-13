---
title: "02 · 준비물과 자산 이용 조건"
weight: 20
---

# 시작하기 전에 준비할 것

예상 시간: 30분 + 계정·권한 준비. 먼저 [라이선스 확인 결과](../../docs/asset-licensing.md)를 읽으세요.

## 모델 이용 조건

공식 소프트웨어는 Apache 2.0, 3D 모델은 README에 **Creative Commons BY-SA-NC**로 표시되어 있습니다. 적용 버전과 파일별 경계는 검토 자료만으로 확정할 수 없었습니다. AWS 고객 행사·PoC·유료/상업적 교육에 자유롭게 쓸 수 있다고 전제하지 마세요.

**실제 모델 다운로드 전**, 운영자가 해당 목적에 맞는 이용 조건 또는 명시적 허가를 확인해야 합니다. 개인 계정으로 받거나 S3를 비공개로 만드는 것만으로 NC 제한이 사라지지 않습니다. 미확인이면 자산 취득·학습을 보류하고 교재의 자체 개념 설명·그림·코드 읽기까지만 진행합니다. 이 교재는 이용 허가를 발급하지 않습니다.

실습 코드는 `--asset-permission-confirmed` 없이는 초기 다운로드를 실행하지 않습니다. 이 옵션은 이미 확인한 사실을 표시하는 것이지 권한을 만들어 주는 기능이 아닙니다.

## 공식 온라인 체험의 범위

[공식 온라인 시뮬레이터](../../static/visuals/biped-3d.html)는 제공자가 호스팅하는 앱을 연결합니다. 인터넷과 제공자 서비스 가용성이 필요하며, 임베드가 열리지 않으면 [공식 Hugging Face Space](https://huggingface.co/spaces/pollen-robotics/microduck-simulator)에 직접 접속하세요. 교재 ZIP에는 이 앱의 메시·가중치·사진을 복사하지 않지만, 브라우저에서 앱을 열면 제공자 자산을 로드합니다.

공개 Space의 임베드·링크는 모델의 NC 조건을 해소하거나 상업 이용권을 부여하지 않습니다. 행사에서 데모를 사용하는 조건도 별도로 확인해야 하며, 워크샵의 자산 다운로드·AWS 학습 전 권한 확인은 유지됩니다. 이 데모는 AWS GPU 학습·내 체크포인트 재생과 별개이고 실제 로봇·모터에 연결하지 않습니다. 데모 화면은 워크샵 학습 성공의 증거가 아닙니다.

## 준비물

| 장소 | 준비물 |
|---|---|
| 내 컴퓨터 | 인터넷 연결, 브라우저, 터미널, Python 3, AWS CLI v2, Session Manager plugin, 교재 ZIP |
| AWS | 본인/행사 계정, EC2·SSM·S3·CloudFormation·IAM 관련 권한, G 계열 On-Demand vCPU 한도 |
| 학습 호스트 | Linux x86_64 NVIDIA GPU, CUDA 지원 AWS Deep Learning AMI, 최소 150 GiB 디스크 |
| 실물 단계 | 조립·교정된 Microduck, 호환 공식 런타임, 충전·지지대·게임패드, 같은 로컬 네트워크, 운영자 |

AWS GPU와 모델 이용 준비가 끝나지 않아도 지금 교재는 읽을 수 있습니다. 실제 로봇의 구매·배송 일정은 [제조사](https://pollen-robotics.com/microduck)에서 확인하세요.

## 내 컴퓨터에서 확인

```bash
aws --version
session-manager-plugin --version
python3 --version
aws sts get-caller-identity
```

마지막 명령의 계정이 실습 계정인지 확인합니다. 회사/행사에서 제공한 인증 절차를 따르고 액세스 키를 교재 파일이나 Git에 적지 않습니다.

## 비용을 계산하는 방법

비용은 `GPU 인스턴스 시간 × 해당 리전 요금 + EBS + S3 + 공인 IPv4/데이터 전송`입니다. 최신 금액은 [EC2 요금](https://aws.amazon.com/ec2/pricing/on-demand/)에서 확인하세요. g6.2xlarge는 시작 후보이며 메모리·수렴 시간은 직접 측정해야 합니다. 정지해도 EBS와 S3는 남습니다.

**확인:** 올바른 AWS 계정, 자산 이용 권한, GPU 한도와 비용 상한을 운영자가 확인했으면 다음으로 진행합니다.

**기억할 점:** 공개된 저장소와 모든 용도에 자유로운 자산은 같은 뜻이 아닙니다.

[← 개념](../module1-concepts/index.ko.md) · [다음: AWS 환경 →](../module3-aws/index.ko.md)
