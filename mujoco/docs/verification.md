# 검증 기록

이 문서는 교재 제작 과정에서 확인한 사실을 기록합니다. 읽음 표시나 출력 예시가 실제 실행 증거를 대신하지 않습니다.

## 검증 수준

| 항목 | 현재 상태 |
|---|---|
| 공식 소스·CLI·라이선스 문서 대조 | 수행: 고정 커밋과 원문 근거 보존 |
| AWS 템플릿 및 관리 코드 | 로컬 단위 테스트와 cfn-lint 수행; 실제 AWS 배포 아님 |
| ONNX 도구 | 합성 ONNX 테스트로 확인; 학습된 Microduck 보행 정책 아님 |
| 학습 명령 래퍼 | 계획·입력 거부·실패 기록 테스트; 실제 GPU 학습 아님 |
| 시뮬레이션 평가 도구 | 공식 API와 로컬 순수 계산 검사; 실제 GPU/로봇 자산으로 통합 실행하지 않음 |
| 교재 HTML·링크·코드 블록·그림 | HTML 빌드·링크·셸 구문 및 실제 Chromium 점검 통과 |
| 공식 온라인 Microduck 데모 | Chromium에서 3D 로딩·방향키 이동 확인; 제공자의 사전학습 데모 |
| AWS 생성·SSM 접속·CUDA 설치 | 이번 제작에서는 실행하지 않음 |
| Microduck 학습·보행 수렴·ONNX 변환 | 이번 제작에서는 실행하지 않음 |
| 실제 Microduck의 모델 로드·보행·복구 | 실제 장치가 없어 실행하지 않음 |
| GitHub Pages·GitBook 공개 게시 | 정적 배포 소스만 제공; 외부 게시하지 않음 |

## 공식 데모와 워크샵 실습의 구분

공식 Hugging Face 시뮬레이터는 사용자 요청에 따라 교재에 연결하고 실제 브라우저에서 실행했습니다. 브라우저는 제공자 서버의 모델·정책을 로드하지만 이 자산을 교재 ZIP이나 저장소에 복사·재배포하지 않습니다. 공식 데모의 움직임은 이 워크샵에서 AWS GPU로 학습한 정책의 결과가 아닙니다.

AWS 다운로드·학습·실물 통합 시험은 실행하지 않았습니다. 공식 모델의 CC BY-SA-NC 버전·범위와 실제 교육 행사 목적에 맞는 권한은 별도 확인 대상입니다. 임베드나 링크가 이용권을 부여하지 않습니다. 자세한 내용은 [라이선스 문서](asset-licensing.md)를 참고하세요.

## 운영자가 추가할 실행 증거

배포 계정·리전(공개 문서에는 비식별화), AMI/인스턴스, GPU/드라이버, 소스·lock 해시, 정확한 명령·시드·환경 수, 로그·체크포인트·ONNX 해시, 평가 JSON/CSV·영상, 실물 하드웨어/펌웨어·운영자 판단·복구 기록을 보관하세요. 과거 Isaac/TurtleBot3 워크샵의 실행 결과를 이 Microduck 과정의 결과로 재사용하지 않습니다.

## 로컬 확인 명령

```bash
python3 -m unittest discover -s tests -v
cfn-lint static/workshop.yaml
node scripts/visuals/build_viewer.mjs
.venv-docs/bin/python scripts/build_site.py
.venv-docs/bin/python scripts/validate_workshop.py
python3 scripts/package_workshop.py
```

ONNX 관련 테스트에는 `requirements-validation.txt` 설치가 필요합니다. 빠진 선택 의존성으로 skip된 테스트는 통과한 추론 테스트로 세지 않습니다. GPU 통합 시험은 별도의 참가자 실행입니다.

## 2026-09-10 기존 실습 코드 검증 기록

- Python 3.12, ONNX 1.20.1, ONNX Runtime 1.24.4, NumPy 2.5.3에서 **109개 단위·회귀 테스트 통과, 실패 0, skip 0**.
- 구성: cloud 31, distribution 8, evaluator 23, policy tools 37, workflow 10.
- `cfn-lint static/workshop.yaml` 종료 코드 0.
- 교체 전 자체 기하 뷰어의 시각 검사 43개 통과, draw.io 레이아웃 100/100. 이 43개는 현재 공식 데모의 검증 수치로 사용하지 않습니다.
- 교체 전 통합 교재의 Chromium 검사 15개 통과. 당시 오프라인 3D 결과는 이전 버전에만 해당합니다.
- 배포 staging은 검증된 소스 목록으로 새로 만들고, 이전 출력은 `artifacts/build-history/`에 보존합니다. 배포 목록·해시·심볼릭 링크·제한 자산 포함 여부를 검사합니다.
- 독립 검토에서 발견한 외부 ONNX 가중치/해시 불일치 경로, 이전 staging 잔여 파일 경로, 문서의 실행 위치·리전·PATH 문제를 수정했습니다.

