# 제한된 Microduck 시뮬레이션 평가

`static/code/evaluate_sim.py`는 공식 환경에서 내보낸 ONNX 정책의 짧은 실행 증거를 기록합니다. 이 구현의 **실제 CUDA/MuJoCo Warp 통합 실행은 NOT EXECUTED(미실행)** 상태입니다. 공식 소스를 읽고 CPU 헬퍼 테스트를 수행한 사실이 GPU 시뮬레이션 성공이나 로봇 검증을 의미하지 않습니다.

실제 모델·메시 이용에는 [자산 이용 조건](asset-licensing.md)에 따른 사용자의 이용 자격 확인이 선행되어야 합니다. 이번 구현 작업에서는 그 자격을 대신 확인하지 않았으며 GPU·실물 로봇 실행, CUDA 설치, 모델·에셋 다운로드, AWS 작업을 수행하지 않았습니다. 스크립트에도 다운로드·설치·실물 제어 기능이 없습니다.

## 실행 명령

자격 확인 후 별도로 준비한 CUDA 환경과 로컬 공식 소스·에셋, 공식 내보내기 결과가 필요합니다. Python과 의존성은 공식 저장소의 고정 `uv.lock`을 따릅니다. 공식 내보내기 단계에서는 정확한 `--checkpoint-file`, 절대 경로의 `--onnx-file`, `--num-envs 1`을 사용합니다. 평가기는 이미 존재하는 ONNX 파일만 읽습니다.

```bash
python /ABS/WORKSHOP/static/code/evaluate_sim.py \
  --repo /ABS/microduck_rl \
  --policy /ABS/policy.onnx \
  --output /ABS/sim-evidence \
  --seconds 10 --seeds 900,901,902 --vx 0.1
```

위의 절대 경로를 실제 경로로 바꾸고, 공식 환경의 Python으로 실행하세요. `--output`은 새 디렉터리 또는 빈 디렉터리여야 합니다. 기존 증거가 있으면 덮어쓰지 않고 거부합니다.

- 기본값은 seed `900,901,902` 각각에 대해 정지 명령 `(0,0,0)`과 낮은 전진 명령 `(0.1,0,0)`을 평가하는 총 6개 표본입니다. 각 표본은 새 단일 환경을 생성합니다.
- `--vx`는 `[0,0.2]` m/s이며 `vy=0`, `yaw_rate=0`입니다. `--vx 0`이면 정지 표본만 평가합니다. 머리 4개·몸체 6개 명령 입력은 모두 0으로 고정합니다.
- `--seconds`는 표본별 **시뮬레이션 시간**입니다. `0.02`초의 배수이며 최대 60초입니다. 기본 10초는 최대 500 제어 스텝입니다. CUDA 초기화·컴파일을 포함한 실제 대기 시간을 제한하는 옵션은 아닙니다.
- seed는 중복 없는 1~16개 정수입니다. 공식 기본 학습 seed `42`는 거부합니다. 사용자는 실제 학습·튜닝 기록과 대조해 평가 seed가 보류되었는지 확인해야 합니다. 보고서의 `held_out_confirmed_by_operator`는 자동으로 확인할 수 없어 항상 `false`입니다.

## 고정 소스와 실행 계약

공식 `pollen-robotics/microduck_rl`의 `develop` 기준 커밋은 다음 값입니다.

```text
53b8971b61baf5b7f3c16d135dd7cac37623de4b
```

`--repo`는 해당 체크아웃의 최상위 경로여야 합니다. 실행 전 HEAD, 공식 `origin`, 추적 파일의 변경 여부(스테이징 포함)를 검사합니다. `src`의 추가 import 가능 파일과 심볼릭 링크도 거부하며, 실제 `mjlab_microduck` 모듈이 지정한 체크아웃에서 로드되었는지 검사합니다. 이 검사는 로컬 소스 확인이며 모델의 학습 출처나 이용 권한을 인증하지 않습니다.

| 항목 | 계약 |
|---|---|
| mjlab | `1.3.0` |
| task | `Mjlab-Velocity-Flat-MicroDuck` |
| 환경 | `ManagerBasedRlEnv`, `cuda:0`, `num_envs=1`, `render_mode=None` |
| 물리 | CUDA MuJoCo Warp; CPU 물리 대체 실행 없음 |
| 제어 주기 | **50 Hz**, `step_dt=0.02 s` (`timestep=0.005 s × decimation=4`) |
| 중력 관측 | **`USE_PROJECTED_GRAVITY=True`** |
| ONNX 입력·출력 | 각각 하나의 정적 float32 텐서, **`[1,61] → [1,14]`** |
| 정책 추론 | ONNX Runtime `CPUExecutionProvider`; 물리는 CUDA에서 실행 |
| 자동 리셋 | **`auto_reset=False`** |

