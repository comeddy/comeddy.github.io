# 로봇·센서 선택의 근거

확인일: 2026-09-09. NVIDIA 문서는 **Isaac Sim 5.1.0**으로 고정했다.
아래의 “확인”은 공식 문서·소스·USD 파일을 읽은 결과다. GPU 실행 및 실물 주행을
검증했다는 의미가 아니다.

## 결론

**TurtleBot3 Burger / Raspberry Pi 4 / Ubuntu 22.04 / ROS 2 Humble**을 유지한다.
Isaac Sim 5.1 공식 Burger 자산의 실제 바퀴 충돌 형상과 관절 위치를 내려받아 읽었으며,
ROBOTIS Burger URDF와 일치했다. 다른 로봇으로 바꾸거나 별도 유료 자산을 구매할 필요가 없다.
시뮬레이션에서 `/scan`을 ROS로 전송할 필요도 없다. 같은 전처리를 호출하여 데이터를
직접 저장하고, 실물에서만 ROS `LaserScan` → NumPy 정책 → `Twist`를 연결한다.

## 공식 자산: 이름뿐 아니라 형상도 확인

[NVIDIA 5.1 Robot Assets][assets]는 `Isaac Sim/Robots` 아래의 경로를
`Turtlebot/Turtlebot3/turtlebot3_burger.usd`로 명시한다. [설치 FAQ][faq]의
기본 asset root를 합친 실제 주소는 다음과 같으며 HTTP 200으로 내려받았다.

```text
https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Robots/Turtlebot/Turtlebot3/turtlebot3_burger.usd
```

실행 시에는 공식 `isaacsim.storage.native.get_assets_root_path()`와
`/Isaac/Robots/Turtlebot/Turtlebot3/turtlebot3_burger.usd`를 결합한다.
실제 파일이 없으면 오류로 종료한다. 다른 로봇이나 임의의 가상 스캔으로 대체하지 않는다.

자산의 root layer와 연결된 `configuration/*_physics.usd`, `*_base.usd`를
OpenUSD로 읽어 확인한 값은 다음과 같다.

| 항목 | 확인한 값 |
|---|---|
| 단위 / 위쪽 축 | `metersPerUnit=1`, `upAxis=Z` |
| 기본 prim / articulation root | `turtlebot3_burger`, 그 prim에 `PhysicsArticulationRootAPI` |
| 바퀴 관절 | `wheel_left_joint`, `wheel_right_joint` |
| 바퀴 collider | 실린더, 반지름 약 `0.033 m`, 폭 약 `0.018 m` |
| 관절 위치, `base_link` 기준 | 왼쪽 `(0, +0.080, 0.023)`, 오른쪽 `(0, -0.080, 0.023) m` |
| 윤거 | `0.160 m` |
| `base_link` 위치 | `base_footprint`보다 `0.010 m` 위 |
| `base_scan` 위치, `base_link` 기준 | `(-0.032, 0, 0.172) m`, 회전 없음 |
| 기본 자세의 스캔 높이 | `base_footprint`보다 약 `0.182 m` 위 |

**주의할 문서 불일치:** [NVIDIA 주행 튜토리얼][drive]의 예시 표에는 wheel radius가
`0.025`로 되어 있다. 해당 수치를 복사하지 않는다. 다운로드한 Burger USD와
[ROBOTIS Humble URDF][urdf]에서 공통으로 확인한 **0.033 m**를 사용한다.
주행 튜토리얼의 윤거 `0.16` 및 관절 이름은 일치한다.

아래 해시는 확인 당시 파일의 증거다. GPU 환경에서는 연결된 전체 자산이 정상적으로
로드되는지 다시 확인해야 한다.

| 파일 | SHA-256 |
|---|---|
| `turtlebot3_burger.usd` (4,503 bytes) | `5c01f82e5e0c9f8a62e93b9d3bc56104c5954948b2451b6bbf384233f0479af4` |
| `configuration/turtlebot3_burger_physics.usd` (6,501 bytes) | `c16c2ca571c7c45df130693aaf85c7bca0a438266e1793203b33372be3152871` |
| `configuration/turtlebot3_burger_base.usd` (11,127,819 bytes) | `2fbd71cae14ea6811790e382975375ae912e1383f605bce43dad291dbc730f85` |

