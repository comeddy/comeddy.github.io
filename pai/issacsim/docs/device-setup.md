# 부록: 빈 microSD부터 로봇 준비하기

사전 준비용입니다. 이미 Humble bringup이 되는 로봇은 교재 모듈 7로 돌아가세요.
아래 명령은 별도 표시가 없으면 **Raspberry Pi의 Ubuntu 터미널**에서 실행합니다.
배터리만으로 장시간 설치하지 말고 제조사가 지정한 안정적인 전원을 사용합니다.

## 1. 조립과 OS

1. [ROBOTIS 조립 가이드](https://emanual.robotis.com/docs/en/platform/turtlebot3/hardware_setup/)의
   Burger 순서로 조립합니다. 케이블을 연결할 때는 전원을 끕니다.
2. 노트북에 [Raspberry Pi Imager](https://www.raspberrypi.com/software/)를 설치합니다.
3. 장비를 Raspberry Pi 4로 선택하고 **Ubuntu Server 22.04 LTS 64-bit**를 선택합니다.
   메뉴에 없다면 Ubuntu의 공식 Raspberry Pi용 22.04 이미지를 Custom image로 선택합니다.
4. 저장 장치가 실습용 microSD인지 확인합니다. 쓰기 작업은 선택한 카드 내용을 지웁니다.
5. 사용자명, 새 암호, Wi-Fi SSID/암호, 국가, SSH를 설정합니다.
6. 기록과 검증이 끝나면 카드를 Pi에 꽂아 부팅합니다.
7. 공유기의 연결 기기 목록 또는 Pi의 모니터에서 `hostname -I`로 IP를 찾습니다.
8. 노트북에서 `ssh <사용자명>@<로봇 IP>`로 접속합니다.

확인:

```bash
cat /etc/os-release
uname -m
```

`22.04`와 `aarch64`가 보여야 합니다.
아래부터는 Raspberry Pi OS나 Ubuntu 24.04에서 실행하지 않습니다.

**내 노트북**의 워크샵 폴더 상위 디렉터리에서 교재와 코드를 먼저 Pi에 복사합니다.

```bash
scp -r physical-ai-isaac-aws "<Pi 사용자명>@<Pi IP>:~/"
```

복사 후 **로봇** 터미널로 돌아갑니다.

## 2. ROS 2 Humble 설치

[ROS 공식 설치 문서](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)를
기준으로 한 ROS-Base 설치입니다.
이미 ROS가 설치되어 있으면 저장소를 중복 추가하지 마세요.

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y locales software-properties-common curl git python3
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository -y universe
curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
  -o /tmp/ros-apt-source-release.json
export ROS_APT_SOURCE_VERSION="$(python3 -c 'import json; print(json.load(open("/tmp/ros-apt-source-release.json"))["tag_name"])')"
curl -fL \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.jammy_all.deb" \
  -o /tmp/ros2-apt-source.deb
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install -y ros-humble-ros-base ros-dev-tools python3-numpy
source /opt/ros/humble/setup.bash
ros2 --help
```

최신 apt source 패키지 버전만 조회합니다. ROS 배포판은 계속 Humble로 유지합니다.
`apt upgrade`에 재부팅 안내가 있으면 재부팅한 뒤 다음 단계로 진행하세요.

## 3. TurtleBot3 드라이버

[ROBOTIS SBC Setup의 Humble 탭](https://emanual.robotis.com/docs/en/platform/turtlebot3/sbc_setup/)을
기준으로 합니다. 아래는 새 `~/turtlebot3_ws`를 만드는 경우입니다.
이미 존재하면 기존 설치를 점검하고 clone을 중복 실행하지 마세요.

```bash
sudo apt install -y python3-argcomplete python3-colcon-common-extensions \
  libboost-system-dev build-essential libudev-dev \
  ros-humble-hls-lfcd-lds-driver ros-humble-turtlebot3-msgs \
  ros-humble-dynamixel-sdk ros-humble-xacro
mkdir -p ~/turtlebot3_ws/src
cd ~/turtlebot3_ws/src
git clone -b humble https://github.com/ROBOTIS-GIT/turtlebot3.git
git -C turtlebot3 checkout 90a68bd2e3c61c12966779da89d8eeaec82730e9
git clone -b humble https://github.com/ROBOTIS-GIT/ld08_driver.git
git clone -b humble https://github.com/ROBOTIS-GIT/coin_d4_driver.git
python3 ~/physical-ai-isaac-aws/static/code/device/apply_bringup_watchdog.py \
  --workspace ~/turtlebot3_ws
cd ~/turtlebot3_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --parallel-workers 1 \
  --packages-skip turtlebot3_cartographer turtlebot3_navigation2 turtlebot3
source ~/turtlebot3_ws/install/setup.bash
ros2 pkg prefix turtlebot3_bringup
```

2GB Pi는 메모리가 부족할 수 있습니다. 공식 SBC 문서의 swap 준비를 먼저 적용하세요.
빌드는 1시간 이상 걸릴 수 있습니다.
교육에서는 지도 작성과 Nav2를 사용하지 않으므로 해당 패키지 빌드를 건너뜁니다.
이들을 의존성으로 묶는 `turtlebot3` 메타패키지도 함께 제외합니다.
실제 실행에 필요한 `turtlebot3_node`와 `turtlebot3_bringup`은 빌드됩니다.

워크샵 패치는 정책 명령을 0.5초 이상 받지 못하면 bringup의 heartbeat를 중단합니다.
이어 OpenCR의 통신 timeout이 작동하도록 만드는 보완입니다.
확인한 기본 펌웨어에는 정책 명령만 별도로 만료시키는 로직이 없어서 필요한 단계입니다.
패치는 지정한 소스의 SHA-256을 확인하고 원본을 보관하며, 다른 변경이 있으면 중단합니다.
**수정된 bringup과 실제 펌웨어의 합산 정지 시간은 모듈 8에서 반드시 측정합니다.**

USB 권한 규칙을 설치합니다.

```bash
export TB3_PREFIX="$(ros2 pkg prefix turtlebot3_bringup)"
sudo cp "$TB3_PREFIX/share/turtlebot3_bringup/script/99-turtlebot3-cdc.rules" \
  /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## 4. OpenCR 펌웨어

OpenCR은 모터를 제어하는 보드입니다. **Burger용 ROS 2 펌웨어**를 사용합니다.
이미 설치된 장비는 버전을 확인하고 불필요하게 다시 굽지 마세요.
아래는 [공식 OpenCR Setup](https://emanual.robotis.com/docs/en/platform/turtlebot3/opencr_setup/)의
loader 방식입니다. 모터 전원은 제조사 지침에 맞게 준비하고 바퀴를 띄웁니다.

```bash
sudo dpkg --add-architecture armhf
sudo apt update
sudo apt install -y libc6:armhf
mkdir -p ~/opencr-workshop
cd ~/opencr-workshop
curl -fL \
  https://github.com/ROBOTIS-GIT/OpenCR-Binaries/raw/master/turtlebot3/ROS2/latest/opencr_update.tar.bz2 \
  -o opencr_update.tar.bz2
sha256sum opencr_update.tar.bz2
tar -xvf opencr_update.tar.bz2
export OPENCR_PORT=/dev/ttyACM0
export OPENCR_MODEL=burger
cd opencr_update
./update.sh "$OPENCR_PORT" "$OPENCR_MODEL.opencr"
```

파일의 SHA-256과 설치 날짜를 운영 기록에 보관하세요.
`latest` URL은 변경될 수 있어 행사 운영자는 리허설에 사용한 파일을 별도로 보관합니다.
실패하면 공식 문서의 recovery mode를 확인합니다.
OpenCR의 **PUSH SW1/SW2는 비상 정지 버튼이 아니라 주행 테스트 버튼**입니다.

## 5. 센서 모델과 실행 환경

LDS 라벨을 확인합니다. 다음 중 **실제 모델 한 가지**를 선택하세요.

```bash
export LDS_MODEL=LDS-02
```

LDS-01 또는 LDS-03이면 위 값을 해당 모델로 바꿉니다.
모든 ROS 터미널에서 사용할 환경을 기록합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
```

이 워크샵은 ROS 프로그램을 모두 Pi에서 실행하므로 localhost 통신으로 제한할 수 있습니다.
노트북은 SSH 화면만 사용합니다. Pi 밖의 RViz에 연결하려면 별도 네트워크 설정이 필요합니다.

**완료 확인:** 명령 만료 패치를 포함한 빌드, `ros2 pkg prefix turtlebot3_bringup` 성공, OpenCR 업로드 성공,
실제 LDS 모델 확인까지 끝났습니다. [모듈 7](../content/module7-device/index.ko.md)로 이동합니다.