정책은 공식 exporter가 관측 정규화를 포함하여 내보낸 결과를 사용합니다. 평가기는 관측을 수작업으로 재조립하거나 다시 정규화하지 않으며, 환경의 `actor` 관측을 그대로 전달합니다. 정책의 입력·출력 개수·타입·형상을 검사하고, 0 입력에서 출력이 유한한지 확인한 뒤 실제 스텝마다 입력·출력의 유한성을 확인합니다. 이는 ONNX 인터페이스 확인이지 보행 품질이나 학습 출처 검증이 아닙니다.

정책은 `check_policy.read_regular`로 최대 256 MiB의 일반 파일을 한 번만 읽습니다. 최종 경로의 심볼릭 링크와 특수 파일은 거부합니다. 읽은 불변 `bytes`를 SHA-256 계산, ONNX 파싱, `onnxruntime.InferenceSession`에 공통으로 전달하므로 읽기 이후 파일이 바뀌어도 해시와 추론 대상이 달라지지 않습니다. 공유 재귀 텐서 탐색 헬퍼로 초기화 텐서뿐 아니라 중첩 그래프·속성·희소 텐서·함수의 `EXTERNAL` 및 `external_data`를 **세션 생성 전에 명시적으로 거부**합니다. 외부 가중치 파일은 읽지 않으며 전체 정책 검사기를 중복 실행하지 않습니다.

환경 설정은 `load_env_cfg(..., play=False)`로 읽습니다. 관측 노이즈, 초기 상태, 물리·액추에이터, 도메인 랜덤화, 푸시 이벤트, 보상, 종료 규칙과 커리큘럼 정의를 유지합니다. 변경은 단일 환경, 기록된 seed, 자동 리셋 해제 및 고정 명령입니다. 공식 명령 클래스의 `_update_command` 확장 지점을 통해 원래 갱신 후 목표 명령을 고정하므로 주기적 재샘플링이나 커리큘럼이 평가 명령을 바꾸지 못합니다. 매 관측에서 실제 명령도 확인합니다.

새 환경의 커리큘럼 카운터는 0부터 시작합니다. ONNX에 학습 환경의 커리큘럼 진행 상태가 들어 있지는 않으므로 특정 체크포인트가 학습 종료 시 경험한 랜덤화 강도를 복원했다고 주장하지 않습니다. seed는 환경 생성 전에 설정하고 리셋에도 전달하여 시작 시 랜덤화와 리셋을 기록된 seed에 연결합니다. CUDA 수치 연산까지 비트 단위 재현성을 보장하지는 않습니다.

## 첫 실패에서 정지

각 표본은 다음 중 먼저 발생하는 조건에서 끝납니다.

1. 원래 환경의 `terminated` 또는 `truncated` 신호.
2. 관측·정책 출력·보상·측정 상태의 비유한 값이나 유효하지 않은 중력 벡터.
3. 아래 즉시 판정용 임시 한계 초과.
4. 요청한 시뮬레이션 시간 도달. 이때 평균 추종 오차도 검사합니다.

종료 신호가 발생한 마지막 상태까지 측정하고 그 표본에서 다시 `step()`을 호출하지 않습니다. 마지막 스텝에서 시간 초과 신호가 발생해도 `duration_reached` 성공으로 바꾸지 않습니다. 비유한 정책 출력은 물리에 전달하지 않으며 시뮬레이션 시간을 증가시키지 않습니다. 다음 독립 seed/명령 표본은 새 환경에서 평가합니다. 런타임 예외가 발생하면 전체 실행을 중지하고 확보된 부분 증거를 남깁니다.

환경 생성 후의 실행은 `torch.no_grad()` 범위에 있고, 생성된 환경은 정상·실패·예외 경로 모두 `finally`에서 `env.close()`를 호출합니다.

## 출력 파일과 상태 해석

| 파일 | 내용 |
|---|---|
| `simulation-report.json` | 소스·정책 SHA-256·설정·한계·전체 상태와 표본별 결과 |
| `episodes.csv` | seed/명령별 한 행의 종료 상태와 누적 지표 |
| `steps.csv` | 초기 상태와 각 제어 스텝의 측정값, 종료/실패 행 포함 |

