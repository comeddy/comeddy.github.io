#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  printf '%s\n' \
    'GPU 호스트에서: bash scripts/cloud/serve-preview.sh' \
    '결과를 127.0.0.1:8000에서 제공. 로컬 PC에서 SSH -L 터널을 열고 접속하세요.' \
    '종료: Ctrl+C. 파일 다운로드용이며 실시간 WebRTC 스트리밍이 아닙니다.'
  exit 0
fi
[[ $# -eq 0 ]] || { echo "--help를 참고하세요." >&2; exit 2; }
result_dir=/opt/isaac-workshop/output
[[ -d "$result_dir" ]] || { echo "결과 경로가 없습니다: $result_dir" >&2; exit 1; }
exec python3 -m http.server 8000 --bind 127.0.0.1 --directory "$result_dir"
