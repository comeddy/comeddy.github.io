---
title: "08 · ONNX 검사와 전달 묶음"
weight: 80
---

# 같은 정책을 로봇이 읽을 파일로 만들기

예상 시간: 30~60분. 실행 위치: GPU 호스트. 변환 후에도 관측 순서·정규화·행동 의미가 유지되어야 합니다.

## 1. 공식 exporter로 내보내기

```bash
cd "$WORKSHOP_ROOT"
mkdir -p artifacts
export POLICY="$WORKSHOP_ROOT/artifacts/policy.onnx"
python3 scripts/workflow.py export --repo "$DUCK_REPO" \
  --checkpoint "$CHECKPOINT" --onnx "$POLICY" --execute
```

공식 exporter는 관측 정규화를 포함하여 내보냅니다. 원본 체크포인트를 임의 코드로 ONNX로 바꾸지 않습니다. 출력이 이미 있으면 덮어쓰지 않으므로 새 파일 이름을 지정하세요. 변수는 새 셸을 열면 다시 설정해야 합니다.

## 2. 모델 형태와 숫자 점검

```bash
cd "$DUCK_REPO"
uv run --frozen python "$WORKSHOP_ROOT/static/code/check_policy.py" "$POLICY" \
  --samples 32 --seed 2026 --report "$WORKSHOP_ROOT/artifacts/onnx-smoke.json"
```

검사는 float32 입력 `[1,61]`, 출력 `[1,14]`, 외부 가중치 의존 여부, 유한한 출력, 합성 입력 전체에서 완전히 고정된 행동인지 확인합니다. 실제 궤적이 아닌 합성 입력 검사이므로 **정규화 의미·관절 순서·보행 품질을 증명하지는 않습니다**. 오류를 무시하거나 임의로 검사를 약하게 바꾸지 마세요.

## 3. ONNX로 새 시드의 시뮬레이션 평가

```bash
uv run --frozen python "$WORKSHOP_ROOT/static/code/evaluate_sim.py" \
  --repo "$DUCK_REPO" --policy "$POLICY" \
  --output "$WORKSHOP_ROOT/artifacts/sim-evaluation" \
  --seconds 10 --seeds 900,901,902 --vx 0.1
```

이 코드는 실제 MuJoCo 환경이 설치된 CUDA 호스트에서 실행하는 실습입니다. 제작 시 GPU 통합 실행까지 검증한 도구는 아니므로 첫 실행에서 API·형태 검사 오류가 나면 기록하고 중단하세요. 자세한 출력과 판정 범위는 [시뮬레이션 평가 도구](../../docs/simulation-evaluator.md)를 확인합니다.

이 평가기는 각 시드에서 정지 시험과 지정한 전진 시험을 포함합니다. 자동 숫자 결과와 모듈 7의 영상·행동 검토를 함께 판단하세요. 10초·3개 시드만으로 모든 바닥·충격·전압·실물 상태를 검증할 수 없습니다. 실제 모델 관찰·영상에는 자산 이용 조건이 적용됩니다.

## 4. 평가 기록 작성

현재 셸의 작업 디렉터리는 `$DUCK_REPO`입니다. 다음 구조로 **`$WORKSHOP_ROOT/artifacts/evaluation.json`**을 만듭니다. 아래 해시 문구를 실제 값으로 바꾸고, **`$WORKSHOP_ROOT/artifacts/simulation-review.md`**를 작성해 시험 조건·관찰·자동 보고서 경로·실패·미검증 항목을 적습니다.

```bash
sha256sum "$CHECKPOINT" "$POLICY"
```

```json
{
  "schema_version": 1,
  "simulation": {
    "status": "not_run",
    "task_id": "Mjlab-Velocity-Flat-MicroDuck",
    "checkpoint_sha256": "실제_체크포인트의_64자리_SHA256",
    "policy_sha256": "실제_ONNX의_64자리_SHA256",
    "reports": ["simulation-review.md"]
  },
  "notes": "실제 수행한 평가와 한계를 기록합니다."
}
```

`status`는 `not_run`, `failed`, `passed` 중 실제 관찰 결과를 적습니다. `passed`는 작성자의 시뮬레이션 평가 의견이며 실물 시험 승인이 아닙니다. 실행하지 않았다면 그대로 `not_run`으로 기록합니다. 보고서 JSON/CSV도 `reports`에 실제 상대 경로로 추가하면 함께 묶입니다. 각 경로의 허용 문자·크기는 [도구 안내](../../docs/policy-tools.md)를 확인하세요.

## 5. 전달할 파일 묶기

아래 `CHECKPOINT_SHA256`은 앞에서 확인한 실제 체크포인트 해시로 바꿉니다. 정식 exporter 사용과 체크포인트 출처를 직접 확인한 경우에만 두 확인 옵션을 넣습니다.

```bash
export CHECKPOINT_SHA256=실제_체크포인트의_64자리_SHA256
uv run --frozen python "$WORKSHOP_ROOT/static/code/bundle_policy.py" create \
  "$POLICY" "$WORKSHOP_ROOT/artifacts/bundle" \
  --evaluation "$WORKSHOP_ROOT/artifacts/evaluation.json" \
  --task-id Mjlab-Velocity-Flat-MicroDuck \
  --checkpoint-sha256 "$CHECKPOINT_SHA256" \
  --source-ref https://github.com/pollen-robotics/microduck_rl@53b8971b61baf5b7f3c16d135dd7cac37623de4b \
  --official-exporter-used --checkpoint-validated-by-user
```

예시의 source-ref는 실제 학습에 사용한 저장소만 기록합니다. 문서 참조용 런타임 커밋을 실제 로봇에 설치된 버전으로 기록하지 마세요. 설치된 하드웨어·펌웨어 버전은 실물 시험 기록에 별도로 남깁니다.

실패하거나 실행하지 않은 평가도 정직하게 보존할 수 있도록 묶음은 만들어집니다. **묶음 생성 성공은 다음 실물 단계의 허가가 아닙니다.** 출력을 보존하고 manifest SHA256은 묶음과 별도로 기록하세요.

```bash
python3 "$WORKSHOP_ROOT/static/code/bundle_policy.py" verify \
  "$WORKSHOP_ROOT/artifacts/bundle"
aws s3 cp "$WORKSHOP_ROOT/artifacts/bundle/" \
  "s3://$ARTIFACT_BUCKET/runs/my-walk/bundle/" --recursive --region "$AWS_REGION"
```

묶음은 `policy.onnx`, `workshop-manifest.json`, `checksums.sha256`, 검사 보고서와 평가 근거를 담습니다. 공식 Hugging Face 게시 manifest와는 다른 워크샵 내부 형식입니다. 여기에 실제 배포를 승인하는 기능은 없습니다.

**확인:** 모델 해시·출처·검사·평가 기록이 연결되었는지 확인합니다. 문제가 있으면 실물로 넘어가지 않습니다.

**기억할 점:** 전송 무결성 검사와 로봇 행동 검증은 별개입니다.

[← 결과 평가](../module7-evaluation/index.ko.md) · [다음: 실제 로봇 준비 →](../module9-robot/index.ko.md)
