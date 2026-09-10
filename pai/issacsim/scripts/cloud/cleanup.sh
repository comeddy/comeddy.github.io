#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
사용법: AWS_REGION=<region> STACK_NAME=<stack> bash scripts/cloud/cleanup.sh [--plan|--delete]
기본 --plan은 AWS 호출 없이 정리 범위를 표시합니다.
실제 삭제: CONFIRM_DELETE_STACK=<동일한 스택 이름>을 지정하고 --delete.
스택의 EC2를 정지한 뒤 버킷을 비우고 스택이 만든 리소스를 삭제합니다.
기존 네트워크 모드에서 참조한 VPC·subnet은 삭제하지 않습니다.
먼저 결과를 다운로드하세요. 되돌릴 수 없습니다.
USAGE
}
mode="${1:---plan}"
case "$mode" in
  --help|-h) usage; exit 0 ;;
  --plan|--delete) ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }
: "${AWS_REGION:?AWS_REGION을 지정하세요}"
STACK_NAME="${STACK_NAME:-physical-ai-isaac}"
export AWS_PAGER=""
if [[ "$mode" == --plan ]]; then
  printf '정리 계획: 리전=%s 스택=%s\n' "$AWS_REGION" "$STACK_NAME"
  echo "스택 소유 EC2 정지 → 스택 소유 S3 객체/미완료 업로드 삭제 → 스택 삭제 → 완료 대기"
  echo "AWS 호출 및 삭제는 하지 않았습니다. 먼저 결과 파일을 다운로드하세요."
  exit 0
fi
[[ "${CONFIRM_DELETE_STACK:-}" == "$STACK_NAME" ]] || {
  echo "삭제하려면 CONFIRM_DELETE_STACK=$STACK_NAME 값을 명시하세요." >&2; exit 2;
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$script_dir/cleanup-resources.py" "$AWS_REGION" "$STACK_NAME"