입력·저장소 사전 검사에서 거부되면 보고서를 만들지 않습니다. 보고서 디렉터리를 준비한 이후 정책·런타임 준비 실패는 JSON의 `status: error`에 기록합니다. 물리 스텝 전에 실패하면 `steps.csv`가 생성되지 않을 수 있습니다. 표본마다 JSON과 요약 CSV를 저장하고, 스텝 CSV는 각 행을 기록한 뒤 flush합니다. 프로세스 강제 종료나 시스템 장애에서 완전한 보고서를 보장하지는 않습니다.

주요 JSON 필드는 다음과 같습니다.

| 필드 | 의미 |
|---|---|
| `schema_version` | `1` |
| `status` | `not_run`, `running`, `complete`, `error`, `interrupted` |
| `simulation_executed` | 최소 하나의 물리 제어 스텝과 측정 행이 기록되었는지 |
| `provisional_thresholds_met` | 전체 표본이 시간 한도를 채우고 워크샵 임시 기준을 충족했는지 |
| `manual_review_required` | **항상 `true`** |
| `manual_video_review_completed` | **항상 `false`** |
| `physical_trial_authorized` | **항상 `false`** |
| `video_recorded` | `false`; 이 헤드리스 평가기는 영상을 생성하지 않음 |
| `manual_review_record` | `null`; 별도 운영자 검토 기록에서 연결 |
| `error` | 실행 예외 설명 또는 `null` |

`status: complete`는 계획된 표본 처리가 끝났다는 뜻입니다. 실패 표본이 있어도 전체 처리는 완료될 수 있으므로 품질 판정으로 해석하지 마세요. `provisional_thresholds_met: true`도 수동 검토나 실물 시험 승인이 아닙니다. 종료 코드는 `0`(모든 임시 기준 충족), `1`(평가 완료, 기준 미충족), `2`(인자/준비/런타임 오류 또는 중단)입니다.

표본에는 정확한 `seed`, `vx`, `vy`, `yaw_rate`, `requested_seconds`, 실제 `steps`, `sim_time_s`, `terminated`, `truncated`, `finite`, `stop_reason`, `failure_stage`를 기록합니다. 주요 종료 원인은 `duration_reached`, `terminated`, `truncated`, `nonfinite_or_invalid_state` 및 해당 지표 이름의 `_limit`입니다. 실행되지 않은 표본의 `finite`는 `null`입니다.

지표는 공식 `env.scene["robot"].data`의 확인된 속성으로 계산합니다.

- `distance_m`: `root_link_pos_w`의 초기 위치 대비 XY 직선 거리. 전진 성공 거리가 아니며, 뒤로 움직여도 양수입니다.
- `path_length_m`: 유한한 연속 측정 위치 사이 XY 이동 거리의 합.
- `planar_velocity_error_m_s`: `root_link_lin_vel_b`의 몸체 기준 XY 속도와 고정 명령 사이 유클리드 오차.
- `yaw_rate_error_rad_s`: `root_link_ang_vel_b`의 z 각속도와 yaw 명령 사이 절대 오차.
- `tilt_deg`: `projected_gravity_b`와 몸체 아래 방향 사이 각도. 정립 0°, 옆으로 누움 90°, 뒤집힘 180°입니다.

평균 속도 오차는 초기 리셋 상태를 제외한 유한한 제어 스텝으로 계산합니다. 거리·최대 기울기는 초기 상태와 종료 상태도 포함합니다. 비유한 실패 행은 지표를 비워 두며 JSON에는 NaN/Infinity를 쓰지 않습니다. 요약 지표는 **마지막으로 유한하게 측정된 값**을 유지하므로 `finite`, `metric_samples`, `stop_reason`과 함께 읽어야 합니다. 예외 중 마지막 스텝이 완료되지 않았다면 기록된 시간은 마지막으로 확보한 측정 시점까지입니다.

## 워크샵 임시 기준과 별도 수동 검토

아래 수치는 워크샵의 초기 선별 기준입니다. 실측으로 보정하거나 안전성 인증을 받은 한계가 아닙니다. 경계값과 같으면 허용하고 **초과**할 때 미충족으로 처리합니다.

| 지표 | 임시 한계 | 검사 시점 |
|---|---:|---|
| 기울기 | 45° | 초기 상태 및 매 스텝 |
| 초기 위치 대비 XY 거리 | 3 m | 초기 상태 및 매 스텝 |
| XY 속도 추종 오차 | 0.75 m/s | 초기 상태 및 매 스텝 |
| yaw 속도 추종 오차 | 2 rad/s | 초기 상태 및 매 스텝 |
| 정지 명령의 XY 드리프트 | 0.25 m | 초기 상태 및 매 스텝 |
| 평균 XY 속도 추종 오차 | 0.20 m/s | 요청 시간 도달 시 |
| 평균 yaw 속도 추종 오차 | 0.50 rad/s | 요청 시간 도달 시 |

