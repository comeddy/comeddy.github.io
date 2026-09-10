#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
GPU 호스트의 저장소에서:
  ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh --check
  ACCEPT_EULA=Y bash scripts/cloud/run-headless.sh <저장소 내 Python 경로> [인자...]
컨테이너: nvcr.io/nvidia/isaac-sim:5.1.0 / UID:GID 1234:1234
입력: /workspace (저장소 읽기 전용)
결과: /output (호스트 /opt/isaac-workshop/output), 환경 변수 ISAAC_OUTPUT_DIR=/output
Python 코드에서 SimulationApp({"headless": True})를 사용해야 합니다.
이 스크립트는 WebRTC/GUI/ROS를 시작하지 않습니다.
USAGE
}
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  usage
  exit 0
fi
[[ $# -ge 1 ]] || { usage >&2; exit 2; }
if [[ "${ACCEPT_EULA:-}" != Y ]]; then
  echo "NVIDIA 라이선스를 읽고 동의한 경우에만 ACCEPT_EULA=Y를 명시하세요." >&2
  echo "https://docs.isaacsim.omniverse.nvidia.com/5.1.0/common/NVIDIA_Omniverse_License_Agreement.html" >&2
  exit 2
fi
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  echo "bootstrap을 마친 Ubuntu GPU EC2 호스트에서 실행하세요." >&2; exit 2;
}
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd -- "$script_dir/../.." && pwd)"
runtime_dir=/opt/isaac-workshop
image=nvcr.io/nvidia/isaac-sim:5.1.0
docker_cmd=(sudo docker)
[[ $EUID -ne 0 ]] || docker_cmd=(docker)
[[ -d "$runtime_dir/output" ]] || {
  echo "먼저 bootstrap-host.sh install 및 재부팅 후 verify를 완료하세요." >&2; exit 1;
}

if [[ "$1" == --check ]]; then
  [[ $# -eq 1 ]] || { usage >&2; exit 2; }
  command_args=(/isaac-sim/isaac-sim.compatibility_check.sh --/app/quitAfter=10 --no-window)
else
  # Resolve symlinks and reject host paths that are outside the mounted repository.
  relative_script="$(python3 - "$project_dir" "$1" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
path = (root / sys.argv[2]).resolve()
if not path.is_file() or path.suffix != ".py" or root not in path.parents:
    raise SystemExit("저장소 안에 존재하는 .py 파일을 지정하세요.")
print(path.relative_to(root))
PY
  )"
  shift
  command_args=(/isaac-sim/python.sh "/workspace/$relative_script" "$@")
fi

"${docker_cmd[@]}" pull "$image"
"${docker_cmd[@]}" image inspect "$image" --format '{{json .RepoDigests}}'
echo "실행 결과의 호스트 경로: $runtime_dir/output"
# Bridge networking and no -p keep every container listener off the public host.
# IMDS hop limit 1 means AWS uploads must be made from the host, not this container.
exec "${docker_cmd[@]}" run --rm --init --name isaac-workshop \
  --gpus all --runtime=nvidia --user 1234:1234 \
  --cap-drop=ALL --security-opt=no-new-privileges:true \
  --shm-size=2g --log-opt max-size=10m --log-opt max-file=3 \
  --network bridge --entrypoint bash --workdir /workspace \
  -e ACCEPT_EULA=Y \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video,display \
  -e PYTHONUNBUFFERED=1 -e PYTHONDONTWRITEBYTECODE=1 \
  -e ISAAC_OUTPUT_DIR=/output -e ISAAC_ROBOT=turtlebot3_burger \
  --mount "type=bind,src=$project_dir,dst=/workspace,readonly" \
  --mount "type=bind,src=$runtime_dir/output,dst=/output" \
  --mount "type=bind,src=$runtime_dir/cache/main,dst=/isaac-sim/.cache" \
  --mount "type=bind,src=$runtime_dir/cache/computecache,dst=/isaac-sim/.nv/ComputeCache" \
  --mount "type=bind,src=$runtime_dir/logs,dst=/isaac-sim/.nvidia-omniverse/logs" \
  --mount "type=bind,src=$runtime_dir/config,dst=/isaac-sim/.nvidia-omniverse/config" \
  --mount "type=bind,src=$runtime_dir/data,dst=/isaac-sim/.local/share/ov/data" \
  --mount "type=bind,src=$runtime_dir/pkg,dst=/isaac-sim/.local/share/ov/pkg" \
  "$image" "${command_args[@]}"
