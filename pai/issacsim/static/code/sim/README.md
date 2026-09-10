# Isaac Sim 5.1 Burger 시뮬레이터

공식 TurtleBot3 Burger USD의 두 바퀴를 PhysX articulation으로 구동한다.
매 0.2초에 같은 경기장 collider로 360개 수평 ray를 측정하고,
상위 `workshop_core.py`의 전처리·전문가·정책·안전 guard를 호출한다.
별도 ROS 프로세스, ONNX, 추가 로봇 구매가 필요하지 않다.

## 실행

Isaac Sim 5.1.0 컨테이너 내부 기준이다. `/workspace`는 저장소 읽기 전용,
`/output`은 결과 쓰기 경로이며 호스트의 `/opt/isaac-workshop/output`과 연결된다.

```bash
/isaac-sim/python.sh /workspace/static/code/sim/run_sim.py \
  --mode collect --episodes 30 --steps 600 --seed 42 \
  --output /output/dataset.npz --preview /output/preview.png
```

먼저 `--episodes 2 --steps 40`으로 GPU 리허설을 진행한다.
PNG는 실제 Isaac 카메라의 첫 에피소드 장면이다. 이미지가 비어 있으면 실패한다.
한 이미지만 저장하며 동영상이나 실시간 스트리밍을 자동 실행하지 않는다.
별도로 디스플레이를 준비한 로컬 머신에서는 `--render`로 창을 열 수 있다.
기본 AWS 경로에서는 `--render`를 지정하지 않는다.

학습 후:

```bash
/isaac-sim/python.sh /workspace/static/code/sim/run_sim.py \
  --mode evaluate --episodes 5 --steps 600 --seed 900 \
  --policy /output/policy.npz --output /output/evaluation.json
```

학습 명령과 실물 연결은 [공통 계약](../../../docs/implementation-contract.md)을 참조한다.

## 생성물과 단위

| 파일 | 내용 |
|---|---|
| `dataset.npz` | `observations`: Nx12 미터, `actions`: Nx2 m/s·rad/s, `episodes`: 정수 ID |
| `dataset.metadata.json` | seed, 자산 경로, 스캔·물리 설정, 실제 에피소드 결과와 배치 |
| `dataset.csv` | 원본 360개 ray, 12개 sector, 요청·실행 명령, 전후 실제 자세, 접촉 |
| `preview.png` | 선택한 첫 에피소드의 실제 렌더 이미지 |
| `evaluation.json` | 학습 정책의 접촉·근접·진행·정지·안전 개입 |
| `evaluation.csv` | 평가 과정의 원본 스캔과 주행 로그 |

CSV의 `sim_time_s`는 해당 에피소드의 첫 스캔을 0초로 하는 제어 시각이다.
`x_m/y_m/yaw_rad`는 스캔을 받은 시점, `next_*`는 명령을 적용한 다음 시점이다.
거리 미검출은 원본 CSV에서 `inf`로 남는다. NPZ는 공통 코어가 유효하다고 판단한
scan의 sector만 저장하며 이미 정규화된 값이 아니다.
라벨은 해당 scan에 대한 **전문가의 요청 명령**이다. 안전 guard가 실행 명령을
변경했는지는 CSV에 별도로 남고, 안전 정지 시 그 에피소드는 종료한다.

## 센서·경기장·평가

- 경기장 안쪽은 6×6 m이며, 벽 4개와 0.45×0.45×0.50 m 상자 8개를 사용한다.
  seed별로 상자와 초기 자세를 생성한다. 학습 42~71과 평가 900~904는 겹치지 않는다.
- 바퀴 반지름 0.033 m, 윤거 0.160 m를 USD의 실제 관절·충돌 형상과 비교한다.
  자산이 없거나 치수가 다르면 오류로 종료한다.
- 스캔은 `base_footprint` 기준 `(-0.032,0,0.182) m`에서 수평으로 발사한다.
  센서 케이스 collider만 비활성화하여 자기 케이스를 측정하지 않는다.
  차체·바퀴·caster의 물리 충돌은 유지한다.
- 에피소드마다 첫 PhysX 스캔을 상자/벽의 알려진 거리와 비교한다.
  `expected_scan()`의 수학적 ray는 **이 검증에만 사용**하며 학습 데이터를 만들지 않는다.
- 실제 자세는 물리 엔진에서 읽고, 이동 중 pose를 강제로 옮기지 않는다.
  초기 자세 설정은 에피소드 reset에서만 수행한다.
- collision은 바닥을 제외한 벽·상자와 차체/바퀴/caster의 실제 PhysX contact force로
  판정한다. near miss는 반지름 0.14 m의 보수적 원형 footprint가 장애물에
  0.10 m 미만으로 접근한 제어 step이다. 두 값을 같은 의미로 해석하지 않는다.
- `moving_step_fraction`의 분모는 **계획한 전체 step**이다. 조기 안전 정지 후
  남은 step도 정지로 계산하므로, 짧게 움직이다 멈춘 정책이 높은 점수를 받지 않는다.
  `path_length_m`과 `net_displacement_m`도 같이 확인한다.
- 안전 guard는 매 에피소드 새로 생성하지만 에피소드 안에서는 정지를 해제하지 않는다.
  충돌·안전 정지로 에피소드가 짧아지면 수집 행 수는 `episodes × steps`보다 작다.

## 검증 범위와 운영자 리허설

CPU에서 확인 가능한 helper 검증:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s static/code/sim -p 'test_*.py' -v
```

공식 문서/API 확인과 USD 파일의 정적 형상 검사는 수행했다.
실제 GPU의 PhysX 주행·접촉 센서·Camera 렌더링은 이 작성 환경에서 실행하지 않았다.
먼저 짧은 수집을 돌려 PNG, scan/collider 일치, 실제 이동 거리, 유효 데이터 행 수를
확인해야 한다. 별도 시험 장면에서 알려진 접촉을 만들어 contact reporting도 확인한다.
성공한 JSON이 아직 없는 실행을 검증 완료라고 표시하지 않는다.

이 센서는 LDS의 광학·회전 시간차·재질·잡음을 재현하지 않는 이상적 센서다.
고정 step/seed는 배치 재현을 돕지만 GPU·드라이버 간 비트 단위 동일성을 보장하지 않는다.
자세가 10도 이상 기울면 평면 과제가 성립하지 않으므로 실패한다.
공식 자산 출처, 정확한 치수, 실제 하드웨어 및 **OpenCR 명령 만료의 한계**는
[로봇 근거 문서](../../../docs/robot-evidence.md)를 참조한다.