기계가 읽는 결과는 [validation-summary.json](validation-summary.json)에 있습니다. 모든 ONNX 테스트 모델은 로컬 합성 데이터입니다. 이 결과는 실제 Microduck 보행 성공 기록이 아닙니다.

## 2026-09-10 공식 시뮬레이터 교체 당시 검증

- 교체 당시 구성도·독립 연결 페이지 검사 **20개 통과**: 원래 관절 도형 제거, 실행 전 외부 요청 없음, 오프라인 안내, 공식 Space 링크, JavaScript 비활성화 대안, 390px 모바일 가로 넘침 없음.
- 교체 당시 교재의 Chromium 검사 **28개 통과**: 22개 페이지, 설명 이미지 5개, 검색·읽음 표시·확대·모바일 목차와 공식 앱의 로딩·이동·종료를 확인했습니다.
- 실제 외부 앱의 **WADDLE IN**을 누른 뒤 Three.js 화면이 렌더링됐고, 방향키 입력 후 HUD에 **ODO 0.1M**이 표시됐습니다. 관찰한 순간 표시값은 0.21M/S, FPS 53, CTRL 47HZ이며 성능 보장이나 벤치마크가 아닙니다. 이 교재 실행의 JavaScript 오류는 0개였습니다.
- 실행 종료와 대화상자 닫기가 외부 iframe을 제거하고, 다시 실행이 새 iframe을 만드는 것을 확인했습니다. 호스트 요청 차단 상황에서도 직접 접속 링크가 보입니다. iframe의 `load` 이벤트를 물리·정책 준비 완료로 간주하지 않습니다.
- 모바일 검증은 390px 교재·연결 안내 레이아웃과 실패 대안의 확인입니다. 모바일 기기 GPU 성능·터치 보행 조작·모든 브라우저의 동작은 확인하지 않았습니다.
- 공식 Space는 제공자가 갱신할 수 있습니다. 메타데이터 관찰 커밋은 출처 문서에 기록하며, 이 외부 앱을 교재의 학습 커밋으로 고정했다고 주장하지 않습니다.

Playwright와 Chromium이 설치된 Python 환경에서 다음을 실행할 수 있습니다. `--live`는 실제 외부 앱을 불러오며 인터넷이 필요합니다. 결과·스크린샷은 배포에서 제외되는 `artifacts/`에 저장합니다.

```bash
python3 scripts/visuals/verify_visuals.py --output artifacts/simulator-visual-checks
python3 scripts/verify_site.py --output artifacts/simulator-site-checks --live
```

## 관절 개념 뷰어 복원과 3D 설명 그림

공식 온라인 시뮬레이터는 그대로 유지하고, 기존 자체 제작 관절 뷰어를 `static/visuals/joint-concepts-3d.html`로 복원했습니다. Module 1에서 관절 연결을 먼저 살펴보고, Module 5의 3분 실습에서 무릎·발목을 움직이며 다시 확인합니다. Module 1·6·9에는 자체 도형으로 만든 3D 설명 그림을 추가했습니다.

독립 관절 뷰어의 현재 소스에 대해 **43개 검사**를 다시 수행했습니다. 6개 슬라이더, 키보드 각도 변경, 캔버스 재그리기, 자세·시점 초기화, 드래그 회전, 확대, 390px 모바일, 제한된 iframe, JavaScript/Canvas 사용 불가 시 정지 그림을 확인했습니다. 외부 네트워크 요청은 없습니다. 이전 버전의 통과 기록을 그대로 가져온 것이 아닙니다.

```bash
node scripts/visuals/build_concept_viewer.mjs
node scripts/visuals/build_teaching_figures.mjs
python3 scripts/visuals/verify_concept_viewer.py --output artifacts/joint-concept-checks
```

이 3D 자료들은 기하학적 설명입니다. 그림과 뷰어에는 중력·접촉·균형 계산이나 실제 관절 제한이 없으며, 공식 데모의 보행 정책이나 실제 장치 시험 결과를 나타내지 않습니다.

통합 교재에서는 **37개 Chromium 검사**를 통과했습니다. 두 뷰어의 별도 열기·조작·닫기, 8개 설명 그림의 오프라인 로딩, 새 3D 그림 3개의 확대, 목차·읽음 표시·모바일 화면을 확인했습니다. 공식 Microduck 앱도 다시 실행해 로봇 렌더링·방향키 이동·종료를 확인했으며 JavaScript 오류가 없었습니다. 이 검증은 실제 AWS 학습이나 하드웨어 동작을 검증한 결과가 아닙니다.