보상값이나 에피소드 완료를 하드웨어 통과로 변환하지 않습니다. 운영자는 별도 영상에서 넘어짐, 발 미끄러짐, 진동, 자세 및 명령 추종을 검토해야 합니다. 영상이 없으면 검토를 완료로 기록할 수 없습니다. 별도 운영자 기록의 예시는 다음과 같습니다. 아래 `false` 값은 미검토 템플릿이며 승인 기록이 아닙니다.

```json
{
  "schema_version": 1,
  "simulation_report": "simulation-report.json",
  "simulation_report_sha256": "<운영자가 계산한 보고서 SHA-256>",
  "policy_sha256": "<보고서에 기록된 정책 SHA-256>",
  "operator": null,
  "reviewed_at": null,
  "held_out_seeds_confirmed": false,
  "video_reference": null,
  "manual_video_review_completed": false,
  "manual_review_required": true,
  "physical_trial_authorized": false,
  "notes": "운영자 검토 미실시"
}
```

영상에는 정책 해시, seed, 명령과 설정을 연결하세요. 이 운영자 문서는 평가기가 생성하거나 승인하는 문서가 아닙니다. 배포 묶음의 별도 `evaluation.json`과도 구분되며, 필요한 경우 `simulation-report.json`을 증거 파일로 연결합니다. 실물 시험은 별도의 운영자 절차와 권한 확인이 필요합니다.

## 확인한 공식 소스

로컬 `../.microduck-workshop-research`의 `velocity-env.py`, `manager-env.py`, `rl-config.py`, `mjlab-tree.json`을 읽고, 필요한 API는 아래 고정 공식 소스에서 확인했습니다.

- [Microduck 환경 설정 및 projected gravity](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/src/mjlab_microduck/tasks/microduck_velocity_env_cfg.py)
- [Microduck 명령 클래스와 갱신 확장 지점](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/src/mjlab_microduck/tasks/mdp.py)
- [Microduck task 등록](https://github.com/pollen-robotics/microduck_rl/blob/53b8971b61baf5b7f3c16d135dd7cac37623de4b/src/mjlab_microduck/tasks/__init__.py)
- [mjlab v1.3.0 환경: reset, step, auto_reset, close](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/envs/manager_based_rl_env.py)
- [mjlab v1.3.0 EntityData: 확인된 자세·속도·중력 속성](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/entity/data.py)
- [mjlab v1.3.0 기본 속도 환경: timestep와 decimation](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/tasks/velocity/velocity_env_cfg.py)
- [mjlab v1.3.0 명령 관리자](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/managers/command_manager.py)
- [mjlab v1.3.0 task 설정 로더](https://github.com/mujocolab/mjlab/blob/v1.3.0/src/mjlab/tasks/registry.py)

상위 환경은 종료·보상 계산 시 파생 자세가 한 물리 서브스텝 이전일 수 있음을 문서화합니다. 평가기는 이를 바꾸지 않으며 `step()` 반환 후 갱신된 상태를 측정합니다. 따라서 원래 종료 규칙과 평가 기울기 한계가 같은 스텝에 동일한 판정을 내린다고 가정하지 않습니다.

## 검증 범위

```bash
python3 -m unittest discover -s tests -p test_evaluate_sim.py -v
```

테스트는 표준 라이브러리 기반이며 GPU·로봇 자산·학습 모델을 사용하지 않습니다. seed/시간 경계, 기울기·거리·오차 수학, ONNX 메타데이터 계약, 첫 실패 후 정지, 종료 상태 보존, 비유한 출력 시 시간 유지, 부분 실패 증거, JSON/CSV와 수동 검토 플래그를 확인합니다. import와 `--help`는 `python -S`로도 확인합니다. 추가 ONNX 회귀 테스트는 `requirements-validation.txt`의 CPU 패키지로 합성 정책만 생성하여 외부 텐서의 재귀적 거부와 파일 변경 후 동일 바이트·해시·추론의 연결을 확인합니다. 이 패키지가 없으면 해당 테스트는 skip되며 GPU 검증으로 집계하지 않습니다.

**미검증:** 실제 공식 ONNX와 CUDA Warp의 연결, 환경 생성 및 명령 확장 클래스의 통합 동작, 실제 랜덤화·시뮬레이션 결과, 영상 검토, 로봇 동작. 이 항목은 사용자의 자산 이용 자격 및 실행 환경이 준비된 뒤 별도 실행 증거로 확인해야 합니다. 소스 대조와 CPU 테스트만으로 통합 검증을 완료했다고 표시하지 마세요.
