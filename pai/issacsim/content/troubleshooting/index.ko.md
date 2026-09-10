---
title: "막혔을 때 찾아보기"
weight: 110
---

# 증상에서 시작하는 문제 해결

막혔을 때는 **어느 컴퓨터에서, 어느 명령을, 어떤 버전으로 실행했는지**부터 적습니다.
아래는 실제 장비에서 확인하며 해결할 순서입니다.

| 증상 | 확인 순서 |
|---|---|
| AWS 인증 안 됨 | 노트북에서 `aws sts get-caller-identity`, 프로파일/SSO 세션 |
| `AccessDenied` | 실패한 API의 교육용 IAM 권한과 조직 SCP; 임의 관리자 권한 확대 없이 관리자 확인 |
| GPU 생성 불가 | G/VT vCPU 한도 → 해당 AZ 타입 제공 → 실제 용량 |
| 스택 이름 이미 존재 | 기존 스택 상태 확인; 결과 보관 후 정리하거나 새 이름 사용 |
| SSH 연결 안 됨 | EC2 공인 IP → 현재 공인 출발 IP/32 → 키 페어 → 인스턴스 상태 |
| 컨테이너 GPU 안 보임 | 호스트 `nvidia-smi` → Docker runtime → bootstrap verify |
| 이미지 인증 오류 | 이미지 태그 확인; NGC가 인증을 요구하면 NVIDIA 공식 계정/레지스트리 절차 사용 |
| 최초 실행이 느림 | 이미지 다운로드·셰이더 캐시·S3 asset 접근 로그; GPU/디스크 사용 확인 |
| `No space left` | `df -h /`, `sudo docker system df`; 필요한 결과 보관 후 디스크 계획 조정 |
| 자산 로드 실패 | 공식 asset root 인터넷 접근, Burger USD 경로, 5.1 버전 |
| 프리뷰 서버 안 열림 | EC2 `serve-preview.sh` 실행, 노트북 `ssh -L`, localhost 포트 충돌 |
| 학습 데이터가 0행 | 시뮬레이션 초기화·센서 높이·유효 scan 검증 로그 |
| 모델 파일 오류 | `.npz` SHA-256, 모델 schema, 파일 크기, 코드 버전 |
| `No module named rclpy` | 로봇 Ubuntu의 Python3인지 확인; Humble `setup.bash` source |
| `No module named numpy` | 로봇에서 `sudo apt install python3-numpy` |
| `/scan`이 없음 | bringup, LDS_MODEL, 센서 USB·전원, 동일 ROS_DOMAIN_ID |
| CLI는 scan이 보이는데 정책은 정지 | scan의 NaN/0/범위/방향·모든 구역·센서 주기, 오류 로그 |
| `command topic ... type` | `/cmd_vel` 실제 타입 확인; Humble의 Twist 계약과 일치 필요 |
| 다른 publisher 발견 | teleop/Nav2/중복 노드 종료; localhost 설정과 DDS discovery 확인 |
| 앞을 막았는데 다른 방향 반응 | 센서 장착 방향·frame_id·각도 0 확인; 기본 노드는 TF 자동 보정 없음 |
| 물체를 치움에도 재시작 안 됨 | 오류가 고정되는 정상 동작; 원인 해결 후 정책 종료·재시작 |
| 바퀴가 계속 돌음 | 즉시 물리 전원 차단; command timeout·bringup heartbeat·OpenCR 펌웨어 조사 |
| 모델이 잘 맞히지만 주행은 나쁨 | 교사 품질 → 데이터 다양성 → 새 seed 평가 → 실제 센서와 시뮬레이션 차이 |
| CloudFormation 삭제 실패 | S3 객체/버전/보존 설정 → 남은 의존 리소스 → stack events |

## 도움을 요청할 때 남길 내용

```text
실행 위치: 노트북 / EC2 / 로봇
실행한 명령:
기대 결과:
실제 오류:
Ubuntu / ROS / Isaac Sim 버전:
모델 SHA-256:
센서 모델과 /cmd_vel 타입:
직전까지 성공한 모듈:
```

로그에는 액세스 키, Wi-Fi 암호, 개인 키 내용을 포함하지 않습니다.
근거 자료는 [공식 출처](../../docs/sources.md)와 [검증 기록](../../docs/verification.md)에 있습니다.

**완료 확인:** 실패한 단계와 실제 오류를 재현 가능한 형태로 정리했습니다.

**기억할 점:** 정지 검사를 끄는 대신 정지 이유를 해결합니다.

[이전: 정리](../module9-cleanup/index.ko.md) · [홈으로](../index.ko.md)
