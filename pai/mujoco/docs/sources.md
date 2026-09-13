# 공식 자료와 버전

학습·런타임 자료 확인 기준은 2026-09-09이며, 공식 온라인 시뮬레이터 메타데이터는 2026-09-10에 추가 확인했습니다. 이동하는 `main`/`develop` 대신 아래 커밋의 코드를 기준으로 명령을 작성했습니다. 온라인 Space는 제공자가 갱신하며 학습 명령의 고정 버전과 별개입니다. 교재 제작 중 실제 GPU/로봇에서 실행하지 않은 단계는 검증 기록에 별도로 표시합니다.

| 자료 | 확인한 내용 |
|---|---|
| [Microduck 제품](https://pollen-robotics.com/microduck) | 제품 정체, 제조사, 구입·배송 확인 경로 |
| [공식 온라인 Microduck 시뮬레이터](https://huggingface.co/spaces/pollen-robotics/microduck-simulator) | Pollen Robotics가 제공하는 브라우저 데모와 임베드 실패 시 직접 접속 경로 |
| [공식 Space 메타데이터 API](https://huggingface.co/api/spaces/pollen-robotics/microduck-simulator) | `sdk: docker`, `runtime.stage: RUNNING`, 공식 앱 호스트 `https://pollen-robotics-microduck-simulator.hf.space` |
| [공식 학습 README](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/README.md) | mjlab·MuJoCo Warp·PPO, 61→14 인터페이스, 모델 이용 조건 |
| [공식 Python 설정](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/pyproject.toml) | Python 3.12, mjlab 1.3.0, Torch/warp/BAM 의존성 |
| [보행 환경 설정](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py) | 기본 태스크, projected gravity, 정규화, PPO 설정·관절 선택 |
| [공식 exporter](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/src/mjlab_microduck/export.py) | `--checkpoint-file`, `--onnx-file`, `--num-envs`, 정규화 포함 공식 내보내기 |
| [공식 CPU ONNX 재생](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/scripts/infer_policy.py) | `--walking`, `--new-cmd-obs`, GUI 키보드, BAM 경로 |
| [mjlab 1.3.0 train](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/scripts/train.py) | 학습 CLI, seed, NaN guard, 실행 디렉터리 |
| [mjlab RL 설정](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/rl/config.py) | `--agent.logger tensorboard`, max iterations, save interval |
| [mjlab play](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/scripts/play.py) | zero policy/체크포인트 재생, Viser 뷰어 |
| [실물 명령 치트시트](https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/docs/robot/cheatsheet.md) | health, policy list/load/reset, init, relax, 게임패드 의미 |
| [실물 정책 manifest](https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/docs/policy-manifest.md) | 모델 API·관측·출력 크기, policy slot |
| [공식 런타임 시뮬레이터](https://github.com/pollen-robotics/microduck/blob/5620aa214e6e304eec00d5c376ac81d3001fb7a3/docs/robot/simulation.md) | 별도 심화 과정 `duck-sim`; 하드웨어 드라이버를 재현하지 않는 한계 |
| [AWS DLAMI 안내](https://docs.aws.amazon.com/dlami/latest/devguide/what-is-dlami.html) | GPU 학습용 AMI 선택 |
| [Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html) | SSM 접속, 로컬 plugin·IAM 전제 |
| [SSM 포트 전달](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html#sessions-start-port-forwarding) | 뷰어 접속에 인바운드 포트가 필요하지 않은 방식 |
| [EC2 G6](https://aws.amazon.com/ec2/instance-types/g6/) | L4 GPU 기반 인스턴스 |

Space 메타데이터 스냅샷의 커밋은 `e81974b932c7ca1819843b7bb3dcd42e2993e98e`입니다. 조사 원본은 워크샵 루트 기준 `../.microduck-workshop-research/hf-simulator-info.json`에 보관하며 교재 ZIP에는 포함하지 않습니다. 이 기록은 조회 당시 호스트·서비스 상태의 근거이며, 실제 iframe 렌더링 성공이나 워크샵 학습 성공의 증거는 아닙니다. 실제 브라우저 검증 범위는 [검증 기록](verification.md)을 따릅니다.

온라인 데모는 인터넷과 제공자 서비스 가용성에 의존하며 내 AWS 학습·체크포인트·실물 로봇 연결과 별개입니다. 교재는 앱을 임베드·링크하고 메시·가중치·사진을 재배포하지 않습니다. 공식 Space의 공개·연결 여부로 상업 이용권이나 모델 NC 조건 해소를 판단하지 않으며, 다운로드·학습 전 [자산 이용 조건](asset-licensing.md) 확인을 유지합니다.

라이선스 원문·정확한 파일 해시는 [라이선스 근거 JSON](licensing-evidence.json)에 있습니다. 커밋을 업데이트하면 설치뿐 아니라 관측 순서·행동 스케일·시뮬레이터·exporter·실물 로더를 함께 다시 검증해야 합니다.
