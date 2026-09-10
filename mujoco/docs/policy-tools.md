# Microduck 정책의 오프라인 검사와 묶음 전달

이 도구는 ONNX 정책 파일 하나를 검사하고, 검토에 필요한 로컬 평가 기록을 묶습니다. 시뮬레이터 실행, Hugging Face 게시, 정책 배포, 로봇 통신은 수행하지 않습니다. 검사 대상 인터페이스는 현재 공개 Microduck 계약에 맞춘 **float32 입력 1개 `[1, 61]`, float32 출력 1개 `[1, 14]`**입니다. 가변 차원, 추가 입력·출력, 다른 자료형은 거부합니다.

## 설치와 테스트

프로젝트 최상위 폴더에서 실행하세요. 현재 검증 패키지의 호환성을 맞추기 위해 **Python 3.12 가상환경**을 사용합니다. 아래 명령은 프로젝트 밖에 환경을 만듭니다. Python 3.12가 먼저 설치되어 있어야 합니다.

```bash
python3.12 -m venv /tmp/microduck-policy-tools-venv
/tmp/microduck-policy-tools-venv/bin/python -m pip install -r requirements-validation.txt
source /tmp/microduck-policy-tools-venv/bin/activate
python -m unittest discover -s tests -p test_policy_tools.py -v
```

이후 예제의 `python`은 활성화한 가상환경의 Python입니다. 개별 패키지를 임의의 최신 버전으로 설치하지 말고, 저장소의 `requirements-validation.txt`에 지정된 버전과 범위를 사용하세요. 실제 학습 환경은 공식 저장소의 잠금 파일을 따릅니다.

안전한 파일 읽기에 POSIX의 `O_NOFOLLOW`와 디렉터리 파일 디스크립터를 사용하므로 Linux/macOS에서 실행해야 합니다. ONNX, ONNX Runtime, NumPy는 정책 검사 시에만 불러옵니다. 모듈 가져오기, `--help`, 묶음 `verify`는 Python 표준 라이브러리만으로 실행됩니다. 선택 패키지가 없으면 ONNX 관련 테스트는 건너뛰고 나머지 테스트는 실행합니다. 테스트 모델은 로컬에서 합성하며, 로봇 자산이나 체크포인트를 다운로드하지 않습니다.

## 정책 파일 검사

체크포인트를 ONNX로 내보낼 때는 공식 `mjlab_microduck.export` 경로를 사용하세요. 공식 exporter는 관찰값 정규화를 포함하는 내보내기 경로를 설명합니다. 그러나 이 검사 도구는 **정규화가 그래프에 포함되었는지, 그 값이 올바른지 증명하지 않습니다.** 공식 exporter가 파일 하나를 만들 것으로 예상하더라도, 실제 생성된 ONNX 파일을 검사해야 합니다.

```bash
python static/code/check_policy.py /path/to/policy.onnx \
  --samples 32 --seed 2026 --report /path/to/new-smoke-report.json
```

`--samples`는 4~1024이며 기본값은 32입니다. `--seed`는 부호 없는 32비트 정수이며 기본값은 2026입니다. `--report`는 선택 사항으로, 이미 존재하는 폴더 안의 **새 파일** 경로여야 합니다. 성공하면 JSON 결과를 표준 출력으로 내보냅니다. 실패하면 표준 오류에 JSON 진단을 출력하고 종료 코드 1을 반환합니다. 명령 인자 오류의 종료 코드는 2입니다. 기존 보고서는 덮어쓰지 않으며, 검사 실패 시 성공 보고서 파일을 만들지 않습니다.

검사 순서는 다음과 같습니다.

