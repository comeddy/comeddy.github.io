# AWS GPU 호스트 실행 도구

대상은 본인 AWS 계정의 **Ubuntu Server 22.04 x86_64 + g6.4xlarge(기본) 또는 g6e.2xlarge(명시적 선택) + Isaac Sim 5.1.0**이다. 명령은 별도 표시가 없으면 `physical-ai-isaac-aws` 저장소 루트에서 실행한다. 2026-09-09에 오리건에서 G6 스택 생성·호스트 설치·Isaac Sim 실행을 확인했다. 실행 조건과 한계는 [검증 기록](../../docs/verification.md)을 따른다.

## 도구 계약

| 파일 | 실행 위치 | 인터페이스 |
| --- | --- | --- |
| `deploy.sh` | 로컬 PC | `--plan`(기본, 오프라인), `--check`(AWS 읽기), `--deploy`(생성) |
| `preflight.py` | `deploy.sh`에서 호출 | `--local` 입력 검사, `--aws` 실제 읽기 조회 |
| `bootstrap-host.sh` | GPU EC2 | `install`, 재부팅 뒤 `verify`; `sudo` 필요 |
| `run-headless.sh` | GPU EC2 | `--check` 또는 저장소 내 `.py` 경로와 인자. `ACCEPT_EULA=Y` 필수 |
| `serve-preview.sh` | GPU EC2 | 인자 없음. 결과를 `127.0.0.1:8000`에서 제공 |
| `cleanup.sh` | 로컬 PC | `--plan`(기본, 오프라인), `--delete`(확인한 스택 삭제) |
| `cleanup-resources.py` | `cleanup.sh`에서 호출 | 스택 리소스를 조회한 뒤 EC2/버킷/스택 정리 |
| `verify-local.py` | 로컬 PC | 인자 없음. 모의 AWS 응답과 오프라인 기본 동작 검사 |

## 1. AMI, 키페어, quota 준비

로컬에 AWS CLI v2와 Python 3을 준비한다. AWS 자격 증명은 AWS CLI의 프로파일/SSO로 설정한다. 템플릿을 실행하는 사용자는 CloudFormation, EC2/VPC, S3, IAM 역할/인스턴스 프로파일 생성 및 `iam:PassRole` 권한이 필요하다. 사전 조회에는 STS, EC2 Describe, CloudFormation ListStacks, Service Quotas 조회 권한이 필요하다.

EC2 콘솔에서 선택한 리전의 **Canonical Ubuntu Server 22.04 LTS, 64-bit x86, HVM, EBS** AMI를 확인한다. Ubuntu Pro, Marketplace Isaac Workstation, ARM, 기존 드라이버 포함 AMI를 선택하지 않는다. 템플릿에는 AMI 기본값이 없다. 스크립트는 기본적으로 공식 게시자 `099720109477`과 Jammy 이미지 이름을 확인한다. 검증한 커스텀 Ubuntu AMI만 `AMI_OWNER_ID`로 별도 소유자를 지정할 수 있다. AMI 메타데이터만으로 실제 OS가 보증되지 않으므로 부팅 시에도 OS를 검사한다.

같은 리전의 SSH 키페어와 로컬 PEM 파일을 준비한다. G/VT On-Demand vCPU quota에 기존 사용량 외에 기본 `g6.4xlarge`는 16 vCPU, 선택형 `g6e.2xlarge`는 8 vCPU 여유가 있어야 한다. 사전 확인은 EC2가 보고한 `DefaultVCpus`로 추가 필요량을 계산한다. 자세한 근거와 비용은 [aws-evidence.md](../../docs/aws-evidence.md)를 확인한다.

```bash
# 아래 값을 실제로 확인한 값으로 바꾼 뒤 실행한다. 꺾쇠 placeholder를 그대로 쓰지 않는다.
export AWS_REGION="us-east-1"
export AMI_ID="직접_확인한_AMI_ID"
export KEY_NAME="기존_키페어_이름"
export SSH_CIDR="현재_공인_IP/32"
export STACK_NAME="physical-ai-isaac"

bash scripts/cloud/deploy.sh --plan
bash scripts/cloud/deploy.sh --check
```

`--plan`은 AWS에 접속하지 않고 입력 형식, 선택한 템플릿과 예정 파라미터만 표시한다. `--check`는 현재 계정, 기존 스택 이름, AMI 소유자, 루트 EBS, 키페어, AZ 제공 여부와 G/VT vCPU quota·사용량을 확인한다. AZ를 지정하려면 `export AVAILABILITY_ZONE=us-east-1a`처럼 본인 계정에서 조회한 값을 쓴다. quota 증액/리소스 생성/AMI 자동 선택을 하지 않는다.

