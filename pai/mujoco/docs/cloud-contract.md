# Microduck 클라우드 실행 계약

이 문서는 Microduck 워크숍 참가자가 AWS GPU 환경을 확인·생성하고, SSM으로 접속해 소스와 학습 결과를 S3로 전달하며, 실습 후 리소스를 정리하는 방법을 안내한다. 별도 표시가 없으면 명령은 워크숍 루트 `physical-ai-from-cloud-to-robot`에서 실행한다.

## 범위와 파일

- `static/workshop.yaml`: 단일 GPU EC2, 새 VPC·퍼블릭 서브넷 하나·IGW, SSM IAM 역할, 보존되는 아티팩트 버킷.
- `scripts/cloud/manage.py`: Python 3.9+ 표준 라이브러리와 AWS CLI v2 subprocess만 사용한다.
- `tests/test_cloud.py`: AWS subprocess fixture, 실제 로컬 stub 프로세스, 템플릿 계약 검사. 실제 AWS 호출 없음.
- `docs/cloud-contract.md`: 이 문서.

템플릿은 JSON 문법으로 쓴 유효한 YAML이다. `json` 표준 라이브러리로 로컬 검사와 배포된 원본 템플릿의 보존 정책 검사를 할 수 있다. 이 파일을 일반 YAML 문법으로 바꾸면 관리 CLI 파서도 함께 변경해야 한다.

## 고정 인프라 계약

| 항목 | 값 |
| --- | --- |
| 기본 인스턴스 | `g6.2xlarge`: 8 vCPU, NVIDIA L4 1개 |
| 명시적 대안 | `g6.4xlarge`: 16 vCPU, NVIDIA L4 1개 |
| AMI | 사용자가 같은 리전에서 선택한 공개 Amazon GPU Deep Learning AMI, Ubuntu 22.04 또는 24.04, x86_64 / HVM / EBS / ENA. 기본 AMI ID 없음 |
| 디스크 | 암호화된 gp3 루트 150GiB, EC2 종료 시 삭제 |
| 네트워크 | `10.77.0.0/16` VPC, `10.77.1.0/24` 서브넷 하나, 퍼블릭 IPv4, IGW 경유 기본 경로 |
| 인바운드 | 없음. SSH/HTTP/스트리밍 포트·키페어 없음 |
| 아웃바운드 | TCP 443은 SSM·S3·HTTPS 다운로드, TCP 80은 Ubuntu APT HTTP 미러 접근용. 기본 VPC DNS 해석 사용 |
| 접속 | SSM Session Manager. 인스턴스 역할에 `AmazonSSMManagedInstanceCore` |
| 메타데이터 | Launch Template에서 IMDSv2 필수, hop limit 1, metadata tags 비활성 |
| S3 | 자동 이름, Public Access Block 전체 활성, BucketOwnerEnforced, SSE-S3 AES256, 버전 관리 활성, TLS 필수 |
| 보존 | 버킷과 버킷 정책 모두 `DeletionPolicy: Retain` 및 `UpdateReplacePolicy: Retain` |
| 워크숍 표식 | 스택 태그와 템플릿 Metadata의 `Workshop=physical-ai-from-cloud-to-robot` |

모듈 4의 `apt-get`으로 `git`, `unzip`, `python3-venv`를 설치할 때 DLAMI의 기본 Ubuntu 저장소가 HTTP 미러를 사용할 수 있어 아웃바운드 TCP 80을 허용한다. APT는 서명된 저장소 메타데이터와 해당 메타데이터에 포함된 패키지 해시를 검증한다. 이 기본 검증을 유지하며 `--allow-unauthenticated`나 `trusted=yes`를 사용하지 않는다. SSM과 S3 통신은 TCP 443을 사용하고, 버킷의 TLS 필수 정책도 유지한다.

AWS DLAMI의 사전 설치 NVIDIA 드라이버를 사용한다. UserData, 커스텀 apt 드라이버 설치, 자동 학습, SSH 키 발급은 없다. IMDS hop limit 1이므로 호스트에서 S3를 사용한다. 컨테이너의 인스턴스 프로파일 접근까지 보장하는 계약은 아니다.

4096개 병렬 환경의 실제 학습 가능 여부는 검증되지 않았다. G6 타입 제공 여부와 quota 통과도 해당 시점의 GPU 재고를 보장하지 않는다. GPU 학습, MuJoCo/프로젝트 의존성 설치, 학습 성능 검증은 별도 본문 단계다.

## CLI 인자

