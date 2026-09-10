# 공식 출처와 버전 선택

자료 확인일: **2026-09-09**. 실행 재현성을 위해 **Isaac Sim 5.1.0**을 선택했습니다.
이 버전이 최신 버전이라는 의미는 아닙니다.
웹 문서도 바뀔 수 있으므로 행사 운영자는 리허설 때 다시 확인합니다.

| 주제 | 공식 문서 | 워크샵에 반영한 내용 |
|---|---|---|
| Isaac Sim 요구사항 | [5.1 System Requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html) | Ubuntu, RTX 기능, RAM/VRAM, 드라이버 |
| AWS 실행 | [AWS Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_aws.html) | AWS GPU 환경과 네트워크 요구사항 |
| 컨테이너 | [Container Installation](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_container.html) | 5.1.0 이미지, UID 1234, 캐시, EULA |
| Python 실행 | [Standalone Python](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/python_scripting/manual_standalone_python.html) | SimulationApp 생성 순서와 종료 |
| 로봇 자산 | [Robot Assets](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html) | 실제 Burger USD 경로 |
| 차륜 제어 | [Mobile Robot Controllers](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/robot_simulation/mobile_robot_controllers.html) | DifferentialController/WheeledRobot |
| 센서 raycast | [Environment Setup](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/python_scripting/environment_setup.html#do-raycast-test) | 충돌 장면에서 실제 거리 조회 |
| GPU 인스턴스 | [Amazon EC2 G6](https://aws.amazon.com/ec2/instance-types/g6/) | g6.4xlarge, 16 vCPU, 64GiB, L4 24GB |
| NVIDIA 드라이버 | [Ubuntu Driver Installation](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/ubuntu.html) | 공식 저장소, 커널 헤더, R580 |
| 컨테이너 런타임 | [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) | Docker GPU runtime 설정 |
| ROS 2 설치 | [Humble Ubuntu deb](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) | Ubuntu 22.04, ROS-Base, apt source 패키지 |
| LaserScan 계약 | [sensor_msgs/LaserScan](https://docs.ros.org/en/humble/p/sensor_msgs/msg/LaserScan.html) | 미터, 각도 0, 반시계, 범위 |
| 센서 QoS | [ROS 2 QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html) | best-effort 센서 구독 |
| Pi 설치 | [ROBOTIS SBC Setup](https://emanual.robotis.com/docs/en/platform/turtlebot3/sbc_setup/) | Humble 탭, Pi4, LDS 모델 |
| OpenCR | [ROBOTIS OpenCR Setup](https://emanual.robotis.com/docs/en/platform/turtlebot3/opencr_setup/) | Burger ROS2 펌웨어, 보드 테스트 버튼 |
| 실제 로봇 실행 | [ROBOTIS Bringup](https://emanual.robotis.com/docs/en/platform/turtlebot3/bringup/) | robot.launch.py, topics, ROS 환경 |
| 하드웨어 | [TurtleBot3 Features](https://emanual.robotis.com/docs/en/platform/turtlebot3/features/) | Burger 구성과 속도 |
| LDS 센서 | [LDS-02](https://emanual.robotis.com/docs/en/platform/turtlebot3/appendix_lds_02/) | 실제 센서 범위·주기와 모델 입력 범위 구분 |
| 비용 | [AWS Pricing Calculator](https://calculator.aws/) | 리전별 최신 비용 산정 |

## 선택의 근거와 주의한 차이

- 공식 AWS 문서의 현재 예제는 Marketplace workstation과 다른 GPU 인스턴스를
  제시합니다. 이 교재의 plain Ubuntu + g6.4xlarge는 소규모 실습을 위한 선택이며
  NVIDIA가 이 저장소 전체를 검증했다는 의미가 아닙니다.
- NVIDIA 주행 튜토리얼의 바퀴 반지름 예시와 Burger USD가 달라, 실제 USD와
  ROBOTIS URDF가 일치하는 **0.033m / 윤거 0.160m**를 사용합니다.
- 모델의 최대 입력 거리 3.5m는 학습 계약입니다. LDS-02 하드웨어 최대 검출 거리는
  별도이며 실제 메시지의 range_min/range_max를 전처리에 전달합니다.
- 시뮬레이터에 ROS 2를 설치하지 않습니다. Isaac Sim Python과 Pi의 Humble Python을
  같은 프로세스에 섞는 문제를 피하고 파일 기반으로 연결합니다.
- 기본 모델은 모방학습입니다. Isaac Lab, 강화학습, VLA, ROS Nav2를 구현했다고
  표시하지 않습니다.

상세한 파일 해시와 출처별 확인 내용은 [로봇 근거](robot-evidence.md)와
[AWS 근거](aws-evidence.md)에 있습니다.

[교재 홈](../content/index.ko.md)