1. 일반 파일에서 최대 256 MiB를 읽고, 그 바이트를 그대로 구조 검사와 추론에 사용합니다.
2. 중첩 그래프, 속성, 희소 텐서, 로컬 함수까지 포함해 외부 텐서 데이터 선언을 찾습니다. 외부 가중치가 있으면 ONNX 검사기나 런타임을 실행하기 전에 거부합니다. 데이터 위치 표시가 잘못되어도 외부 데이터 항목이 있으면 거부합니다. 외부 가중치를 허용하는 옵션은 없습니다. 파일 이름만 바꾸지 말고, 외부 파일에 의존하지 않는 ONNX로 다시 내보내세요.
3. ONNX 그래프와 정확한 float32 입출력 차원을 검사합니다. ONNX Runtime의 CPU 실행 공급자와 단일 연산 내부·연산 간 스레드를 사용합니다.
4. 준비 추론 1회와 여러 시드 기반 입력에 대한 추론을 수행합니다. 모든 결과는 유한한 float32 `[1, 14]`여야 합니다. 준비 추론도 유한성은 검사하지만 지연 시간 통계에서는 제외합니다.
5. **모든 측정 입력에서 행동 벡터가 정확히 같으면** 상수 출력 진단으로 실패합니다. 전부 0인 출력뿐 아니라 고정된 0이 아닌 벡터도 잡습니다. 일부 입력에서 0이 나오거나 일부 행동 채널이 항상 같아도, 다른 입력에서 한 채널이라도 변하면 허용합니다. 최대 변화 폭이 0보다 크고 `1e-6` 이하이면 실패 대신 경고를 남깁니다.

합성 입력은 직립 자세 주변의 작은 변화를 가정합니다. 각속도 ±0.5, `[0,0,-1]` 근처의 정규화한 중력, 관절 위치 차이 ±0.15, 관절 속도 ±0.5, 이전 행동 ±0.3, 명령 슬롯 3개 ±0.15, 나머지 명령 슬롯 10개 ±0.1을 사용합니다. 첫 입력은 직립 중력과 나머지 0으로 구성합니다. 관찰 블록 순서는 3+3+14+14+14+13을 가정합니다. 이는 독립적으로 만든 합성 값이며 물리적으로 일관된 동작 궤적이 아닙니다. 작업별 명령 의미, 배율, 관절 순서, 정규화 방식은 별도로 확인해야 합니다.

보고서에는 정책 SHA256, 입출력 정보, 표본 수·시드, 패키지 버전, 전체·행동별 최솟값/최댓값, 최대 행동 변화 폭, CPU 지연 시간 최소/평균/최대(ms)가 포함됩니다. 지연 시간에는 Python과 런타임 호출 비용이 들어가며 로봇의 실시간 성능을 나타내지 않습니다.

제한된 입력에서 정상 정책이 같은 출력을 내는 경우도 있으므로 상수 진단이 실패하면 내보내기 과정과 체크포인트를 직접 조사하세요. 반대로 유한하고 변하는 출력만으로 학습된 보행 정책이라고 판단할 수 없습니다. 무작위 그래프나 잘못된 정책도 통과할 수 있고, 비결정적 그래프는 상수 진단을 피할 수 있습니다. 이 도구는 행동 안전 인증, ONNX 실행 격리, 계산 시간 제한을 제공하지 않습니다. 신뢰할 수 있는 로컬 모델에 사용하세요.

## 평가 JSON의 필수 구조

본인이 작성한 평가 JSON을 준비합니다. 아래 필드는 **모두 필수**이고, 이 스키마 계층에 알 수 없는 필드를 추가하면 거부합니다. 상세 지표, 동영상 설명, 수동 평가 내용은 `reports`가 가리키는 별도 파일에 넣으세요. 이 구조는 상세 평가 보고서 형식을 강제하지 않습니다.

```json
{
  "schema_version": 1,
  "simulation": {
    "status": "not_run",
    "task_id": "YOUR_TASK_ID",
    "checkpoint_sha256": "<64 lowercase hexadecimal characters>",
    "policy_sha256": "<SHA256 of the exact ONNX file>",
    "reports": ["simulation-report.md", "run-01/metrics.json"]
  },
  "notes": "User-provided evaluation record; describe the method and limitations."
}
```

예시의 자리표시자는 실제 값으로 바꾸세요. `status`는 `passed`, `failed`, `not_run` 중 하나를 명시해야 합니다. **실제로 시뮬레이션 평가를 수행하고 통과했다고 판단한 경우에만 `passed`를 기록하세요.** 묶음 생성에 시뮬레이션 통과 조건은 없습니다. 실패하거나 아직 평가하지 않은 정책도 그 상태 그대로 검토용으로 묶을 수 있습니다. 통과 상태는 사용자가 제공한 기록이며 도구가 추론한 결과가 아닙니다. 어떤 상태도 실물 시험을 승인하지 않습니다.

