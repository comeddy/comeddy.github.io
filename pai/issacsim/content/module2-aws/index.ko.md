---
title: "2. AWS GPU 환경 만들기"
weight: 30
---

# 2. 나만의 GPU 실습실

**시간: 50분 · 실행 위치: 내 노트북 → AWS EC2**

이 단계에서 비용이 발생하는 리소스를 생성합니다. 앞 단계의 예산과 계정을 먼저 확인하세요.
구성은 GPU 서버 한 대, 인터넷 연결용 네트워크, 결과 보관용 S3입니다.

:image[그림 2. 실제 CloudFormation 구성에 맞춘 AWS 배포 아키텍처]{src="/static/images/architecture/aws-deployment.png" width=1400}

큰 경계부터 AWS 계정·리전·VPC·퍼블릭 서브넷 순서로 읽습니다.
GPU EC2가 가상 실습장과 학습을 실행하고, EBS는 작업 파일을, S3는 결과를 보관합니다.
노트북에서 SSH로 접속하며, 실제 로봇은 배포받은 모델로 로컬에서 판단합니다.
그림은 기본 G6·새 VPC 구성을 보여줍니다. 아래의 선택 옵션으로 기존 네트워크나 G6e를 사용할 수 있습니다.

## 2-1. 리전·키 페어·접속 IP 정하기

**내 노트북**에서 워크샵 폴더를 엽니다.

```bash
export AWS_REGION=us-west-2
export STACK_NAME=physical-ai-isaac
aws sts get-caller-identity
```

위 리전은 예시 기본값입니다. GPU 한도를 확보한 리전으로 바꾸어도 됩니다.
모든 리소스는 같은 리전에 만드세요.

AWS 콘솔의 **EC2 → Network & Security → Key Pairs → Create key pair**에서
`physical-ai-key` 이름, RSA, `.pem`을 선택하고 다운로드합니다.
이미 있는 키 페어라면 그 이름과 보관 중인 개인 키를 사용할 수 있습니다.

```bash
export KEY_NAME=physical-ai-key
export KEY_FILE="$HOME/Downloads/physical-ai-key.pem"
chmod 400 "$KEY_FILE"
curl https://checkip.amazonaws.com
```

출력된 공인 IPv4 주소 뒤에 `/32`를 붙입니다.

```bash
export SSH_CIDR="<내 공인 IPv4>/32"
```

`<내 공인 IPv4>`는 바꿔야 하는 자리입니다. `0.0.0.0/0`을 넣으면 사전 검사가 거절합니다.
회사 VPN의 IP가 바뀌면 나중에 보안 그룹의 SSH 소스도 갱신해야 합니다.

## 2-2. Ubuntu 이미지 찾기

EC2 콘솔 **Launch instance → Quick Start Ubuntu**에서
**Ubuntu Server 22.04 LTS / 64-bit x86**의 AMI ID를 확인합니다.
이 화면에서 인스턴스를 생성하지 않고 ID만 복사합니다.

```bash
export AMI_ID="<선택한 리전의 ami-ID>"
bash scripts/cloud/deploy.sh --plan
bash scripts/cloud/deploy.sh --check
```

`--plan`은 로컬 입력만 확인하고, `--check`는 AWS 정보를 읽기 조회합니다.
사전 검사에서 계정, Canonical Ubuntu 이미지, SSH 키, 제공 AZ, 현재 G/VT vCPU 사용량과 VPC·인터넷 게이트웨이 한도를 확인합니다.
`--check`가 끝나도 GPU 재고 확보가 보장되는 것은 아닙니다.

### 한도나 GPU 재고 때문에 막힌 경우

VPC·인터넷 게이트웨이 한도를 이미 사용한 계정은 운영자가 확인한 기존 public VPC와 subnet을 사용할 수 있습니다.
`EXISTING_VPC_ID`와 `EXISTING_SUBNET_ID`를 함께 설정하면 됩니다.
스크립트가 해당 subnet의 인터넷 경로와 남은 IP를 확인하며, 기존 네트워크를 변경하거나 삭제하지 않습니다.
구체적인 입력은 [기존 네트워크 사용법](../../scripts/cloud/README.md)을 따릅니다.

G6 재고가 계속 부족하면 **L40S GPU·64GiB 메모리·8 vCPU의 G6e**를 명시적으로 선택할 수 있습니다.
리전의 G6e 단가를 먼저 확인한 뒤 실행합니다. 자동으로 더 비싼 인스턴스로 바꾸지는 않습니다.

