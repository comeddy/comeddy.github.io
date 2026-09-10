# Physical AI: From Cloud to Robot

**Microduck · AWS GPU → MuJoCo → 보행 강화학습 → ONNX → 실제 로봇**

한국어로 따라 하는 독립 워크샵입니다. 먼저 [index.html](index.html)을 브라우저에서 여세요. 기존 Isaac Sim/TurtleBot3 워크샵과 코드를 공유하지 않습니다.

- 가상 로봇이 관찰·행동·보상으로 배우는 과정을 이해합니다.
- SSM으로 접속하는 AWS GPU 환경을 만들고, 공식 Microduck 코드를 고정 버전으로 설치합니다.
- 짧은 환경 점검과 실제 보행 학습을 구분하고, 평가 결과를 기록합니다.
- ONNX 모델을 검사·묶음으로 전달하고, 공식 런타임으로 실물에 적용·복구하는 순서를 배웁니다.
- 구조·학습 개념은 자체 제작 그림으로 설명하고, 브라우저 체험은 Pollen Robotics의 공식 온라인 Microduck 시뮬레이터를 연결합니다.

관절의 연결 관계는 [관절을 움직이며 이해하기](static/visuals/joint-concepts-3d.html)에서 오프라인으로 먼저 살펴볼 수 있습니다. Module 1·6·9에는 같은 자체 3D 도형으로 만든 설명 그림을 넣었습니다.

## 먼저 확인

공식 소프트웨어와 로봇 3D 자산의 라이선스가 다릅니다. [자산 이용 조건](docs/asset-licensing.md)을 먼저 읽으세요. 모델·메시·사전학습 가중치는 이 교재에 포함하지 않습니다. AWS 고객 행사 등 상업적 맥락의 이용 권한이 불명확하면 실제 자산을 받는 단계에서 멈추고 확인해야 합니다. 별도 다운로드도 이용 제한을 없애지 않습니다.

[공식 온라인 시뮬레이터 열기](static/visuals/biped-3d.html)는 인터넷과 제공자 서비스 가용성에 의존합니다. 교재 안에서 열리지 않으면 [Hugging Face Space](https://huggingface.co/spaces/pollen-robotics/microduck-simulator)에 직접 접속하세요. 이 브라우저 데모는 AWS GPU 학습이나 내 체크포인트 재생과 별개이며, 실제 로봇·모터에 연결하지 않습니다. 데모 화면은 이 워크샵의 학습 성공을 증명하지 않습니다. 교재는 제공자 앱을 임베드·링크하며 메시·가중치·사진을 재배포하지 않습니다. 임베드가 모델의 NC 조건을 없애거나 상업 이용권을 부여하지 않으며, 다운로드·학습 전 권한 확인은 그대로 필요합니다.

교재와 보조 코드의 검증 상태는 [검증 기록](docs/verification.md)에 있습니다. 로컬 코드 검증과 실제 GPU 보행 학습, 실제 로봇 시험을 구분합니다. 이 배포본에 검증된 보행 모델은 포함되지 않습니다.

## 구성

| 경로 | 내용 |
|---|---|
| `content/` | Workshop Studio 형식의 한국어 교재 |
| `static/workshop.yaml` | SSM 접속 GPU EC2, private S3, VPC 인프라 |
| `static/code/` | 시뮬레이션 평가, ONNX 점검, 배포 묶음 검증 |
| `static/upstream-lock.json` | 공식 소스 기준 커밋과 모델 인터페이스 |
| `static/images/`, `static/visuals/` | 편집 가능한 3D 설명 그림, 오프라인 관절 뷰어, 공식 온라인 시뮬레이터 |
| `scripts/workflow.py` | 기본은 명령 미리보기, `--execute`로 실행 |
| `scripts/cloud/` | 클라우드 확인·배포·정지·삭제 도구 |
| `docs/` | 출처, 라이선스, 강사 안내, 검증 범위 |

## 교재 빌드와 검증

```bash
python3 -m venv .venv-docs
.venv-docs/bin/python -m pip install -r requirements-docs.txt
node scripts/visuals/build_viewer.mjs
node scripts/visuals/build_concept_viewer.mjs
node scripts/visuals/build_teaching_figures.mjs
.venv-docs/bin/python scripts/build_site.py
.venv-docs/bin/python scripts/validate_workshop.py
python3 -m unittest discover -s tests -v
```

ONNX 검사 테스트는 `requirements-validation.txt`의 추가 패키지가 필요합니다. 명령과 결과는 검증 기록을 참고하세요. `_site/`는 정적 호스팅용, `_gitbook/`은 GitBook에 가져올 Markdown 소스입니다. `scripts/package_workshop.py`는 공개 가능한 교재 파일만 ZIP에 포함합니다. 이 작업은 사이트를 외부에 게시하지 않습니다.

## 첫 명령

```bash
python3 scripts/workflow.py smoke --repo "$HOME/workshops/microduck_rl"
```

`PLAN ONLY`이면 AWS나 학습을 실행하지 않은 것입니다. 설치·과금·실물 동작 전에는 해당 모듈의 전제 조건과 실제 명령을 확인하세요.
