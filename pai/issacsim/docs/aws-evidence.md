# AWS 실습 근거와 운영 제약

확인일: **2026-09-09**. 아래 문서는 공식 사이트에서 직접 조회했다. Isaac Sim 관련 절차는 **5.1.0**으로 고정한다. 버전 URL의 내용도 나중에 수정될 수 있으므로 진행자는 행사 전에 다시 확인해야 한다.
공식 5.1.0 문서는 현재 지원 종료를 표시한다. 이 워크샵은 재현할 버전을 고정한 교육 자료이며, 신규 운영 환경의 버전 선택은 최신 지원 릴리스로 별도 검토한다.

## 결론

이 워크숍은 **본인 AWS 계정(BYOA, `customer_provided`) 전용**이다. Ubuntu Server 22.04 x86_64와 `g6.4xlarge` 한 대에서 Isaac Sim 5.1.0의 standalone Python을 headless로 실행한다. TurtleBot3 Burger를 기본 로봇으로 삼고, 직접 기록한 데이터와 NumPy `.npz` 모델을 사용한다. 클라우드 호스트에 ROS, PyTorch, ONNX, 데스크톱 환경을 추가 설치하지 않는다.

`g6.4xlarge`는 이 워크샵의 기본 실습 인스턴스다. NVIDIA의 공식 AWS 예제를 그대로 복제한 구성이나 성능 인증 결과로 표현하면 안 된다. 현재 공식 AWS 페이지는 Marketplace의 Development Workstation AMI와 `g6e.2xlarge` 또는 `g7e.8xlarge`를 안내한다. 이 저장소는 사용자가 확인한 Ubuntu AMI에 공식 드라이버와 컨테이너를 설치한다. 재고 부족 시 `INSTANCE_TYPE=g6e.2xlarge`를 명시적으로 선택할 수 있지만, 이번 애플리케이션 리허설은 G6/L4에서만 수행했다.

2026-09-09에 실제 AWS API 조회, 오리건의 새 VPC/G6 스택 생성, 드라이버 설치·재부팅, 컨테이너 GPU 전달 및 Isaac Sim 호환성 검사를 통과했다. 실제 센서 데이터와 카메라 PNG도 생성했다. 상세 결과·이미지 digest·검증 한계는 [검증 기록](verification.md)에 기록한다. 이 결과가 다른 리전의 용량이나 실물 로봇 동작을 보장하지는 않는다.

## 공식 자료와 설계에 반영한 내용