`python3 scripts/cloud/manage.py [check|deploy|status|stop|destroy] [옵션]`

| 인자 | 기본값 / 용도 |
| --- | --- |
| 서브명령 생략 | `check`. 읽기 전용 AWS 조회. 오프라인 모드나 리소스 생성이 아님 |
| `--region` | `AWS_REGION` 또는 `AWS_DEFAULT_REGION`. 둘 다 없으면 필수 |
| `--stack`, `--stack-name` | 동일한 인자, 기본 `physical-ai-microduck`. 영문자로 시작, 영문/숫자/하이픈, 128자 이하 |
| `--ami-id` | `check`·`deploy`에서 필수. 이 리전에서 검증할 AMI ID. 환경변수에서 자동으로 추측하지 않음 |
| `--instance-type` | `g6.2xlarge` 기본. `g6.4xlarge`도 허용. `check`·`deploy`에서 사용 |
| `--availability-zone` | 선택 사항. `check`·`deploy`에서 사용. 생략 시 사용 가능한 일반 AZ와 타입 제공 AZ 교집합의 이름순 첫 번째 |
| `--profile` | 선택 사항. 모든 AWS 호출에 적용. 생략하면 AWS CLI 기본 자격 증명 체인/SSO/`AWS_PROFILE` 사용 |
| `--wait-seconds` | 기본 1200, 허용 1..3600. 각 상태 대기 단계의 제한. 배포는 CFN 생성과 SSM Online을 각각 대기 |
| `--confirm-stack-name` | `destroy`에만 필수. `--stack` 값과 정확히 일치해야 함 |

`stop`에는 추가 확인 플래그가 없다. `status`·`stop`·`destroy`에는 AMI와 인스턴스 타입을 다시 전달할 필요가 없다. `--key-name`, `--ssh-cidr`, AMI owner override, `--force`, 자동 버킷 삭제 옵션은 없다. 기존 스택 갱신·변경 집합·자동 재배포도 지원하지 않는다.

각 AWS CLI 프로세스는 최대 45초, connect/read timeout은 10/20초, 최대 2회 시도다. 목록 조회는 최대 20페이지(페이지당 최대 100개)에서 중단하며, 한도를 초과하거나 권한이 부족하면 불완전한 결과를 통과시키지 않는다. 상태 조회는 최대 10초 간격이다. 상태 대기 제한 직전에 시작된 마지막 AWS 호출에는 추가로 최대 45초가 걸릴 수 있다.

## 준비 및 사전 검사

로컬에 Python 3.9+, AWS CLI v2, 설정된 AWS 자격 증명을 준비한다. SSM shell에는 로컬 Session Manager plugin도 필요하다. 비밀 키를 템플릿·스크립트·소스 zip에 넣지 않는다.