기본 모드는 `static/workshop.yaml`로 VPC와 IGW를 각각 하나 생성한다. `--check`와 `--deploy`는 먼저 해당 계정·리전의 VPC와 IGW 개수를 각각 현재 quota와 비교한다. 둘 중 하나라도 여유가 없으면 스택 생성 전에 중단한다. Service Quotas `vpc` 서비스에서 확인한 필드는 `VPCs per Region` (`L-F678F1CE`)과 `Internet gateways per Region` (`L-A4707A72`)이며, 이름 대신 quota 코드로 조회 결과를 선택한다. quota를 읽지 못한 경우에도 중단한다. [AWS VPC quota 문서](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html)의 기본값 대신 계정에 적용된 값을 사용한다.

### 인스턴스 용량 부족 시 명시적 대안: G6e

`INSTANCE_TYPE`은 `g6.4xlarge`와 `g6e.2xlarge`만 허용하며, 생략하면 `g6.4xlarge`를 사용한다. 두 타입 모두 x86_64이며, 새 VPC와 기존 네트워크 모드에서 같은 방식으로 선택한다.

| 타입 | vCPU | RAM | GPU |
| --- | --- | --- | --- |
| `g6.4xlarge` (기본) | 16 | 64 GiB | NVIDIA L4 1개, 24 GB VRAM |
| `g6e.2xlarge` (명시적 대안) | 8 | 64 GiB (65,536 MiB) | NVIDIA L40S 1개, EC2 보고 GPU 메모리 45,776 MiB |

G6 재고가 부족할 때 G6e를 별도로 검토할 수 있다. 두 타입의 가격은 다르므로, vCPU가 적다는 이유로 더 저렴하다고 판단하지 말고 **선택한 리전의 최신 On-Demand 가격과 예산을 먼저 확인**한다. NVIDIA 공식 AWS 예제에 G6e가 안내되어 있지만 이 저장소의 Ubuntu AMI·컨테이너 구성은 별도 실기 검증 대상이다. 근거는 [aws-evidence.md](../../docs/aws-evidence.md)를 확인한다.

```bash
# G6e 가격과 비용을 확인한 뒤 명시적으로 선택한다.
export INSTANCE_TYPE="g6e.2xlarge"
bash scripts/cloud/deploy.sh --plan
bash scripts/cloud/deploy.sh --check
# 사용자가 생성할 때: bash scripts/cloud/deploy.sh --deploy
```

선택값은 기존 CloudFormation `InstanceType` 파라미터로 전달된다. `--plan`은 실제 선택 타입을 표시하고, `--check`는 해당 타입의 AZ 제공 목록과 G/VT quota를 확인한다. 실제 용량 부족, quota 부족 또는 오류가 발생해도 타입이나 AZ를 자동 변경하지 않는다. `unset INSTANCE_TYPE` 또는 `export INSTANCE_TYPE=g6.4xlarge`로 기본 타입을 사용한다. 기존 스택 이름 거부와 AMI·키·네트워크·정리 소유권 검사는 유지된다.

### VPC·IGW 한도에 도달한 경우: 기존 public 네트워크

새 VPC와 IGW가 계정 한도로 생성되지 않는 경우, 확인한 기존 VPC와 public subnet을 명시해 같은 GPU·S3·IAM·보안 그룹 구성을 배포할 수 있다. 자동으로 다른 네트워크를 선택하거나 재시도하지 않는다. 두 변수를 모두 지정해야 하며, ID는 `vpc-` / `subnet-` 뒤에 8자리 또는 17자리 소문자 16진수 형식이어야 한다.

```bash
export EXISTING_VPC_ID="직접_확인한_VPC_ID"
export EXISTING_SUBNET_ID="직접_확인한_SUBNET_ID"
bash scripts/cloud/deploy.sh --plan
bash scripts/cloud/deploy.sh --check
# 확인한 사용자가 생성할 때: bash scripts/cloud/deploy.sh --deploy
```

| 환경 변수 | CloudFormation 파라미터 | 동작 |
| --- | --- | --- |
| `EXISTING_VPC_ID` | `ExistingVpcId` | 새 보안 그룹을 만들 기존 VPC |
| `EXISTING_SUBNET_ID` | `ExistingSubnetId` | GPU 인스턴스의 기존 public subnet |
| `AVAILABILITY_ZONE` | `AvailabilityZone` | 생략하면 subnet AZ 사용. 지정하면 subnet AZ와 일치해야 함 |