자산을 직접 만들 필요가 생기면 [공식 TurtleBot URDF 가져오기 튜토리얼][import]
경로를 따른다. `turtlebot3_description/urdf/turtlebot3_burger.urdf`의 xacro
namespace를 전처리하고, movable base 및 두 바퀴 velocity drive를 설정한다.
ROBOTIS 저장소의 확인한 Humble 커밋은
`90a68bd2e3c61c12966779da89d8eeaec82730e9`이다. 임의로 만든 축소형 로봇을
사용할 때는 “Burger 복제 단순 모델”로 표기하고 공식 자산과 구분한다.

## 실행·센서·데이터 계약

공통 함수·CLI·학습 데이터 키는 [구현 계약](implementation-contract.md)을 따른다.
`observations`는 **미터 단위 Nx12**, `actions`는 **m/s와 rad/s의 Nx2**다.
정규화는 공통 코어가 담당하므로 시뮬레이터에서 미리 `/3.5` 하지 않는다.
입력 각도는 [ROS Humble LaserScan 정의][scan]대로 +X 전방이 0이고 +Z 기준 반시계다.
각 sector는 `[i·30°, (i+1)·30°)`이며 중심은 `(i+0.5)·30°`다.
전방은 sector 11과 0 사이에 있으므로 첫 번째 bin만 전방으로 취급하면 안 된다.

시뮬레이터는 공식 [standalone Python][standalone]의 `SimulationApp`과
[DifferentialController / WheeledRobot][controller]로 실행한다. 컨테이너의
`/isaac-sim/python.sh`를 사용하고, Kit·Isaac 관련 import보다 먼저
`SimulationApp`을 생성한다. NumPy 정책을 ROS와 분리하면 Python 버전 혼합도 피할 수 있다.
[NVIDIA ROS 설치 문서][ros]에 따르면 Isaac Sim 5.1은 Python 3.11을 사용하며,
Ubuntu 22.04의 일반 Humble Python 3.10 환경을 같은 프로세스에 섞어 source하면 안 된다.

센서는 [공식 PhysX raycast 예제][raycast]와 같은 scene query를 사용한다.
렌더링용 외형만 있는 장애물이 아니라 **충돌이 켜진 같은 USD 장애물**을 측정한다.
장애물은 바닥에서 **최소 0.50 m** 높이로 만들고, 약 0.182 m의 수평 스캔이
벽·상자를 관통하지 않는지 첫 미리보기와 알려진 거리 측정으로 확인한다.
자신의 LiDAR 케이스에 ray가 닿지 않도록 센서 케이스 collider는 별도로 제외한다.
바닥 아래나 케이스 내부에서 쏘아 얻은 0 거리 스캔을 정상 학습 데이터로 쓰지 않는다.

기본 모드는 headless이며 `--preview /output/preview.png`는
[공식 Camera API][camera]로 첫 에피소드의 RGB 이미지를 저장한다.
`--render`는 디스플레이가 준비된 로컬 Isaac Sim에서 사용할 선택 기능이다.
AWS 기본 실행은 화면 창이나 WebRTC를 요구하지 않는다.
데이터·CSV·미리보기·평가 JSON은 읽기 전용 `/workspace` 밖의 `/output`에 저장한다.

## 실제 장비 준비 근거