AMI는 [DLAMI 공식 문서](https://docs.aws.amazon.com/dlami/latest/devguide/what-is-dlami.html)와 EC2 콘솔에서 같은 리전의 Amazon GPU DLAMI Ubuntu 22.04/24.04로 선택한다. 고정 ID를 복사하지 않는다. 드라이버와 SSM Agent를 포함한 이미지를 선택하고, 배포 후 SSM과 NVIDIA 상태를 확인한다. 임의 Canonical 기본 Ubuntu AMI, 개인 복사 AMI, Marketplace 제품 코드가 있는 이미지는 이 계약에서 거부한다.

```bash
export AWS_REGION=us-west-2
export STACK_NAME=physical-ai-microduck
export AMI_ID='직접_확인한_AMI_ID'

python3 scripts/cloud/manage.py check \
  --region "$AWS_REGION" --stack "$STACK_NAME" \
  --ami-id "$AMI_ID" --instance-type g6.2xlarge
```

서브명령을 생략해도 같은 읽기 전용 검사다. `check`는 STS 계정, 같은 스택 이름의 부재, CloudFormation validate-template, 다음 사항을 조회한다.

1. `describe-images --owners amazon --image-ids ...` 및 `ImageOwnerAlias=amazon`으로 소유자를 확인한다. available/public/machine, Linux/UNIX, x86_64/HVM/EBS/ENA, Ubuntu 버전과 GPU DLAMI 이름, 제품 코드 부재, 비폐기 이미지, 계정 AMI 허용 여부, 부팅 모드 호환성을 검사한다.
2. 루트 이름은 AMI에서 얻는다. `/dev/sda1` 또는 `/dev/xvda`, 150GiB 이하 루트 EBS 하나만 허용한다. 추가 EBS가 필요한 AMI는 지원하지 않는다.
3. EC2 타입의 x86_64/On-Demand 지원과 단일 NVIDIA L4를 확인한다. 사용 가능한 일반 AZ에서 타입 제공 여부를 확인한다.
4. 계정에 적용된 VPC quota `L-F678F1CE`와 IGW quota `L-A4707A72`를 조회하고 각각 하나를 추가할 여유를 검사한다.
5. G/VT On-Demand vCPU quota `L-DB2E81BA`를 조회한다. pending/running의 non-Spot 사용량은 타입의 DefaultVCpus로 계산하고, 활성 Capacity Reservation의 미사용 G/VT vCPU도 더한다. 예약 유형에 따른 예외를 감안해 보수적으로 계산한다.

키페어를 요구하거나 조회하지 않는다. 계정 IAM/SCP, EBS·S3·IAM 등 모든 서비스 quota, 실제 GPU 재고, 실행 중 quota 변화, DLAMI 내부 드라이버 상태까지 사전 보장하지 않는다. 메타데이터 검사는 OS 부팅 검증을 대신하지 않는다.

읽기 검사 권한에는 STS GetCallerIdentity, CloudFormation DescribeStacks/ValidateTemplate, EC2 DescribeImages/DescribeInstanceTypes/DescribeAvailabilityZones/DescribeInstanceTypeOfferings/DescribeVpcs/DescribeInternetGateways/DescribeInstances/DescribeCapacityReservations, Service Quotas GetServiceQuota가 필요하다. 배포에는 템플릿 리소스의 생성·롤백·삭제 권한과 IAM PassRole/CAPABILITY_IAM 동의가 필요하다. 상태 관리에는 CloudFormation ListStackResources/GetTemplate/DescribeStacks, EC2 DescribeInstances/StopInstances, SSM DescribeInstanceInformation 권한도 필요하다. 관리 CLI는 이러한 권한을 자동 부여하지 않는다.

## 명시적 배포와 상태 확인

아래 `deploy`는 사용자가 비용 발생을 결정한 시점에 실행하는 명령이다.

```bash
python3 scripts/cloud/manage.py deploy \
  --region "$AWS_REGION" --stack "$STACK_NAME" \
  --ami-id "$AMI_ID" --instance-type g6.2xlarge

python3 scripts/cloud/manage.py status \
  --region "$AWS_REGION" --stack "$STACK_NAME"
```

`deploy`는 전체 `check`를 다시 실행한 다음 새 스택을 `create-stack`으로 생성한다. 스택 태그를 자동 부여한다. 기존 스택이면 중단하며 업데이트하지 않는다. CloudFormation 생성 제한은 20분이고 생성 실패 시 ROLLBACK을 요청한다. CREATE_COMPLETE 뒤 SSM Online/Linux까지 확인한다. SSM timeout은 성공한 스택을 자동 삭제하지 않는다. EC2가 계속 과금될 수 있으므로 `status`를 확인하고 `stop` 또는 `destroy`를 별도로 실행한다.

`status`는 JSON 객체 하나를 출력한다. `Resources`는 논리 ID→물리 ID, `Outputs`는 CloudFormation 출력 키→값이다. `deploy`/`destroy`는 진행 안내도 출력하므로 전체 stdout을 JSON 하나로 파싱하지 않는다.

| CFN 파라미터 | 전달 방식 |
| --- | --- |
| `AmiId` | 사용자가 지정한 `--ami-id` |
| `InstanceType` | `--instance-type` |
| `AvailabilityZone` | 검증된 AZ |
| `RootDeviceName` | 선택한 AMI에서 조회한 루트 이름 |

출력: `TrainingInstanceId`, `ArtifactBucketName`, `ArtifactBucketArn`, `VpcId`, `SubnetId`, `SecurityGroupId`, `AvailabilityZone`, `InstanceRoleArn`, `WorkshopMarker`. 공인 접속 URL이나 SSH 접속 명령은 출력하지 않는다.

CFN 콘솔에서 템플릿만 직접 배포하면 관리 CLI의 AMI 검증과 자동 스택 태그가 생략된다. 본문은 이 CLI 배포 경로를 사용한다. 실패 진단은 다음 읽기 명령으로 한다.

```bash
aws cloudformation describe-stack-events \
  --region "$AWS_REGION" --stack-name "$STACK_NAME" --max-items 30
```

## SSM 접속, 소스 전달, 결과 저장

로컬에서 배포 출력 값을 읽는다. 이후 모든 S3 경로는 이 스택의 전용 버킷이다.

```bash
export TRAINING_INSTANCE_ID="$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`TrainingInstanceId`].OutputValue | [0]' --output text)"
export ARTIFACT_BUCKET="$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`ArtifactBucketName`].OutputValue | [0]' --output text)"

# 최종 패키지는 워크숍 루트의 상위 디렉터리에 있다.
# ZIP은 physical-ai-from-cloud-to-robot/ 최상위 폴더를 포함한다.
# 매니페스트 경로는 physical-ai-from-cloud-to-robot/static/upstream-lock.json이다.
aws s3 cp ../physical-ai-from-cloud-to-robot.zip "s3://$ARTIFACT_BUCKET/workshop/source.zip" \
  --region "$AWS_REGION" --sse AES256

aws ssm start-session --region "$AWS_REGION" --target "$TRAINING_INSTANCE_ID"
```

로컬 업로더에게 해당 버킷의 PutObject 권한이 필요하다. 인스턴스 역할이 로컬 사용자에게 권한을 주지는 않는다. 세션 사용자는 SSM StartSession과 해당 인스턴스/세션 문서에 대한 허가가 필요하다.

SSM shell에서 Ubuntu 사용자로 전환한 뒤 실제 OS·GPU를 먼저 확인한다.

```bash
sudo -iu ubuntu
cat /etc/os-release
uname -m
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
python3 --version
aws --version

# 로컬 터미널의 버킷 출력 값을 이 SSM shell에 입력한다.
export AWS_REGION=us-west-2
export ARTIFACT_BUCKET='배포_출력의_ArtifactBucketName'
mkdir -p "$HOME/workshops"
aws s3 cp "s3://$ARTIFACT_BUCKET/workshop/source.zip" "$HOME/workshops/source.zip" --region "$AWS_REGION"
python3 -m zipfile -e "$HOME/workshops/source.zip" "$HOME/workshops"
cd "$HOME/workshops/physical-ai-from-cloud-to-robot"
test -f static/upstream-lock.json
```

호스트 역할의 S3 허용 범위는 다음과 같다. 모든 ARN은 해당 스택의 버킷으로 한정한다.

| 경로 | 호스트 권한 |
| --- | --- |
| 버킷 | ListBucket, GetBucketLocation, ListBucketMultipartUploads |
| `workshop/*` | GetObject: `workshop/source.zip` 다운로드 |
| `runs/*` | GetObject, PutObject, AbortMultipartUpload, ListMultipartUploadParts |
| 삭제 / ACL | DeleteObject, DeleteObjectVersion, PutObjectAcl 부여하지 않음 |

학습은 본문에서 별도로 실행한다. 결과를 저장할 때는 학습 결과만 담은 디렉터리를 선택한다.

```bash
# GPU 호스트: 본문에서 확인한 실제 결과 디렉터리와 실행 ID로 치환한다.
export RUN_DIR='실제_학습_결과_디렉터리'
export RUN_ID='실행_ID'
aws s3 cp "$RUN_DIR/" "s3://$ARTIFACT_BUCKET/runs/$RUN_ID/" \
  --recursive --no-follow-symlinks --region "$AWS_REGION" --sse AES256
```

```bash
# 로컬 PC: 공개 URL 대신 인증된 S3 다운로드를 사용한다.
aws s3 cp "s3://$ARTIFACT_BUCKET/runs/" ./artifacts/ \
  --recursive --region "$AWS_REGION"
```

## 중지 및 스택 삭제

```bash
python3 scripts/cloud/manage.py stop --region "$AWS_REGION" --stack "$STACK_NAME"
```

`stop`은 스택 표식과 리소스 계약, 인스턴스의 CloudFormation stack-id/Workshop 태그를 검사하고 그 EC2 한 대만 중지한다. 최종 `stopped` 상태를 다시 조회한 뒤 `Verified: true`를 반환한다. 이미 stopped이면 재요청 없이 상태를 확인한다. EBS와 S3 저장 비용은 계속 발생한다. 재시작이 필요하면 EC2 콘솔에서 이 인스턴스를 시작한 뒤 `status`로 SSM Online을 확인한다.

삭제 전에 필요한 루트 디스크 결과를 S3로 업로드하고 버킷 이름을 별도로 기록한다. 루트 EBS는 EC2 종료와 함께 삭제된다.

```bash
python3 scripts/cloud/manage.py status --region "$AWS_REGION" --stack "$STACK_NAME"
python3 scripts/cloud/manage.py destroy --region "$AWS_REGION" --stack "$STACK_NAME" \
  --confirm-stack-name "$STACK_NAME"
```

`destroy`는 이름 확인값이 없거나 다르면 AWS 호출 전에 중단한다. 표식 없는 스택, 진행 중 스택, 계약 외 리소스가 있는 스택을 거부한다. 배포된 원본 템플릿 Metadata와 ArtifactBucket/ArtifactBucketPolicy의 Retain 정책을 다시 읽어 확인한다. 이름을 확인한 뒤 실제 삭제는 해당 스택 ARN으로만 요청한다. 삭제 완료 상태를 기다리며, DELETE_FAILED이면 추가 강제 삭제를 하지 않는다.

버킷과 TLS 정책은 보존된다. `RetainedArtifactBucket`에 이름을 출력하며 S3 객체·버전·버킷을 삭제하는 AWS 호출은 전혀 수행하지 않는다. 생성 실패/롤백 뒤에도 보존된 버킷이 남을 수 있다. `status`의 리소스 또는 CloudFormation 이벤트에서 ArtifactBucket의 물리 ID를 확인하고 기록한다.

## 보존 버킷의 별도 수동 정리

이 단계는 보관할 결과와 과거 버전까지 삭제하기로 사용자가 결정한 뒤 실행한다. 관리 CLI는 이 작업을 자동화하지 않는다. 같은 이름의 새 스택을 만들더라도 이전 보존 버킷을 재사용하거나 삭제하지 않는다.

1. 정확한 버킷 이름과 계정·리전을 확인하고 필요한 소스/결과/과거 버전을 백업한다.
2. S3 콘솔의 **버전 표시**를 켜서 현재 객체, 모든 과거 버전, 삭제 마커를 각각 확인한다. 일반 재귀 삭제는 버전 전체를 비우지 않는다.
3. 아래 읽기 명령의 `Versions`와 `DeleteMarkers`를 모두 확인한다. NextToken이 있으면 같은 명령에 `--starting-token`으로 이어서 조회한다.
4. 삭제할 특정 키와 VersionId를 명시하여 하나씩 지운다. 삭제 마커도 해당 VersionId로 삭제한다. 범용 purge 스크립트나 `s3 rm --recursive`/`rb --force`는 제공하지 않는다.
5. 미완료 multipart upload는 콘솔에서 확인 후 중단하거나 7일 lifecycle 정리를 기다린다. 다른 객체와 버전에는 만료 lifecycle이 없다.
6. 모든 버전·삭제 마커·업로드를 정리한 뒤 빈 버킷만 별도로 삭제한다.

```bash
# 읽기: 해당 버킷의 버전/삭제 마커와 미완료 업로드 확인
aws s3api list-object-versions --region "$AWS_REGION" \
  --bucket "$ARTIFACT_BUCKET" --max-items 100
aws s3api list-multipart-uploads --region "$AWS_REGION" \
  --bucket "$ARTIFACT_BUCKET" --max-items 100

# 의도한 버전 하나만 영구 삭제. 실제로 확인한 값으로 치환한다.
aws s3api delete-object --region "$AWS_REGION" --bucket "$ARTIFACT_BUCKET" \
  --key '확인한_객체_키' --version-id '확인한_VersionId'

# 모든 버전과 삭제 마커가 정리되어 비어 있는 버킷만 삭제 가능
aws s3api delete-bucket --region "$AWS_REGION" --bucket "$ARTIFACT_BUCKET"
```

## 로컬 검증과 한계

```bash
python3 -B -m unittest discover -s tests -p test_cloud.py -v
cfn-lint static/workshop.yaml
python3 -B scripts/cloud/manage.py --help
```

테스트는 기본 읽기 전용 동작, AMI 거부 조건, quota/페이지 처리, 기존·무표식 스택 거부, 생성 후 SSM 대기, stop 최종 확인, 삭제 확인값·배포된 보존 정책·계약 외 리소스 거부를 다룬다. 실제 AWS 계정에 대한 사전 검사, 배포, SSM 접속, DLAMI 부팅, GPU 학습은 수행하지 않았다. 퍼블릭 IPv4·EC2·EBS·보존 S3 비용이 발생하며 리전별 가격은 실행 전에 확인한다.

참고: [describe-images 소유자 필터](https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-images.html), [EC2 quota](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-resource-limits.html), [CFN 리소스 목록 API](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/list-stack-resources.html), [CloudFormation Retain](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html), [Session Manager 준비](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-prerequisites.html).