작업 ID와 체크포인트 SHA256은 생성 명령의 값과 같아야 하고, 정책 SHA256은 실제 ONNX 바이트와 같아야 합니다. 체크포인트 해시는 사용자가 제공한 출처 정보입니다. 도구는 체크포인트를 불러오거나 ONNX가 그 체크포인트에서 만들어졌다는 사실을 증명하지 않습니다. 평가 JSON을 작성하기 전에 다음과 같이 파일 해시를 확인할 수 있습니다.

```bash
shasum -a 256 /path/to/checkpoint.pt /path/to/policy.onnx
```

`reports`에는 평가 JSON이 있는 폴더를 기준으로, 존재하고 비어 있지 않은 파일을 1~32개 지정합니다. 경로는 중복될 수 없습니다. 각 경로 구성 요소는 영문자·숫자로 시작하고 영문자·숫자·`.`·`_`·`-`만 포함해야 하며, 전체 경로는 240자 이하여야 합니다. 하위 폴더는 허용합니다. 절대 경로, `..`, `.`, 빈 경로 구성 요소, 역슬래시, 심볼릭 링크, 특수 파일, 파일과 폴더 이름 충돌, 예약된 참조 이름 `evaluation.json`은 거부합니다. URL이나 상위 폴더 파일 대신 로컬로 내보낸 보고서를 넣으세요.

참조 파일은 바이트를 변경하지 않고 묶음의 `evidence/`로 복사합니다. 존재 여부, 비어 있지 않음, 해시를 검사하지만 Markdown/PDF/동영상 내용의 정확성을 평가하지 않습니다. JSON 참조 파일은 문법, 중복 키, NaN, Infinity, 숫자 오버플로를 검사합니다. 평가 JSON은 최대 1 MiB, 각 참조 파일은 최대 16 MiB, 묶음 전체 내용은 최대 512 MiB입니다.

## 워크샵 묶음 생성

```bash
python static/code/bundle_policy.py create /path/to/policy.onnx /path/to/new-bundle \
  --evaluation /path/to/evaluation.json \
  --task-id YOUR_TASK_ID \
  --checkpoint-sha256 CHECKPOINT_SHA256 \
  --source-ref https://github.com/pollen-robotics/microduck_rl@FULL_TRAINING_COMMIT \
  --source-ref https://github.com/pollen-robotics/microduck@FULL_RUNTIME_COMMIT \
  --official-exporter-used \
  --checkpoint-validated-by-user \
  --samples 32 --seed 2026
```

소스 참조에는 브랜치나 변경 가능한 태그 대신 **소문자 40자리 Git 커밋 전체 해시**를 넣습니다. `--source-ref`는 최소 1개가 필요합니다. 학습·런타임·로봇 소스 등 필요한 공개 GitHub 저장소마다 반복해서 지정할 수 있으며, 최대 16개의 서로 다른 저장소 URL을 허용합니다. 오프라인으로 기록하므로 커밋의 실제 존재나 체크포인트와의 관계를 원격 확인하지 않습니다. 작업 ID는 영문자·숫자로 시작하고 영문자·숫자·`_`·`.`·`:`·`-`를 사용할 수 있습니다.

`--official-exporter-used`와 `--checkpoint-validated-by-user`는 **사용자가 직접 확인한 사실을 기록하는 선택 옵션**이며 기본값은 false입니다. 공식 exporter를 사용했다는 사실과 체크포인트를 별도로 검증했다는 사실을 확인한 경우에만 각각 넣으세요. 매니페스트의 exporter 이름은 첫 옵션이 가리키는 내보내기 도구의 이름이며, 자동 감지 결과가 아닙니다. 정책 검사 통과로 이 옵션들을 자동으로 true로 바꾸지 않습니다. 두 옵션이 모두 true여도 `normalizer_verified`는 false입니다.

생성 명령은 ONNX 검사를 다시 실행하고, 검사한 바이트를 그대로 복사합니다. 출력의 상위 폴더는 미리 존재해야 하고 출력 폴더 자체는 없어야 합니다. 빈 폴더나 끊어진 심볼릭 링크도 기존 출력으로 판단하여 거부합니다. 다른 프로세스가 같은 이름을 먼저 만들어도 덮어쓰지 않습니다. 쓰기나 자체 검증에 실패하면 이 명령이 새로 만든 미완성 묶음만 정리합니다. 생성·검증 중에는 대상 파일을 다른 프로세스에서 변경하지 마세요.

