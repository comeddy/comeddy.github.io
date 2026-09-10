---
title: "1. 전날 준비"
weight: 20
---

# 1. 준비를 끝내면 실습이 쉬워집니다

**시간: 전날 1–3시간 + 당일 확인 10분 · 실행 위치: 내 노트북**

## 1-1. 준비물

| 준비물 | 기본 선택 | 확인할 것 |
|---|---|---|
| 노트북 | Mac, Linux 또는 Windows WSL2 | 터미널, SSH, AWS CLI v2 |
| AWS 계정 | 교육용 개인/회사 계정 | EC2·VPC·IAM·S3·CloudFormation 권한 |
| 로봇 | TurtleBot3 Burger | Raspberry Pi 4, OpenCR, 배터리, DYNAMIXEL 모터 |
| 거리 센서 | 키트의 LDS | 센서 세대와 드라이버 일치 |
| 네트워크 | 노트북과 로봇이 같은 공유기 | 게스트 Wi-Fi의 기기 간 통신 차단 해제 |
| 실습장 | 최소 2m × 2m의 평평한 바닥 | 낙하 가장자리 없이 박스로 경계 표시 |
| 받침대 | 바퀴가 뜨는 안정적인 받침 | 모터 확인 중 로봇이 떨어지지 않을 것 |

로봇 키트가 이미 조립되어 있으면 가장 쉽습니다. 구매 시 Raspberry Pi·LDS 포함 여부와
배터리 충전기 포함 여부를 확인하세요. 부품 가격은 지역·공급업체에 따라 달라집니다.

Jetson 보유자는 [장비별 경로](../../docs/hardware-options.md)를 보세요.
로봇이 없어도 모듈 6까지는 완료할 수 있고, 그 경우 “실물 배포 완료”로 기록하지 않습니다.

## 1-2. 노트북 확인

AWS CLI v2 설치는 [AWS 공식 안내](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)를 따릅니다.
회사의 SSO 환경이면 조직에서 안내한 프로파일을 사용하세요.

```bash
aws --version
ssh -V
python3 --version
aws sts get-caller-identity
```

마지막 명령에서 자신의 계정과 역할을 확인합니다.
권한 오류가 나면 관리자에게 교육용 역할을 요청합니다. 장기 액세스 키를 교재나 코드에 넣지 마세요.

워크샵 폴더를 다운로드해 압축을 풀고 이동합니다.

```bash
cd physical-ai-isaac-aws
ls
```

`README.md`, `content`, `scripts`, `static`이 보이면 맞는 위치입니다.
이후 노트북 명령은 별도 설명이 없으면 이 폴더에서 실행합니다.

## 1-3. GPU 한도와 재고

기본 인스턴스 `g6.4xlarge`는 16 vCPU를 사용합니다.
AWS 콘솔에서 사용할 리전을 선택하고 **Service Quotas → Amazon EC2**로 들어갑니다.
`Running On-Demand G and VT instances` 한도가 **16 이상**인지 확인합니다.
같은 계열의 인스턴스를 이미 사용 중이면 그 사용량만큼 추가 한도가 필요합니다.

한도가 0이면 전날 상향을 요청합니다. 승인까지 걸리는 시간은 보장되지 않습니다.
한도가 충분해도 GPU 재고가 없을 수 있으므로 강사는 사전 실행을 확인해야 합니다.
Workshop Studio 제공 계정에 GPU가 자동으로 허용된다고 가정하지 않습니다.

## 1-4. 비용을 먼저 정하기

이 워크샵은 무료 티어 실습이 아닙니다. [AWS Pricing Calculator](https://calculator.aws/)에서
선택한 리전의 `g6.4xlarge` On-Demand, gp3 200GiB, 공인 IPv4, S3와 전송량을 견적에 넣습니다.

```text
총 비용 ≈ GPU 시간당 요금 × 켜 둔 시간
        + EBS 200GiB의 사용 기간
        + 공인 IPv4 사용 시간
        + S3 저장·요청 + 인터넷 데이터 전송
```

학습용 예산을 정하고 AWS Budgets 알림을 만드세요.
예산 알림은 자동 종료 장치가 아닙니다.
중간에 EC2를 Stop하면 GPU 컴퓨팅 비용은 중단되지만 EBS는 남습니다.

## 1-5. OS와 펌웨어 준비

로봇은 **Ubuntu 22.04 arm64 + ROS 2 Humble**로 준비합니다.
ROBOTIS 문서의 **Humble** 탭을 선택해서 진행하고,
기본으로 보이는 Jazzy/Ubuntu 24.04 절차와 혼합하지 마세요.
조립, SD 카드 이미지, OpenCR 펌웨어, LDS 세대 확인은 모듈 7의 공식 링크를 따릅니다.

**완료 확인:** 계정 확인 성공, GPU 한도 확보, 충전된 로봇, 정확한 OS 버전, 실습 폴더를 준비했습니다.

**기억할 점:** GPU 한도와 장비 OS는 당일 실습에서 가장 자주 시간을 소모하는 부분입니다.

[이전: 개념](../introduction/index.ko.md) · [다음: AWS GPU](../module2-aws/index.ko.md)