이 모드의 템플릿은 `static/workshop-existing-network.json`이다. 원본의 `AmiId`, `KeyName`, `SshCidr`, `InstanceType`, `AvailabilityZone`, `RootDeviceName` 파라미터도 그대로 전달한다. JSON은 미리 생성된 파일이며 일반 배포에는 생성기나 `cfn-lint`가 필요하지 않다.

사전 확인은 지정 VPC/subnet이 `available`인지, subnet이 지정 VPC에 속하는지, 사용할 IPv4 주소가 최소 하나 있는지, subnet AZ가 선택한 `INSTANCE_TYPE`을 제공하는지 읽기 조회한다. subnet의 명시적 route table 연결을 먼저 확인하고, 없으면 VPC main route table을 사용한다. 유효 route table에는 `active` 상태의 `0.0.0.0/0` IGW 경로가 있어야 하며, 그 IGW의 attachment는 같은 VPC에 `available` 상태여야 한다. NAT/사설 경로나 blackhole 경로는 거부한다.

템플릿이 인스턴스 ENI에 `AssociatePublicIpAddress: true`를 명시하므로 subnet의 `MapPublicIpOnLaunch`가 꺼져 있어도 허용한다. 기존 VPC/subnet/route table/IGW의 설정·태그·연결은 수정하지 않으며, 스택으로 가져오거나 소유하지 않는다. 이 모드에서는 새 VPC·IGW가 필요 없어 해당 생성 quota 검사를 생략하지만 AMI·키·스택 이름·G/VT vCPU 검사는 유지한다. quota·가용 IP 조회는 실행 시점의 상태이며 AZ 제공 목록은 실제 GPU 용량 보장이 아니다. 네트워크 ACL 등 실제 통신과 부팅 후 런타임은 별도로 확인한다.

기본 모드로 돌아가려면 `unset EXISTING_VPC_ID EXISTING_SUBNET_ID`를 실행한다. 실패한 동일 이름 스택은 rollback 완료 상태여도 재사용하지 않으므로 새 `STACK_NAME`을 지정하거나 사용자가 기존 스택을 정리해야 한다.

## 2. 스택 생성과 접속

다음 명령부터 비용이 발생할 수 있다. 예산과 quota를 확인한 사용자가 직접 실행한다.

```bash
bash scripts/cloud/deploy.sh --deploy
```

같은 이름의 기존 스택은 실수로 교체하지 않도록 사전 확인에서 거부한다. 업데이트가 필요하면 CloudFormation 변경 내용을 별도로 검토한다.

```bash
export INSTANCE_ID="$(aws cloudformation describe-stacks --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue | [0]" --output text)"
export PUBLIC_IP="$(aws ec2 describe-instances --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
export RESULTS_BUCKET="$(aws cloudformation describe-stacks --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='ResultsBucketName'].OutputValue | [0]" --output text)"
export KEY_FILE="$HOME/.ssh/내_키.pem"
chmod 400 "$KEY_FILE"
ssh -i "$KEY_FILE" ubuntu@"$PUBLIC_IP"
```

Stop/start 후에는 위 EC2 조회를 다시 실행한다. CloudFormation의 IP Output은 실시간으로 갱신되지 않는다.
처음 연결할 때 호스트 키 지문을 확인한다. SSH 호스트 키 검증을 끄는 옵션을 사용하지 않는다. SSM을 사용하려면 로컬 Session Manager 플러그인과 사용자 권한을 준비한 후 다음 명령을 사용한다.

```bash
aws ssm start-session --region "$AWS_REGION" --target "$INSTANCE_ID"
```

스택 Outputs는 `InstanceId`, `PublicIp`, `ResultsBucketName`, `SshCommand`, `SsmCommand`, `PreviewTunnelCommand`다. `CREATE_COMPLETE`는 GPU 드라이버나 Isaac Sim 준비 완료가 아니다.

## 3. 저장소 복사와 호스트 설치

로컬 PC에서 저장소의 **부모 디렉터리**로 이동하여 복사한다. `.env`, 개인 키, AWS 자격 증명을 저장소 안에 넣지 않는다.

```bash
scp -i "$KEY_FILE" -r physical-ai-isaac-aws ubuntu@"$PUBLIC_IP":~/
```

EC2에 SSH로 접속한 터미널에서:

```bash
cd ~/physical-ai-isaac-aws
sudo cloud-init status --wait
sudo tail -n 30 /var/log/isaac-workshop-init.log
sudo bash scripts/cloud/bootstrap-host.sh install
sudo reboot
```