```text
new-bundle/
  policy.onnx
  workshop-manifest.json
  checksums.sha256
  smoke-report.json
  evidence/
    evaluation.json
    simulation-report.md
    run-01/metrics.json
```

`workshop-manifest.json`은 **워크샵 전용 형식**이며 공식 Hugging Face 정책 게시용 매니페스트가 아닙니다. 고정한 소스 참조, 작업·체크포인트 출처, 사용자 확인 옵션, 정책 해시, 사용자 평가 상태, 참조 파일, 각 내용 파일의 해시를 기록합니다. `checksums.sha256`은 자기 자신을 제외한 내용 파일과 워크샵 매니페스트의 해시를 포함합니다. 각 줄은 소문자 SHA256, 공백 두 개, 상대 경로 순서입니다.

다음 상태 값은 항상 false로 기록합니다.

```json
{
  "physical_trial_authorized": false,
  "hardware_validated": false,
  "deployment_authorized": false,
  "deployed": false,
  "normalizer_verified": false
}
```

성공하면 `verified`, `scope: "bundle_integrity_and_schema_only"`, 정책·매니페스트 SHA256, 파일 수, 사용자 평가 상태, 위 false 상태가 들어 있는 JSON을 출력합니다. 나중에 묶음 전체가 바뀌었는지 확인하려면 **매니페스트 해시를 묶음 밖에 따로 보관**하세요. 일반 파일로 전달할 수 있는 묶음을 만들 뿐, 생성 명령이 게시나 배포를 실행하지 않습니다.

## 전달받은 묶음 검증

```bash
python static/code/bundle_policy.py verify /path/to/bundle \
  --expected-manifest-sha256 INDEPENDENTLY_RETAINED_MANIFEST_SHA256
```

해시 옵션은 선택 사항입니다. 검증은 표준 라이브러리만 사용하며 정책을 실행하지 않습니다. 파일 목록의 정확한 일치, 체크섬, 매니페스트 해시, 필수 스키마·출처 정보, 정책과 평가 기록의 연결, 참조 파일 존재 여부, false 상태를 검사합니다. 읽기 전에 상대 경로를 검사하고, 묶음 아래의 모든 경로 구성 요소에서 심볼릭 링크를 따라가지 않는 방식으로 파일을 엽니다. 묶음 자체가 심볼릭 링크이거나 내부에 심볼릭 링크·특수 파일이 있으면 거부합니다. 매니페스트나 체크섬의 경로를 통해 묶음 밖의 파일을 읽지 않습니다. 추가·누락 파일, 중복 체크섬 항목, 잘못된 JSON, 유한하지 않은 JSON 숫자도 실패 처리합니다.

체크섬은 우발적 손상을 찾지만 디지털 서명은 아닙니다. 누군가 내용 파일·매니페스트·체크섬을 모두 바꾸면 서로 일치하는 다른 묶음을 만들 수 있습니다. 별도로 신뢰할 수 있게 보관한 매니페스트 해시가 있으면 이런 교체를 검출할 수 있습니다. 그 기준이 없을 때 `verified: true`는 현재 파일들이 내부 기록과 일치한다는 의미입니다. 작성자 신원, 실제 exporter·체크포인트 계보, 시뮬레이션 평가 내용, 실물 시험 승인을 보증하지 않습니다. `verify`는 복사된 추론 보고서를 다시 실행하지 않습니다. 새 추론 검사가 필요하면 `check_policy.py`를 별도로 실행하세요.

## 공개 참고 자료

- [Microduck 정책 계약과 런타임 소스](https://github.com/pollen-robotics/microduck): 현재 계약은 관찰값 61개와 행동값 14개입니다. 개별 묶음을 검토할 때는 기록된 런타임 커밋을 기준으로 확인하세요.
- [공식 Microduck 학습·내보내기 소스](https://github.com/pollen-robotics/microduck_rl): `mjlab_microduck.export` / `scripts/export.py` 경로를 사용합니다. 기록한 학습 커밋에서 실제 내보내기 절차를 확인하세요.
- [ONNX 외부 데이터 설명](https://onnx.ai/onnx/repo-docs/ExternalData.html), [ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html).