| 항목 | 공식 근거와 실습 적용 |
|---|---|
| SBC / 모델 | [ROBOTIS 사양][features]: Burger에 Raspberry Pi 4, OpenCR, 두 XL430 구동부 |
| OS / ROS | [SBC Setup의 Humble 절][sbc]: Ubuntu Server 22.04.5 64-bit (RPi 3/4/400), ROS 2 Humble ROS-Base 권장 |
| 로봇 소스 | `turtlebot3`의 `humble` branch. 반복 가능한 교육 이미지는 커밋도 고정 |
| Bringup | [공식 Bringup][bringup]: `export TURTLEBOT3_MODEL=burger`, `ros2 launch turtlebot3_bringup robot.launch.py` |
| 센서 선택 | 장착된 LDS-01/02/03에 맞게 `LDS_MODEL`과 드라이버 선택. 새 제품도 모델을 현장에서 확인 |
| ROS 연결 | 같은 `ROS_DOMAIN_ID`, 호환 RMW, 같은 LAN의 multicast. AWS까지 DDS를 연결할 필요 없음 |
| 기본 topics | `/scan`, `/cmd_vel`, `/odom`, `/joint_states`, `/tf` |
| 하드웨어 최대 속도 | Burger `0.22 m/s`, `2.84 rad/s`. 워크샵은 더 낮은 `0.12 m/s`, `0.6 rad/s` |

[확인한 Humble 노드 소스][node]에는 `Twist`와 `TwistStamped`를 다루는 코드가 있다.
패키지 설정·버전에 따라 실제 타입을 `ros2 topic type /cmd_vel`로 확인한다.
워크샵 코드는 `geometry_msgs/msg/Twist`를 계약으로 사용한다.
실물 `/scan`의 `frame_id`, 전방 방향, 범위, QoS, 주기는 현장에서 확인한다.

## OpenCR heartbeat는 정책 명령 만료 검사가 아니다

**확인한 ROS 2 펌웨어에는 독립적인 `cmd_vel` 수신 시각 만료 검사가 없다.**
[OpenCR 소스][opencr] 커밋 `68ec75d8a400949580ecf263e0105ea9743b878e`의
`turtlebot3_ros2/src/turtlebot3/turtlebot3.cpp`를 확인했다.

| 소스 위치 | 확인한 동작 |
|---|---|
| 815–820행 | linear/angular 명령을 `goal_velocity_from_cmd`에 저장. 수신 시각 갱신 없음 |
| 618–623행 | `get_connection_state_with_ros2_node()==false`이면 명령을 0으로 초기화 |
| 943–965행 | 연결 상태는 `heart_beat`의 변화에 의존. 명령 수신 시각은 검사하지 않음 |
| 107행 | `HEARTBEAT_TIMEOUT_MS=500`은 통신 heartbeat의 상수이며 정책 명령 만료 시간이 아님 |
| 956행 | `debug_mode==true`도 연결을 유지하므로 실제 설정도 확인 필요 |

bringup의 heartbeat가 계속되는 동안 정책 프로세스만 강제 종료되면 마지막 속도
명령이 남을 수 있다. Python 노드의 `finally`·watchdog은 `SIGKILL` 후 실행되지 않는다.
**“정책 종료 후 1초 안에 자동 정지” 같은 보장을 이 소스로부터 추론하면 안 된다.**
실제 플래시된 바이너리가 이 소스 커밋과 같은지는 별도 확인 사항이다.

실물 주행에는 명령 나이를 검사하는 독립 제어 계층이 필요하다. 권장 보완 위치는
bringup의 모터 출력 직전 또는 OpenCR 펌웨어다. 별도 ROS supervisor는 정책 종료를
처리할 수 있지만, supervisor 자체가 종료되고 bringup은 살아 있는 고장은 별도로 남는다.
최종 출력 계층에 만료 검사가 없다면 shadow mode와 바퀴를 든 시험까지만 진행한다.
이를 보완하기 위해 이 저장소는
[bringup 패치 소스](../static/code/device/apply_bringup_watchdog.py)를 제공한다.
실행할 때는 워크샵 전체 ZIP을 압축 해제하여 `.py`와
`workshop_cmd_vel_watchdog.hpp`를 같은 폴더에 유지해야 한다.
지정한 TurtleBot3 Humble 소스에만 적용하며, 명령 수신 후 500ms가 지나면 heartbeat
전송을 중단한다. 설치·재빌드·재시작은 [로봇 설치 부록](device-setup.md)에 포함한다.
이 보완과 실제 펌웨어의 합산 정지 시간은 별도 실물 시험 대상이다.
바퀴를 든 상태에서 정책 `SIGKILL`, supervisor 사용 시 그 프로세스의 종료,
bringup 종료, USB 연결 단절을 **각각** 시험하고 실제 정지 여부·시간을 측정한다.
RC100·보드 버튼 등 다른 명령 입력은 해당 시험에서 비활성화한다.