재부팅하면 SSH 연결이 종료된다. 재접속 후:

```bash
cd ~/physical-ai-isaac-aws
sudo bash scripts/cloud/bootstrap-host.sh verify
cat /opt/isaac-workshop/installed-packages.txt
```

설치는 NVIDIA R580 드라이버, Docker CE, NVIDIA Container Toolkit, 호스트용 AWS CLI를 준비한다. 공식 저장소의 패치 버전은 변할 수 있다. 이미지 다운로드/EULA 동의는 수행하지 않는다. `verify`는 재부팅 여부, `nvidia-smi`, Docker GPU 전달, SSM 서비스를 확인한다. 작은 `ubuntu:22.04` 컨테이너를 다운로드하여 GPU 전달을 검사한다.

실패하면 설치 출력과 `journalctl -u docker`, `dkms status`, `nvidia-smi`를 확인한다. `.run` 드라이버와 apt 설치를 혼합하거나 충돌 패키지를 임의 삭제하지 않는다. 이 도구는 새 실습 호스트를 전제로 한다.

## 4. 컨테이너 검사와 standalone 실행

사용자가 [NVIDIA EULA](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/NVIDIA_Omniverse_License_Agreement.html)를 확인하고 동의한 경우에만 다음 명령을 실행한다.

```bash
ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh --check
```

출력에서 **`System checking result: PASSED`**를 직접 확인한다. 실패/경고 내용을 확인하지 않은 채 다음 단계로 진행하지 않는다. 컨테이너 digest도 출력되므로 재현 기록에 보관한다.

작은 시뮬레이션으로 시작한다.

```bash
ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh static/code/sim/run_sim.py \
  --mode collect --episodes 1 --steps 120 --seed 42 \
  --output /output/smoke.npz --preview /output/preview.png
```

전달한 Python 코드에서 `SimulationApp({"headless": True})`를 설정해야 한다. 래퍼는 시뮬레이터의 인자를 그대로 전달한다. 시뮬레이터 옵션과 산출물은 해당 코드의 README를 함께 확인한다.

| 컨테이너 경로/설정 | 의미 |
| --- | --- |
| `/workspace` | 저장소 읽기 전용. 작업 디렉터리도 `/workspace` |
| `/output` | `/opt/isaac-workshop/output`에 연결. 데이터와 PNG 기록 |
| `ISAAC_OUTPUT_DIR=/output` | 출력 경로를 인자 없이 환경 변수로 받을 때 사용 |
| `ISAAC_ROBOT=turtlebot3_burger` | 기본 로봇 선택을 위한 값. 실제 장면/자산 생성은 시뮬레이터 담당 |
| `/workspace/.../model.npz` | 저장소에 복사한 순수 NumPy 모델을 읽는 경로 |
| `/isaac-sim/python.sh` | 래퍼가 사용하는 Isaac Sim Python |
| UID/GID `1234:1234` | 캐시/출력의 소유자와 일치. 호스트의 `ubuntu` 사용자와 다름 |

이미지 태그는 `nvcr.io/nvidia/isaac-sim:5.1.0`이다. GPU는 모두 전달하지만 특권 모드/호스트 네트워크/공개 포트 매핑을 사용하지 않는다. ROS나 별도 PyTorch/ONNX 설치를 하지 않는다. 두 번 동시에 실행하면 `isaac-workshop` 이름 충돌로 종료된다. 정상 완료 또는 `Ctrl+C`로 종료 후 다시 실행한다.

## 5. PNG 미리보기와 다운로드

앞 단계의 `--preview /output/preview.png`로 생성한 이미지와 CSV/JSON/NPZ 결과를 다운로드한다. 이 기본 과정은 MP4를 생성하지 않는다.

로컬 PC에서:

```bash
mkdir -p downloaded-results
scp -i "$KEY_FILE" -r ubuntu@"$PUBLIC_IP":/opt/isaac-workshop/output/. ./downloaded-results/
```

브라우저에서 보려면 EC2 터미널에서 다음 명령을 유지한다.

```bash
bash scripts/cloud/serve-preview.sh
```

로컬의 다른 터미널에서:

```bash
ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 -i "$KEY_FILE" ubuntu@"$PUBLIC_IP"
```

로컬 브라우저에서 `http://127.0.0.1:8000/preview.png`를 연다. 사용이 끝나면 HTTP 서버와 SSH 터널을 각각 `Ctrl+C`로 종료한다. SG의 8000 포트를 열지 않는다. 이는 저장된 결과 파일 보기이며 WebRTC가 아니다.

## 6. 선택: 비공개 S3 저장

