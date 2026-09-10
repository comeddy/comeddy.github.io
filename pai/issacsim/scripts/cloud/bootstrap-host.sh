#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
GPU EC2 호스트에서 실행:
  sudo bash scripts/cloud/bootstrap-host.sh install
  sudo reboot
  sudo bash scripts/cloud/bootstrap-host.sh verify
Ubuntu Server 22.04 x86_64의 새 호스트 전용. Isaac Sim 이미지/EULA 처리는 하지 않습니다.
USAGE
}
mode="${1:-}"
case "$mode" in
  --help|-h) usage; exit 0 ;;
  install|verify) ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -eq 1 ]] || { usage >&2; exit 2; }
[[ $EUID -eq 0 ]] || { echo "sudo로 실행하세요." >&2; exit 2; }
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 && "$(uname -m)" == x86_64 ]] || {
  echo "Ubuntu 22.04 x86_64만 지원합니다." >&2; exit 2;
}
state_dir=/var/lib/isaac-workshop
runtime_dir=/opt/isaac-workshop

if [[ "$mode" == verify ]]; then
  [[ -f "$state_dir/install-boot-id" ]] || {
    echo "먼저 install을 실행하세요." >&2; exit 1;
  }
  if [[ "$(cat "$state_dir/install-boot-id")" == "$(cat /proc/sys/kernel/random/boot_id)" ]]; then
    echo "드라이버 설치 이후 sudo reboot가 필요합니다." >&2
    exit 1
  fi
  nvidia-smi
  driver="$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1)"
  [[ "$driver" == 580.* ]] && dpkg --compare-versions "$driver" ge 580.65.06 || {
    echo "기대 드라이버는 R580, 580.65.06 이상입니다. 실제: $driver" >&2; exit 1;
  }
  systemctl is-active --quiet docker
  docker info --format '{{json .Runtimes}}'
  # An Ubuntu image checks device injection without accepting the Isaac Sim EULA.
  docker run --rm --runtime=nvidia --gpus all \
    --cap-drop=ALL --security-opt=no-new-privileges:true ubuntu:22.04 nvidia-smi
  if systemctl is-active --quiet amazon-ssm-agent; then
    echo "SSM Agent: active"
  else
    systemctl is-active snap.amazon-ssm-agent.amazon-ssm-agent.service
  fi
  df -h /
  echo "호스트 확인 완료. Isaac Sim 호환성 검사는 EULA 확인 후 run-headless.sh --check로 별도 실행하세요."
  exit 0
fi

if command -v cloud-init >/dev/null; then
  cloud-init status --wait
fi
if [[ -x /usr/bin/nvidia-uninstall ]]; then
  echo ".run 방식 NVIDIA 드라이버가 감지되었습니다. 기존 설치와 혼합하지 말고 새 Ubuntu AMI를 사용하세요." >&2
  exit 1
fi
for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
  if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q '^install ok installed$'; then
    echo "충돌 가능 패키지 $package 감지. 새 Ubuntu AMI에서 실행하세요." >&2
    exit 1
  fi
done
export DEBIAN_FRONTEND=noninteractive
apt-get -o DPkg::Lock::Timeout=300 update
apt-get -o DPkg::Lock::Timeout=300 install -y --no-install-recommends \
  ca-certificates curl gnupg build-essential dkms "linux-headers-$(uname -r)" \
  libvulkan1 vulkan-tools pciutils awscli python3
if ! lspci -d 10de: | grep -q .; then
  echo "NVIDIA PCI 장치가 없습니다. g6.4xlarge인지 확인하세요." >&2
  exit 1
fi

scratch_dir="$(mktemp -d)"
trap 'rm -rf "$scratch_dir"' EXIT
# NVIDIA's official CUDA repository keyring, verified against Packages.gz.
curl --fail --silent --show-error --location --retry 3 \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb \
  -o "$scratch_dir/cuda-keyring.deb"
printf '%s  %s\n' d93190d50b98ad4699ff40f4f7af50f16a76dac3bb8da1eaaf366d47898ff8df \
  "$scratch_dir/cuda-keyring.deb" | sha256sum --check -
dpkg -i "$scratch_dir/cuda-keyring.deb"
printf 'blacklist nouveau\noptions nouveau modeset=0\n' > /etc/modprobe.d/isaac-workshop-nouveau.conf
update-initramfs -u
apt-get -o DPkg::Lock::Timeout=300 update
apt-get -o DPkg::Lock::Timeout=300 install -y nvidia-driver-pinning-580
apt-get -o DPkg::Lock::Timeout=300 install -y cuda-drivers-580

install -m 0755 -d /etc/apt/keyrings
curl --fail --silent --show-error --location --retry 3 \
  https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
printf '%s\n' \
  'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu jammy stable' \
  > /etc/apt/sources.list.d/docker.list
curl --fail --silent --show-error --location --retry 3 \
  https://nvidia.github.io/libnvidia-container/gpgkey -o "$scratch_dir/container-toolkit.key"
gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  "$scratch_dir/container-toolkit.key"
curl --fail --silent --show-error --location --retry 3 \
  https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  -o "$scratch_dir/container-toolkit.list"
sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  "$scratch_dir/container-toolkit.list" > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get -o DPkg::Lock::Timeout=300 update
apt-get -o DPkg::Lock::Timeout=300 install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
  nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl enable docker
systemctl restart docker

install -d -m 0755 "$runtime_dir" "$state_dir"
for path in cache/main/ov cache/main/warp cache/computecache config data/documents data/Kit logs pkg output; do
  install -d -o 1234 -g 1234 -m 0755 "$runtime_dir/$path"
done
# Parent cache/data paths are also bind-mounted into the non-root container.
chown 1234:1234 "$runtime_dir/cache/main" "$runtime_dir/data"
dpkg-query -W cuda-drivers-580 nvidia-driver-pinning-580 docker-ce nvidia-container-toolkit \
  > "$runtime_dir/installed-packages.txt"
cat /proc/sys/kernel/random/boot_id > "$state_dir/install-boot-id"
echo "설치 완료. 로그: $runtime_dir/installed-packages.txt"
echo "이제 sudo reboot 후 재접속하여 bootstrap-host.sh verify를 실행하세요."