## 정확도와 재현성의 경계

- 공식 Burger의 articulation·바퀴 치수를 사용하지만 마찰, caster 접촉, 질량,
  모터 지연, 배터리 상태를 실제 장비에 맞춰 보정한 digital twin은 아니다.
- 센서는 이상적 수평 2D 거리 센서다. 광학 반사, 검은 표면·유리, 회전 중
  시간차, 누락값과 잡음을 완전히 재현하지 않는다. 센서 케이스의 자체 충돌도 제외한다.
- **0.05~3.5 m는 모델 입력 범위**다. 이를 실제 LDS 사양이라고 설명하지 않는다.
  [LDS-02 공식 사양][lds]은 검출 거리 **0.16~8 m**, 스캔 주파수 **5 Hz 이상**이다.
  실제 입력은 메시지의 `range_min/range_max`를 공통 전처리에 전달한다.
- 2D 스캔보다 낮은 물체·낙하 지점·계단, 움직이는 사람, 경사로는 기본 과제 밖이다.
  가상 경기장은 불투명한 정적 상자와 벽, 평평한 바닥으로 제한한다.
- seed는 배치·초기 자세와 데이터 분할을 재현한다. 다른 GPU·드라이버·PhysX
  버전까지 바이트 단위로 동일한 동역학 결과를 보장하지 않는다.
- 평가는 collision/near miss뿐 아니라 실제 이동 거리·정지 비율·안전 개입을
  같이 본다. 항상 정지하는 정책을 장애물 회피 성공으로 판정하지 않는다.
- 실물에서는 독립 정지 guard와 watchdog을 항상 적용한다. 모방학습 결과가
  안전 기능이나 실물 주행 검증을 대체하지 않는다.

[assets]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html
[faq]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_faq.html
[import]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/ros2_tutorials/tutorial_ros2_turtlebot.html
[drive]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/ros2_tutorials/tutorial_ros2_drive_turtlebot.html
[urdf]: https://github.com/ROBOTIS-GIT/turtlebot3/blob/90a68bd2e3c61c12966779da89d8eeaec82730e9/turtlebot3_description/urdf/turtlebot3_burger.urdf
[node]: https://github.com/ROBOTIS-GIT/turtlebot3/blob/90a68bd2e3c61c12966779da89d8eeaec82730e9/turtlebot3_node/src/turtlebot3.cpp
[standalone]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/python_scripting/manual_standalone_python.html
[controller]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/robot_simulation/mobile_robot_controllers.html
[raycast]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/python_scripting/environment_setup.html#do-raycast-test
[camera]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/sensors/isaacsim_sensors_camera.html
[ros]: https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_ros.html
[scan]: https://docs.ros.org/en/humble/p/sensor_msgs/msg/LaserScan.html
[features]: https://emanual.robotis.com/docs/en/platform/turtlebot3/features/
[sbc]: https://emanual.robotis.com/docs/en/platform/turtlebot3/sbc_setup/
[bringup]: https://emanual.robotis.com/docs/en/platform/turtlebot3/bringup/
[lds]: https://emanual.robotis.com/docs/en/platform/turtlebot3/appendix_lds_02/
[opencr]: https://github.com/ROBOTIS-GIT/OpenCR/blob/68ec75d8a400949580ecf263e0105ea9743b878e/arduino/opencr_arduino/opencr/libraries/turtlebot3_ros2/src/turtlebot3/turtlebot3.cpp