```bash
export INSTANCE_TYPE=g6e.2xlarge
bash scripts/cloud/deploy.sh --check
```

기본값으로 돌아가려면 `unset INSTANCE_TYPE`을 실행합니다.
이미 생성에 실패한 스택은 이벤트를 기록하고 정리한 뒤 다시 배포합니다.
기존 네트워크 모드에서 AZ를 바꿀 때에는 `EXISTING_SUBNET_ID`도 해당 AZ의 subnet으로 바꿉니다.

## 2-3. 생성하기

```bash
bash scripts/cloud/deploy.sh --deploy
```

CloudFormation 콘솔에서 `physical-ai-isaac` 스택이 `CREATE_COMPLETE`가 되는지 봅니다.
정상 완료 시 Output 목록이 출력됩니다. IP와 인스턴스 ID, 결과 버킷 이름을 기록합니다.
EC2 한 대만 만들어졌는지 확인하세요.

```bash
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" --region "$AWS_REGION" \
  --query 'Stacks[0].Outputs' --output table
export INSTANCE_ID="$(aws cloudformation describe-stacks --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue | [0]" --output text)"
export EC2_IP="$(aws ec2 describe-instances --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
```

Stop/start 후 IP가 바뀌면 위 EC2 조회를 다시 실행합니다.
CloudFormation의 처음 IP Output이 실시간으로 갱신되는 것은 아닙니다.

**생성 결과:** 선택한 `g6.4xlarge` 또는 `g6e.2xlarge` GPU, 암호화된 200GiB gp3 디스크, 제한된 SSH,
SSM 역할, 비공개 S3. GUI 스트리밍 포트를 인터넷에 개방하지 않습니다.

## 2-4. 코드 복사와 접속

워크샵 폴더의 상위 디렉터리에서 폴더 전체를 EC2로 보냅니다.

```bash
cd ..
scp -i "$KEY_FILE" -r physical-ai-isaac-aws "ubuntu@$EC2_IP:~/"
ssh -i "$KEY_FILE" "ubuntu@$EC2_IP"
```

처음 접속할 때 서버 호스트 키를 확인합니다. 이후 화면의 프롬프트가
`ubuntu@ip-...`로 바뀌면 이제 **AWS EC2**입니다.

```bash
cd ~/physical-ai-isaac-aws
cat /etc/os-release
uname -m
cloud-init status --wait
sudo bash scripts/cloud/bootstrap-host.sh install
```

설치가 끝나면 재부팅합니다. SSH 연결이 끊기는 것은 정상입니다.

```bash
sudo reboot
```

약 2–3분 후 **내 노트북**에서 다시 SSH 접속하고 **AWS EC2**에서 확인합니다.

```bash
cd ~/physical-ai-isaac-aws
sudo bash scripts/cloud/bootstrap-host.sh verify
```

`nvidia-smi`에서 L4(기본) 또는 L40S(G6e) GPU와 드라이버가 보이고 컨테이너 안에서도 GPU가 보여야 합니다.
이 검사는 Isaac Sim 자체를 실행하는 검사는 아닙니다.

## 막히면

| 증상 | 해결 |
|---|---|
| GPU quota 부족 | 기존 사용량 외에 G6는 16 vCPU, G6e는 8 vCPU 여유를 확인 |
| VPC·IGW 한도 부족 | 운영자가 확인한 기존 public 네트워크 사용 또는 한도 증액 |
| `InsufficientInstanceCapacity` | 다른 제공 AZ 또는 G6e 선택; 기존 네트워크는 subnet의 AZ도 변경. 실패한 스택 정리 후 재시도 |
| SSH timeout | 현재 공인 IP, `/32` 보안 그룹, 인스턴스 상태 확인 |
| AMI 거절 | Ubuntu 22.04 x86_64 Canonical 표준 이미지인지 확인 |
| `nvidia-smi` 없음 | bootstrap 설치 로그와 재부팅 여부 확인 |
| apt 잠금 | cloud-init 완료를 기다리고 설치 로그 확인 |

**완료 확인:** GPU가 호스트와 컨테이너 양쪽에서 보입니다.

**기억할 점:** 스택 생성 성공과 GPU 애플리케이션 실행 성공은 서로 다른 확인 단계입니다.

[이전: 준비](../module1-preflight/index.ko.md) · [다음: Isaac Sim](../module3-simulation/index.ko.md)