EC2 **호스트 셸**에서 실행한다. 컨테이너에 AWS 자격 증명을 전달하지 않는다.

```bash
set -a
source /etc/isaac-workshop.env
set +a
aws s3 cp /opt/isaac-workshop/output/ "s3://$RESULTS_BUCKET/results/" --recursive
aws s3 ls "s3://$RESULTS_BUCKET/results/"
```

인스턴스 역할은 이 버킷의 읽기/업로드만 허용한다. 로컬 사용자는 별도의 S3 읽기 권한이 있어야 다운로드할 수 있다. 버킷을 공개로 바꾸지 않는다.

```bash
# 로컬 PC, 2단계의 RESULTS_BUCKET 환경 변수 사용
aws s3 cp "s3://$RESULTS_BUCKET/results/" ./downloaded-results/ --recursive
```

## 7. 종료

먼저 필요한 결과를 다운로드한다. 아래 자동 정리는 **기본 모드와 기존 네트워크 모드 모두 같은 명령**을 사용한다. 로컬 PC에서 대상 계정/리전/스택을 다시 확인한 뒤 실행한다.

```bash
bash scripts/cloud/cleanup.sh --plan

# 실제 영구 삭제
CONFIRM_DELETE_STACK="$STACK_NAME" bash scripts/cloud/cleanup.sh --delete
```

정리 도구는 `CONFIRM_DELETE_STACK`의 정확한 일치, `deploy.sh`가 붙인 Workshop 태그, 스택 상태와 스택 소유 리소스의 논리 ID·타입을 확인한다. EC2를 정지하여 쓰기를 끝낸 뒤 S3 객체/미완료 업로드를 비우고 스택을 삭제하며, 완료까지 기다린다. 자동 삭제 실패 시 오류를 숨기지 않는다. 콘솔에서 직접 만든 스택은 `Workshop=physical-ai-isaac-aws` 스택 태그가 있어야 이 도구로 정리할 수 있다.

**기존 네트워크 모드 정리:** 스택에 저장된 `ExistingVpcId`와 `ExistingSubnetId`가 모두 유효하고, 스택 리소스가 기존 네트워크 템플릿의 7개 논리 ID·타입과 정확히 일치할 때 허용한다. 기존 네트워크를 소유하는 리소스나 예상하지 않은 추가 리소스가 있으면 변경 전에 거부한다. 로컬의 `EXISTING_VPC_ID`·`EXISTING_SUBNET_ID` 설정은 정리에 필요하지 않다. 정지·S3 비우기·삭제 대상은 CloudFormation에서 조회한 스택 소유 물리 ID만 사용하며, 기존 VPC/subnet/route table/IGW를 조회·변경·삭제하지 않는다. 스택이 만든 EC2·EBS·보안 그룹·S3·IAM·launch template만 정리된다. 기본 모드는 기존처럼 스택 소유 `WorkshopVpc`가 있어야 한다. 이미 정지한 EC2는 그대로 두고 나머지 정리를 진행한다.

버킷 버전 관리나 보존 설정을 별도로 변경한 경우 자동 정리는 중단된다. 그 경우 버전/삭제 마커를 수동 정리한 뒤 CloudFormation 콘솔에서 스택을 삭제한다. 스택 생성 자체가 실패해 리소스가 일부만 남은 경우도 콘솔 이벤트를 확인한다.

EC2 중지만으로는 EBS/S3 비용이 끝나지 않는다. CloudFormation 삭제 완료, 루트 EBS 삭제, S3 삭제를 확인한다. 별도로 만든 스냅샷, 복사본, 기존 키페어는 정리 도구가 삭제하지 않는다.

## 로컬 검증

```bash
python3 scripts/cloud/verify-local.py
cfn-lint static/workshop.yaml static/workshop-existing-network.json
```

첫 명령은 표준 라이브러리만 사용한다. AWS 응답은 모의 값이며 실제 AWS CLI/Docker/bootstrap을 실행하지 않는다. 기존 public 네트워크·main route table·ID 불일치·사설 경로·가용 IP·VPC/IGW quota 소진, 선택 인스턴스 타입의 AZ·vCPU 계산, 두 모드의 정리 동작과 소유권 경계, 잘못된 스택 식별 정보의 삭제 차단을 확인하고, 가짜 CLI로 배포 래퍼의 템플릿·파라미터 전달을 검사한다. 두 번째 명령은 별도로 설치한 `cfn-lint`가 필요하다. 이 오프라인 검사와 실제 AWS 리허설 결과는 [검증 기록](../../docs/verification.md)에 구분해 기록한다.