| 자료 | 직접 확인한 내용 | 반영 |
| --- | --- | --- |
| [Isaac Sim 5.1 요구사항](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html) | x86_64 Ubuntu 22.04/24.04, 최소 RAM 32GB, SSD 50GB, VRAM 16GB. GPU 최소 예시는 RTX 4080. Linux 테스트 드라이버는 580.65.06. RT Core 없는 A100/H100은 지원하지 않음 | Ubuntu 22.04와 RTX 기능이 있는 L4 선택. L4를 RTX 4080과 동일 성능이라고 주장하지 않음 |
| [Isaac Sim 5.1 AWS 배포](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_aws.html) | Marketplace AMI, RTX GPU, 키페어. 현재 예제는 g6e.2xlarge/g7e.8xlarge. SSH TCP 22, DCV TCP 8443, WebRTC TCP 49100/UDP 47998 | 기본 워크플로에는 SSH만 허용. DCV/WebRTC 포트는 생성하지 않음 |
| [Isaac Sim 5.1 컨테이너 설치](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html) | `nvcr.io/nvidia/isaac-sim:5.1.0`, Docker, NVIDIA Container Toolkit. UID/GID 1234:1234, 캐시 마운트, EULA 플래그. standalone Python은 headless 지원 | 이미지 버전 고정, 비루트 컨테이너 사용자, 영속 캐시, 별도 호환성 검사 |
| [EC2 G6 인스턴스](https://aws.amazon.com/ec2/instance-types/g6/) | g6.4xlarge: 16 vCPU, RAM 64GiB, L4 1개, GPU 메모리 24GB, 로컬 스토리지 600GB. L4는 3세대 RT Core, Vulkan 지원 | CPU/RAM/VRAM 여유를 가진 소규모 실습 후보. 로컬 NVMe는 실습에서 사용하지 않음 |
| [NVIDIA Ubuntu 드라이버 설치](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/ubuntu.html) | 실행 중인 커널의 헤더, 공식 CUDA 저장소 키링, 드라이버 분기 pinning, 설치 후 재부팅 | `nvidia-driver-pinning-580`과 `cuda-drivers-580` 사용. `.run` 설치와 혼합하지 않음 |
| [Ubuntu 22.04 NVIDIA 저장소 패키지 인덱스](https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/Packages.gz) | `cuda-keyring` 1.1-1, `nvidia-driver-pinning-580`, `cuda-drivers-580` 존재. 조회 시 R580 패치 580.178.04가 확인됨 | 존재하는 패키지명 사용, 키링 SHA256 검증. 설치된 버전은 호스트에 기록 |
| [NVIDIA Container Toolkit 설치](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | 공식 apt 저장소, `nvidia-container-toolkit`, `nvidia-ctk runtime configure --runtime=docker`, Docker 재시작 | 공식 저장소에서 설치하고 런타임 등록 |
| [Docker Engine Ubuntu 설치](https://docs.docker.com/engine/install/ubuntu/) | Docker apt 저장소와 서명 키, docker-ce 패키지, 기존 docker.io/containerd 등 충돌 주의 | 새 Ubuntu 호스트 사용. 충돌 패키지가 있으면 자동 삭제하지 않고 중단 |
| [Canonical AWS Ubuntu 이미지 확인](https://documentation.ubuntu.com/aws/aws-how-to/instances/find-ubuntu-images/) | 이미지 이름/아키텍처/리전 확인, 일반 상용 리전 Canonical 소유자 `099720109477` | AMI ID 기본값 없음. `deploy.sh --check`에서 소유자·이름·루트 EBS를 확인 |
| [EC2 할당량](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-resource-limits.html) | On-Demand 인스턴스 한도는 계열별 vCPU 기반이며 리전별 확인 필요 | G/VT 현재 사용량과 추가 16 vCPU를 비교. 증액은 사용자가 사전에 요청 |
| [Ubuntu SSM Agent 설치](https://docs.aws.amazon.com/systems-manager/latest/userguide/agent-install-ubuntu-64-snap.html) | Ubuntu에서 snap 기반 SSM Agent 설치와 서비스 시작 | UserData에서 기존 서비스 또는 snap 설치를 사용 |
| [EC2 메타데이터 옵션](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-options.html), [CloudFormation Launch Template MetadataOptions](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-properties-ec2-launchtemplate-metadataoptions.html) | IMDSv2 토큰 필수, 응답 hop limit 설정 | Launch Template에서 토큰 필수·hop limit 1. AWS 업로드는 호스트에서 수행 |

`099720109477`은 참가자 계정 ID가 아니라 Canonical이 문서화한 이미지 게시자 ID다. AWS 중국/GovCloud 등 다른 파티션은 이 워크숍의 검증 범위에 포함하지 않는다.

## 선택한 구성과 한계

- **메모리/스토리지:** RAM 64GiB와 VRAM 24GB는 소규모 로봇 장면의 출발점이다. 200GiB gp3는 요구사항의 최소 50GB보다 크지만 NVIDIA의 “Good” SSD 500GB보다 작다. Docker 이미지, 셰이더 캐시, 수집 데이터가 디스크를 채울 수 있으므로 `df -h /`로 확인한다. 대규모 센서·병렬 환경·Isaac Lab 학습에는 적합성을 보장하지 않는다.
- **드라이버:** 문서의 580.65.06은 테스트 버전이다. 스크립트는 보안 패치를 받을 수 있도록 R580의 저장소 제공 패치를 설치한다. 완전히 동일한 환경을 재현하려면 검증한 AMI·커널·드라이버·컨테이너 digest를 기록해야 한다. “최신 드라이버면 항상 작동한다”고 안내하지 않는다.
- **커널:** 새 Ubuntu 22.04 AMI를 전제로 한다. 커스텀 AMI의 Secure Boot/MOK, 기존 GRID/.run 드라이버, 오래되거나 너무 새로운 커널과 DKMS 조합은 추가 조치가 필요할 수 있다. 설치 오류를 무시하거나 자동으로 보안 기능을 끄지 않는다.
- **인터넷:** NVIDIA 컨테이너 레지스트리, Ubuntu/Docker/NVIDIA 패키지 저장소, 온라인 Isaac Sim 자산에 접근해야 한다. 첫 실행은 이미지 다운로드와 셰이더 준비 때문에 오래 걸릴 수 있다. 캐시가 있어도 모든 확장의 오프라인 실행을 보장하지 않는다.
- **공개 IP:** NAT Gateway 비용을 피하려고 퍼블릭 서브넷과 공인 IPv4를 사용한다. 공인 IPv4 자체는 유료다. SSH는 현재 사용자 공인 IPv4 `/32` 하나만 허용한다. 회사/VPN 외부 IP가 바뀌면 SG 규칙을 새 `/32`로 수정해야 한다.
- **SSM:** 인스턴스에는 `AmazonSSMManagedInstanceCore`가 연결되지만, 사용자에게 Session Manager 권한과 로컬 플러그인이 별도로 필요하다. SSM은 아웃바운드 HTTPS를 사용한다. AMI/네트워크/UserData가 실패하면 SSM도 준비되지 않을 수 있다.
- **자격 증명:** 시뮬레이션 컨테이너는 bridge 네트워크, 비루트 사용자, IMDS hop limit 1로 실행한다. 이 hop limit은 일반 bridge에서 메타데이터 응답을 제한하는 설정이며, 임의의 호스트 권한 컨테이너까지 격리하는 보안 경계는 아니다. 컨테이너에 AWS 키를 주입하지 않고, 결과는 호스트의 인스턴스 역할로 S3에 업로드한다.
- **S3:** 버킷은 비공개, AES256 서버 측 암호화, ACL 비활성화, TLS 강제다. 인스턴스의 S3 권한은 이 버킷의 읽기·업로드에 한정되며 객체 삭제 권한은 없다. SSM 관리형 정책에는 서비스 운영상 wildcard 리소스 권한이 포함된다. 사용자/정리 도구의 권한과 인스턴스 역할을 혼동하지 않는다.
- **워크숍 계정:** 이 과정은 개인·회사 실습 계정(BYOA)을 기준으로 설계했다. Workshop Studio 제공 계정으로 행사를 진행하려면 운영자가 해당 계정의 GPU 할당량·가용 리전·권한을 확인하고 별도 리허설을 완료해야 한다.

## Headless와 미리보기

시뮬레이터 코드는 Isaac Sim 모듈을 사용하기 전에 `SimulationApp({"headless": True})`를 만들고, 종료 시 `close()`를 호출해야 한다. Headless 실행도 Isaac Sim의 GPU 요구사항을 따른다. 클라우드의 순수 NumPy 정책은 거리 센서(LiDAR) 관측을 입력으로 사용하고, 시뮬레이터가 직접 기록한 데이터로 학습한 결과 `.npz`를 같은 컨테이너에서 읽는다. 기본 정책에는 카메라 입력을 사용하지 않는다.

기본 산출물은 CSV/JSON/NPZ와 **다운로드 가능한 PNG 미리보기**다. 시뮬레이터에 `--preview /output/preview.png`를 전달한다. MP4 생성은 현재 구현 범위에 포함하지 않는다. `run-headless.sh`는 `/workspace`를 읽기 전용으로 마운트하므로 기록 경로를 `/output` 또는 환경 변수 `ISAAC_OUTPUT_DIR`로 지정해야 한다. 이 스크립트가 시뮬레이터 Python의 `headless` 설정이나 출력 인자 이름을 자동으로 변경하지는 않는다.

`serve-preview.sh`는 호스트 `127.0.0.1:8000`에서 결과 파일을 제공한다. 참가자는 SSH `-L` 터널을 통해 브라우저로 PNG를 열거나 `scp`로 다운로드한다. 이는 저장된 결과 보기이며 Isaac Sim 실시간 GUI 스트리밍 기능은 아니다.

WebRTC는 **기본 미지원**이다. 공식 AWS 예제의 TCP 49100뿐 아니라 UDP 47998도 요구하므로 일반 SSH TCP 포워딩만으로 된다고 안내하면 안 된다. 향후 선택 실습으로 추가하려면 별도의 제한된 UDP 경로/VPN, GPU 인코딩, 클라이언트와 보안 그룹을 검증해야 한다. 현재 템플릿에 8443/49100/47998/8000 인바운드는 없다.

## 라이선스 동의

[NVIDIA Omniverse License Agreement](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/NVIDIA_Omniverse_License_Agreement.html)를 사용자가 직접 확인한 뒤, **명령 한 번에만 `ACCEPT_EULA=Y`**를 지정한다. 스택/UserData/bootstrap은 Isaac Sim 이미지를 받거나 EULA에 동의하지 않는다. `run-headless.sh`는 해당 환경 변수가 없으면 이미지 다운로드 전에 종료한다.

컨테이너 문서는 `PRIVACY_CONSENT=Y`를 데이터 수집 동의로 설명하며, 지정하지 않으면 opt-out할 수 있다고 명시한다. 이 워크숍은 해당 플래그를 설정하지 않는다. 관련 세부사항은 [Data Collection & Usage](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/data-collection.html)를 확인한다.

## Quota, 비용과 종료

계정/리전에서 **Running On-Demand G and VT instances** 한도에 기존 사용량 외에 기본 G6에 **16 vCPU**, 선택형 G6e에 **8 vCPU** 여유가 필요하다. `deploy.sh --check`는 조회 가능한 running/pending On-Demand G/VT 사용량을 계산하지만 동시 실행, 예약 용량, 별도 계정 정책에 따른 차이가 있을 수 있다. AZ에서 인스턴스 타입을 제공해도 즉시 GPU 용량을 보장하지 않는다. `VcpuLimitExceeded`, `InsufficientInstanceCapacity`, IAM/SCP 제한은 각각 별도로 처리한다.

비용은 다음 항목으로 산정한다. 변동하는 리전별 가격을 고정 금액으로 인용하지 않는다.

| 비용 항목 | 산정/확인 |
| --- | --- |
| g6.4xlarge On-Demand Linux | 실행 시간 × 선택 리전 단가. [EC2 On-Demand 가격](https://aws.amazon.com/ec2/pricing/on-demand/) |
| 루트 gp3 200GiB | 생성부터 삭제까지의 저장 시간. [EBS 가격](https://aws.amazon.com/ebs/pricing/) |
| 공인 IPv4 한 개 | 할당 시간. [VPC 가격](https://aws.amazon.com/vpc/pricing/) |
| S3 결과 데이터 | 용량, PUT/GET 요청, 데이터 전송. [S3 가격](https://aws.amazon.com/s3/pricing/) |
| 외부 전송/별도 산출물 | 다운로드 트래픽, 수동 스냅샷·복사본 등. [AWS Pricing Calculator](https://calculator.aws/)에서 합산 |

초기 다운로드·bootstrap·오류 조사 시간도 EC2 실행 시간에 포함된다. EC2를 **중지**하면 일반적인 On-Demand 컴퓨트 과금은 멈추지만 EBS와 S3는 남는다. Stop/start 시 공인 IP가 바뀔 수 있다. 이 워크숍은 Spot, 예약 인스턴스, 자동 증액, 용량 예약을 생성하지 않는다.

종료 순서는 **결과 다운로드 → 스택 확인 → EC2 정지 → 버킷 비우기 → CloudFormation 스택 삭제 → 삭제 완료 확인**이다. `cleanup.sh --plan`은 오프라인 계획이며, `CONFIRM_DELETE_STACK=<스택명> ... --delete`를 명시해야 실제 정리를 수행한다. 스택에서 조회한 리소스만 대상으로 한다. 루트 EBS는 암호화되고 `DeleteOnTermination: true`다. 비어 있지 않은 S3 버킷은 CloudFormation에서 삭제되지 않으므로 자동 정리 도구가 먼저 객체/미완료 업로드를 제거한다.

정리 실패 시 CloudFormation 이벤트와 EC2/EBS/S3 콘솔을 확인한다. 직접 만든 스냅샷, 다른 버킷 복사본, 키페어는 스택 삭제 대상이 아니다. 사용자가 버킷 버전 관리/보존 설정을 바꾸었거나 스택이 불완전하게 생성되었다면 자동 삭제 도구가 중단할 수 있다. 이 경우 버전·삭제 마커·보존 설정을 확인하고 콘솔에서 정리해야 한다.

## 검증 경계

기본 YAML·기존 네트워크 JSON 모두 `cfn-lint`를 통과했다. `python3 scripts/cloud/verify-local.py`는 기존 네트워크·인스턴스 선택·정리 범위를 포함해 검사한다. 최종 테스트 수와 실행 결과는 [검증 기록](verification.md)을 따른다. 별도로 YAML을 파싱하여 SSH `/32`, IMDSv2, 200GiB 암호화 gp3, S3 공개 차단·암호화, 인스턴스 역할의 버킷 범위와 UserData 쉘 구문을 확인했다. `cfn_nag_scan`은 작성 환경에 설치되어 있지 않아 실행하지 않았다.

로컬 검증 대상으로 CloudFormation 스키마, 쉘 구문, Python 구문, 오프라인 기본 동작, EULA gate, 잘못된 `/32` 입력 거부, 모의 AWS 응답에 대한 사전 확인/정리 범위 검사를 사용한다. 이 경로에서는 실제 AWS API나 Docker/GPU를 실행하지 않는다. 운영자는 본인 계정에서 다음을 순서대로 확인해야 한다.

1. `deploy.sh --check`로 AMI/키/리전/AZ/quota 확인.
2. 실제 생성 후 `cloud-init status --wait`, `/var/log/isaac-workshop-init.log` 확인.
3. `bootstrap-host.sh install`, 재부팅, `bootstrap-host.sh verify`.
4. EULA 동의 후 Compatibility Checker 출력의 **`System checking result: PASSED`** 확인. 종료 코드만 보고 통과로 간주하지 않는다.
5. 작은 장면에서 데이터/PNG 생성과 NumPy 정책 로드를 확인.
6. 로컬 결과 다운로드 후 스택을 삭제하고 잔여 비용 리소스를 확인.

구체적인 실행 명령과 컨테이너 경로 계약은 [cloud 스크립트 사용법](../scripts/cloud/README.md)을 따른다.
