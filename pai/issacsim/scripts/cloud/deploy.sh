#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
사용법: bash scripts/cloud/deploy.sh [--plan|--check|--deploy]
필수 환경 변수: AWS_REGION, AMI_ID, KEY_NAME, SSH_CIDR (현재 공인 IPv4/32)
선택: STACK_NAME=physical-ai-isaac, AVAILABILITY_ZONE, AMI_OWNER_ID
인스턴스: INSTANCE_TYPE=g6.4xlarge (기본) 또는 g6e.2xlarge. 자동 변경 없음.
기존 public 네트워크: EXISTING_VPC_ID와 EXISTING_SUBNET_ID를 함께 지정
기본 --plan: AWS 호출 없이 입력과 예정 명령 출력.
--check: 계정/AMI/AZ/키/G·VT vCPU 및 VPC·IGW quota 또는 기존 네트워크 읽기 조회.
--deploy: 사전 확인 후 CloudFormation 스택 생성. 이때부터 비용이 발생할 수 있음.
USAGE
}

mode="${1:---plan}"
case "$mode" in
  --help|-h) usage; exit 0 ;;
  --plan|--check|--deploy) ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }
for name in AWS_REGION AMI_ID KEY_NAME SSH_CIDR; do
  [[ -n "${!name:-}" ]] || { echo "필수 환경 변수 누락: $name" >&2; exit 2; }
done
export STACK_NAME="${STACK_NAME:-physical-ai-isaac}"
export INSTANCE_TYPE="${INSTANCE_TYPE-g6.4xlarge}"
export AWS_PAGER=""
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/preflight.py" --local
template="$script_dir/../../static/workshop.yaml"
parameters=("AmiId=$AMI_ID" "KeyName=$KEY_NAME" "SshCidr=$SSH_CIDR" "InstanceType=$INSTANCE_TYPE")
if [[ -n "${EXISTING_VPC_ID:-}" ]]; then
  template="$script_dir/../../static/workshop-existing-network.json"
  parameters+=("ExistingVpcId=$EXISTING_VPC_ID" "ExistingSubnetId=$EXISTING_SUBNET_ID")
fi

if [[ "$mode" == --plan ]]; then
  printf '계획만 출력합니다. 리소스 생성 없음.\n'
  printf '리전=%s 스택=%s AMI=%s 인스턴스=%s 디스크=200GiB gp3\n' \
    "$AWS_REGION" "$STACK_NAME" "$AMI_ID" "$INSTANCE_TYPE"
  plan_parameters=("${parameters[@]}" "RootDeviceName=<조회한 루트 장치>")
  if [[ -n "${EXISTING_VPC_ID:-}" ]]; then
    plan_parameters+=("AvailabilityZone=${AVAILABILITY_ZONE:-<기존 subnet AZ>}")
  else
    plan_parameters+=("AvailabilityZone=${AVAILABILITY_ZONE:-<조회한 AZ>}")
  fi
  printf '실행 예정 명령:\n'
  python3 -c 'import shlex,sys; print(shlex.join(sys.argv[1:]))' \
    aws cloudformation deploy --region "$AWS_REGION" \
    --stack-name "$STACK_NAME" --template-file "$template" \
    --capabilities CAPABILITY_IAM --tags Workshop=physical-ai-isaac-aws \
    --parameter-overrides "${plan_parameters[@]}"
  printf '실행 전 --check로 실제 계정의 요구 조건을 확인하세요.\n'
  exit 0
fi

command -v aws >/dev/null || { echo "AWS CLI가 필요합니다." >&2; exit 2; }
preflight_file="$(mktemp)"
trap 'rm -f "$preflight_file"' EXIT
python3 "$script_dir/preflight.py" --aws > "$preflight_file"
if [[ "$mode" == --check ]]; then
  cat "$preflight_file"
  exit 0
fi
az="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["AvailabilityZone"])' "$preflight_file")"
parameters+=("AvailabilityZone=$az")
root_device="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["RootDeviceName"])' "$preflight_file")"
echo "스택 생성 시작: $STACK_NAME ($AWS_REGION, $INSTANCE_TYPE). GPU 및 스토리지 비용이 발생합니다."
aws cloudformation deploy --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" --template-file "$template" \
  --capabilities CAPABILITY_IAM \
  --tags Workshop=physical-ai-isaac-aws \
  --parameter-overrides "${parameters[@]}" "RootDeviceName=$root_device"
aws cloudformation describe-stacks --region "$AWS_REGION" --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' --output table
echo "스택 생성 완료. SSH에서 cloud-init status --wait 확인 후 호스트 bootstrap을 실행하세요."
