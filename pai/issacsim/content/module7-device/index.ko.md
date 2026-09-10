---
title: "7. 실제 로봇에 배포"
weight: 80
---

# 7. 모델이 실제 로봇 안으로 들어갑니다

**시간: 60분 · 실행 위치: 내 노트북 → 로봇**

이 단계의 시작 조건은 Ubuntu 22.04, ROS 2 Humble, Burger 드라이버와 OpenCR 준비입니다.
새 장비라면 [빈 microSD부터 준비하기](../../docs/device-setup.md)를 전날 완료하세요.
이미 준비된 로봇도 이 교재의 **bringup 명령 만료 패치**가 필요합니다.
아래 센서 확인은 바퀴를 띄운 상태에서 진행하고, 패치 설치·재빌드 전에는 모터를 구동하지 않습니다.

## 7-1. 로봇 접속

**내 노트북**에서 실제 계정명과 IP를 넣습니다.

```bash
export ROBOT_USER="<Pi 사용자명>"
export ROBOT_IP="<Pi의 사설 IP>"
ssh "$ROBOT_USER@$ROBOT_IP"
```

**로봇**에서 아래 환경을 설정합니다. 이후 새 로봇 터미널을 열 때도 같은 설정을 적용하세요.
`LDS_MODEL`은 센서 라벨에 맞게 LDS-01/02/03 중 하나를 선택합니다.

```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
export LDS_MODEL=LDS-02
export ROS_DOMAIN_ID=30
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 launch turtlebot3_bringup robot.launch.py
```

이 터미널은 센서·모터 드라이버를 실행하므로 켜 둡니다.
`Succeeded to open the port`, 센서와 odometry 시작 로그를 확인합니다.
전원 스위치에 손이 닿도록 하고 로봇의 바퀴는 받침대로 띄워 둡니다.

## 7-2. 센서와 메시지 형식 확인

두 번째 **로봇** 터미널을 열어 위 환경 설정을 다시 적용한 뒤:

```bash
ros2 topic list
ros2 topic type /scan
ros2 topic type /cmd_vel
ros2 topic echo /scan --once --qos-reliability best_effort
ros2 topic info /cmd_vel --verbose
```

`/scan`은 `sensor_msgs/msg/LaserScan`, `/cmd_vel`은 `geometry_msgs/msg/Twist`여야 합니다.
Jazzy의 `TwistStamped` 환경은 이 코드의 기본 대상이 아닙니다.
현재 모터 명령 publisher는 0이어야 합니다. teleop/Nav2 등이 있으면 종료합니다.

상자를 앞·왼쪽·오른쪽에 한 곳씩 놓고 거리 변화가 해당 방향에 나타나는지 봅니다.
센서가 180도 돌아가 있으면 AI도 앞뒤를 반대로 이해합니다.

## 7-3. 모델과 실행 코드 전송

**내 노트북**에서 워크샵 폴더의 상위 디렉터리로 이동합니다.
폴더 안 `artifacts`에 모듈 5에서 받은 모델·SHA-256이 있는지 확인합니다.

```bash
scp -r physical-ai-isaac-aws "$ROBOT_USER@$ROBOT_IP:~/"
```

**로봇**에서 설치와 파일 무결성을 확인합니다.

```bash
sudo apt update
sudo apt install -y python3-numpy
cd ~/physical-ai-isaac-aws/artifacts
sha256sum -c policy.npz.sha256
cd ~/physical-ai-isaac-aws
PYTHONPATH=tests python3 -m unittest \
  test_policy.ScanTests test_policy.GuardTests \
  test_policy.ArtifactTests test_policy.EdgeControllerTests -v
```

`policy.npz: OK`가 나오고 테스트가 통과해야 합니다.
기본 추론에는 pip, PyTorch, CUDA, TensorRT가 필요하지 않습니다.
ROS가 인식되지 않는 별도 Python 가상환경 대신 Ubuntu의 `python3`를 사용하세요.
위 명령은 로봇에 필요한 추론·입력·정지 검사를 수행합니다. 모델 학습은 AWS에서 진행합니다.

## 7-4. 명령 만료 패치와 bringup 재시작

bringup 터미널을 `Ctrl+C`로 종료합니다. **로봇**에서:

```bash
cd ~/physical-ai-isaac-aws
python3 static/code/device/apply_bringup_watchdog.py --workspace ~/turtlebot3_ws
cd ~/turtlebot3_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select turtlebot3_node --parallel-workers 1
source ~/turtlebot3_ws/install/setup.bash
```

전날 부록에서 이미 설치한 경우 `Already patched and verified`가 나옵니다.
`unrecognized source`이면 지원하는 커밋과 다릅니다. 기존 수정본을 덮어쓰지 말고
[설치 부록](../../docs/device-setup.md)의 새 워크스페이스 준비 절차를 따릅니다.
검사만 하고 싶을 때는 `--check`를 붙입니다.

재빌드 후 모듈 7-1의 환경 설정과 `ros2 launch turtlebot3_bringup robot.launch.py`를
다시 실행합니다. 이전부터 실행 중인 프로세스에는 새 코드가 반영되지 않습니다.
이제 기본 펌웨어의 heartbeat만으로 남아 있던 정책 종료 상황을 보완할 수 있습니다.
실제 정지 시간은 다음 모듈에서 측정합니다.

## 7-5. 그림자 실행

bringup은 계속 켜 둡니다. 환경 설정을 마친 두 번째 로봇 터미널에서:

```bash
cd ~/physical-ai-isaac-aws
python3 static/code/device/ros_policy_node.py \
  --model artifacts/policy.npz
```

`--arm`이 없으므로 `/workshop/cmd_vel_preview`에만 결과를 보냅니다.
**모터에 전달하는 `/cmd_vel`에는 발행하지 않습니다.**

세 번째 로봇 터미널에서도 같은 환경을 적용하고:

```bash
ros2 topic echo /workshop/cmd_vel_preview
```

상자를 움직일 때 판단이 변하는지, 잘못된 입력에서는 0이 나오는지 봅니다.
문제를 수정하고 다시 실행할 때는 먼저 `Ctrl+C`로 기존 노드를 종료합니다.

**완료 확인:** 모델 무결성, 테스트, 명령 만료 패치·재빌드, 실제 센서 그림자 출력을 확인했습니다.

**기억할 점:** 배포 성공은 파일 복사뿐 아니라 실제 입력에서 추론이 되는 것까지 확인하는 일입니다.

[이전: 가상 검증](../module6-evaluation/index.ko.md) · [다음: 저속 주행](../module8-real-run/index.ko.md)
