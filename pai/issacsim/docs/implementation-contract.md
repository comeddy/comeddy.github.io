# 구현 계약

이 파일은 워크샵 코드와 실습 문서의 공통 인터페이스다.

- 워크샵 기본값: 한국어, 사전 준비 별도 + 하루 7시간, 개인 AWS 계정.
- 버전 기준: Isaac Sim 5.1.0 컨테이너, Ubuntu 22.04 x86_64 EC2,
  TurtleBot3 Burger / Raspberry Pi 4 / Ubuntu 22.04 arm64 / ROS 2 Humble.
- 과제: 평평한 실내의 낮은 속도 장애물 회피. 지도 작성·목적지 탐색·물체 집기와 구분한다.
- 학습: Isaac Sim에서 규칙 기반 교사가 만든 데이터를 작은 NumPy 신경망에 모방 학습.
  Isaac Lab 강화학습은 선택 확장이다. 이 기본 과정을 강화학습이라고 부르지 않는다.
- 클라우드가 학습하고 로봇이 로컬 추론한다. 인터넷으로 실시간 속도 명령을 보내지 않는다.

## Python 인터페이스

`static/code/workshop_core.py`:

- `NUM_SECTORS=12`, `MAX_RANGE=3.5`, `MAX_LINEAR=0.12`, `MAX_ANGULAR=0.6`.
- `scan_to_sectors(ranges, angle_min, angle_increment, range_min, range_max)`
  returns `(sectors_metres: np.ndarray shape(12,), valid: bool)`.
- LaserScan 표준: 0 rad 전방, 양의 각도 반시계, bin `floor((angle % 2π)/(2π/12))`.
  bin0=0..30°, bin11=330..360°. 모든 bin이 있어야 유효하다.
- 유한 거리의 최솟값을 사용. `+inf`는 장애물 없음으로 최대거리로 변환 가능하나,
  유한 측정이 전혀 없거나 각도/거리 스펙이 잘못된 scan은 무효다.
  NaN·음수·범위 밖 등 무효 샘플은 해당 bin을 가리지 않도록 보수적으로 처리.
- `expert_action(sectors)` returns `(linear_mps, angular_radps)`.
- `safe_action(sectors, requested, scan_age, valid=True)` returns `(linear, angular)`;
  무효·오래된 scan, 전방 근접 장애물은 영속 정지, 유한값·속도 제한 검사.
- `Policy.load(path)` / `policy.predict(sectors)` returns `(linear, angular)`.
- Input normalization is clipped sectors / MAX_RANGE, identical in train/sim/device.
- Model uses NumPy `.npz`, `allow_pickle=False`, schema/version validation.

`static/code/train.py` CLI:

```
python train.py --data artifacts/dataset.npz --output artifacts/policy.npz
```

Dataset `.npz` keys: `observations` Nx12 metres, `actions` Nx2 physical units,
`episodes` N integer IDs. Training/validation split by episode, not adjacent rows.
Model metrics saved beside output as `metrics.json`.

`static/code/sim/run_sim.py` CLI:

```
/isaac-sim/python.sh /workspace/static/code/sim/run_sim.py --mode collect --episodes 30 --steps 600 --seed 42 --output /output/dataset.npz
/isaac-sim/python.sh /workspace/static/code/sim/run_sim.py --mode evaluate --episodes 5 --steps 600 --seed 900 --policy /output/policy.npz --output /output/evaluation.json
```

Simulator directly calls common core functions and exports actual simulated scan data.
Evaluation uses unseen seeds and safety guard, reporting collisions/near misses, progress,
and intervention rate separately so a stopped robot cannot count as successful avoidance.

`static/code/device/ros_policy_node.py`:

```
python3 ros_policy_node.py --model ~/physical-ai-isaac-aws/artifacts/policy.npz
python3 ros_policy_node.py --model ~/physical-ai-isaac-aws/artifacts/policy.npz --arm
```

Default shadow mode publishes only `/workshop/cmd_vel_preview`. `--arm` explicitly
enables `/cmd_vel` output; no auto-start service. ROS QoS matches best-effort LaserScan.
Watchdog timer checks monotonic scan receipt age independent of callbacks and publishes
zero on timeout, exceptions and shutdown. Re-arm required after fault is preferred.
Single `/cmd_vel` publisher required. Manual physical stop and OpenCR communication
watchdog must be checked before floor driving. Module 6 quantitative and proximity/progress
review gates must also pass; the current NO-GO model is excluded from floor driving.
No autonomous recovery after a fault.

## 검증 경계

2026-09-09에 로컬 테스트·문서·CloudFormation 검사와 실제 AWS 배포, Isaac Sim 실행,
데이터 수집·학습·평가를 수행했다. GPU 렌더링과 CPU PhysX를 사용했다.
Linux ARM의 ROS 2 빌드·DDS 및 실제 모델 그림자 실행도 검증했다.
실물 센서·OpenCR·모터 시험은 수행하지 않았으며, 현재 모델의 바닥 주행은 NO-GO다.
조건·근거·미실행 범위는 [검증 기록](verification.md)을 따른다.
