# 워크숍 시각 자료

모든 로컬 경로는 `physical-ai-from-cloud-to-robot/` 기준입니다. 구조·학습 개념도와 관절 개념 뷰어는 자체 제작 자료입니다. 관절 연결을 오프라인으로 익힌 뒤 Pollen Robotics의 공식 온라인 Microduck 시뮬레이터를 별도로 체험할 수 있습니다.

## 바로 사용할 자산

| 용도 | 경로 | 규격 |
|---|---|---|
| AWS 구성도 편집본 | `static/images/aws-architecture.drawio` | draw.io XML, 서비스와 그룹 편집 가능 |
| AWS 구성도 이미지 | `static/images/aws-architecture.png` | 3785 × 2423, 흰 배경, 2배 내보내기 |
| AWS 구성도 벡터 | `static/images/aws-architecture.svg` | PNG와 같은 draw.io 편집본, 접근성 설명 포함 |
| 모듈: 강화학습 | `static/images/learning-loop.svg` | 1440 × 940 |
| 모듈: Sim-to-Real | `static/images/sim-to-real-gates.svg` | 1440 × 940 |
| 모듈: 관측과 행동 | `static/images/observation-action.svg` | 1440 × 940 |
| 공식 온라인 시뮬레이터 연결 페이지 | `static/visuals/biped-3d.html` | 제공자 앱 임베드와 공식 Space 직접 접속 안내, 인터넷 필요 |

자체 기하 뷰어의 `biped-poster.svg`·`biped-poster.png`는 공식 시뮬레이터의 화면이 아닙니다. 홈페이지 미리보기나 공식 데모의 대체 이미지로 사용하지 않습니다. SVG 개념도는 `<title>`과 `<desc>`를 포함하며, `<img>`로 사용하는 호스트에서도 아래의 `alt`를 제공합니다.

## 관절 개념 뷰어와 중간 챕터 3D 그림

| 위치 | 자료 | 목적 |
|---|---|---|
| Module 1 | `static/images/joint-chain-3d.svg` | 무릎 각도를 바꾸면 그 아래 링크가 함께 이동하는 연결 관계 |
| Module 1·5 | `static/visuals/joint-concepts-3d.html` | “관절을 움직이며 이해하기”: 6개 슬라이더·시점 회전·정면/측면·자세 프리셋 |
| Module 6 | `static/images/policy-step-3d.svg` | 관측 → 정책 → 목표 관절각 → 다음 관측의 제어 과정 |
| Module 9 | `static/images/sim-to-real-3d.svg` | 마찰·지연·조립 차이와 지지된 실물 준비의 개념 |

이 자료들은 같은 자체 제작 3D 도형을 투영하여 만들었고, 네트워크 없이 표시됩니다. 공식 Microduck CAD나 측정된 하드웨어 치수·지지대 도면이 아닙니다. 교재에서는 그림을 눌러 확대할 수 있습니다.

관절 개념 뷰어는 `sandbox="allow-scripts"`인 별도 `srcdoc` iframe으로 열립니다. 공식 시뮬레이터의 외부 iframe과 목적·권한·실행 경로가 다릅니다. 개념 뷰어의 각도는 로봇 입력이나 모터 제한값으로 사용할 수 없습니다.

## 권장 대체 텍스트와 캡션

- **AWS 구성도 alt:** “학습자가 IAM과 SSM으로 L4 GPU EC2에 접속해 학습하고 비공개 S3에 결과를 보관한다. 운영자가 번들을 다운로드·검증한 뒤 로컬 Microduck 런타임에 배치한다. 모터 제어는 로컬 50Hz 루프에서 수행한다.”
- **학습 루프 alt:** “관측, 정책, 행동, 시뮬레이터가 한 스텝씩 반복된다. 수집한 경험으로 PPO가 정책을 갱신한다.”
- **통과 조건 alt:** “번들 무결성, 입출력 계약, 시뮬레이션 검증, 실기 실행 승인을 순서대로 확인한다. 실패하면 중단하고 수정한다.”
- **관측과 행동 alt:** “한쪽 다리의 고관절·무릎·발목 각도와 관절 속도를 설명한다. 관측을 정책에 넣어 행동을 얻으며, 실제 관측의 길이와 순서는 환경 설정을 확인한다.”
- **시뮬레이터 iframe 제목:** “Pollen Robotics 공식 온라인 Microduck 시뮬레이터”
- **시뮬레이터 캡션:** “제공자가 운영하는 온라인 데모입니다. 인터넷과 서비스 가용성이 필요하며, 내 AWS 학습·체크포인트 재생·실물 로봇 연결과 별개입니다.”

## 공식 시뮬레이터 임베드 계약

참가자 링크는 `static/visuals/biped-3d.html` 경로를 유지합니다. 로컬 페이지가 연결할 제공자 앱의 주소는 `https://pollen-robotics-microduck-simulator.hf.space`이며, 직접 접속 대안은 [공식 Hugging Face Space](https://huggingface.co/spaces/pollen-robotics/microduck-simulator)입니다.

인터넷과 제공자 서비스 가용성이 필요합니다. 로컬 HTML을 열 수 있어도 공식 앱은 오프라인으로 동작하지 않습니다. 프레임 차단·서비스 중단·브라우저 제한에 대비해 iframe 밖에서도 공식 Space 링크와 안내문을 읽을 수 있어야 합니다. 직접 접속도 서비스 중단을 해결하지는 않으므로, 그때는 교재의 구조·학습 개념도로 학습을 이어갑니다.

기존 자체 뷰어의 외부 요청 없는 `srcdoc`·`sandbox="allow-scripts"` 검증은 새 외부 앱에 적용되지 않습니다. 실제 wrapper와 홈페이지의 임베드 설정은 브라우저에서 확인해야 합니다. HF API의 `RUNNING`이나 iframe의 `load` 이벤트만으로 로봇 화면·조작이 정상이라고 판정하지 않습니다. 호스트에 모달이 있다면 닫기 버튼과 Escape 처리는 호스트가 담당합니다.

## 조작과 범위

조작 방법은 공식 앱의 현재 화면 안내를 따릅니다. 이전 자체 뷰어의 6개 관절 슬라이더, 굽힌 자세 프리셋, 임의 관절각 범위와 오프라인 정지 SVG 대체 화면은 공식 앱의 기능으로 안내하지 않습니다. 해당 기능은 복원한 오프라인 관절 개념 뷰어에서 사용합니다.

공식 온라인 데모는 제공자가 갱신하는 앱이며, AWS GPU에서 수행하는 MuJoCo/mjlab 학습이나 참가자의 체크포인트 재생과 별개입니다. 워크샵은 이 연결을 통해 실제 로봇·모터를 제어하지 않습니다. 데모에서 보이는 움직임은 워크샵 학습 성공·보행 품질·하드웨어 안전 검증의 증거가 아닙니다. AWS에서 직접 실행하는 Viser 실습은 Module 5, 모델 학습·평가는 후속 모듈에서 진행합니다.

관측 그림은 여러 환경에 통용되는 개념도입니다. 특정 정책의 관측 차원이나 관절 순서를 선언하지 않습니다. 실습의 실제 텐서 계약은 해당 환경·manifest·정책 도구 문서를 따릅니다.

## AWS 구성도 작성 근거

`architecture-diagram` 스킬과 `references/design-tokens.md`, `references/aws-reference-conventions.md`를 적용했습니다. `aws-architecture.spec.json`을 스킬의 `layout_aws.py`로 생성하여 단일 Region/VPC/AZ/public subnet/EC2 뼈대를 얻은 뒤, 생성기에서 지원하지 않는 VPC 밖 관리 서비스와 로컬 파일 전달 구역을 XML로 합성합니다.

- IAM은 AWS Cloud의 전역 서비스 구역, SSM과 S3는 Region 안이면서 VPC 밖에 배치했습니다.
- EC2는 L4 GPU, DLAMI Ubuntu, MuJoCo Warp / mjlab PPO로 표기했습니다.
- Public IPv4와 IGW 기본 경로 및 TCP 80/443 아웃바운드를 명시했습니다. Ubuntu apt의 HTTP 미러가 80을 사용하고 SSM Agent는 HTTPS 연결을 시작합니다. SSH 인바운드는 없습니다.
- 비공개 S3에 checkpoint·ONNX·workshop-manifest·SHA-256을 보관합니다. 운영자의 다운로드·검증·승인 이후 로컬 배치로 연결합니다.
- 클라우드에서 로봇 모터로 직접 가는 연결선은 없습니다. 50Hz/20ms 루프는 로컬 런타임 안에만 표시합니다.
- 사용하지 않는 NAT, Bedrock, SageMaker는 넣지 않았습니다.
- 서비스 아이콘은 동일한 78 × 78 크기이고, 직교 연결선은 6개입니다. 관리 관계는 회색 점선, 학습 결과 업로드는 주황 실선, 파일 전달은 회색 실선입니다.

AWS 아이콘은 draw.io의 AWS 셰이프 라이브러리를 통해 렌더링했습니다. AWS 명칭·아이콘은 해당 소유자의 상표입니다. 교육용 개념 SVG는 독자 제작이며 실제 로봇 메시·CAD·사진·체크포인트를 사용하지 않았습니다. 공식 시뮬레이터의 앱·자산·의존성은 제공자 서비스에서 로드하고 교재 ZIP에 복사·재배포하지 않습니다. 임베드·링크가 모델의 NC 조건을 해소하거나 상업 이용권을 부여하지 않으며, 다운로드·학습 전 [자산 이용 조건](asset-licensing.md) 확인은 유지합니다.

## 재생성과 검증

구성도 생성에는 Python 3, draw.io CLI와 한국어 글꼴이 필요합니다. 스킬 기본 위치는 `~/.agents/skills/architecture-diagram`이며 `ARCHITECTURE_SKILL` 환경 변수로 바꿀 수 있습니다. `scripts/visuals/build_architecture.py`, `build_diagrams.py`, `finalize_architecture_svg.py`가 기존 구성도·개념도를 생성합니다. 공식 앱 자체는 이 워크샵에서 빌드·복제하지 않습니다.

`node scripts/visuals/build_viewer.mjs`는 공유 구현인 `microduck-embed.mjs`·`microduck-embed.css`와 연결 페이지 템플릿으로 공식 시뮬레이터 연결 페이지를 재생성합니다. `scripts/visuals/build.sh`도 같은 생성기를 사용합니다. 교재 HTML은 같은 공유 구현을 대화상자에 삽입합니다. `node scripts/visuals/build_concept_viewer.mjs`는 독립 관절 뷰어를, `node scripts/visuals/build_teaching_figures.mjs`는 3개의 3D 설명 그림을 재생성합니다. 사이트 빌드·현재 검사 명령은 [README](../README.md)와 [검증 기록](verification.md)을 따릅니다.

AWS 구성도의 기존 최종 게이트 기록은 **100/100 (geometry 100, design 100)**, XML은 **41 cells / 33 vertices / 6 edges / 4 AWS resource icons / 4 AWS group containers**입니다. 일반 사용자 아이콘과 AZ 사각형은 도구의 AWS resource/group 개수에 포함되지 않습니다. 이 기록은 구성도에 관한 것이며 공식 시뮬레이터 연결 검증 결과가 아닙니다.

이전 자체 기하 뷰어 버전에서는 43개 시각 자료 검사를 통과했습니다. 당시 `viewer-desktop.png`, `viewer-mobile.png`, `viewer-srcdoc.png`, `viewer-fallback.png`와 네트워크 요청 0건·Canvas·관절 슬라이더·오프라인 검사 결과는 이전 버전의 근거입니다. 공식 시뮬레이터의 렌더링·조작·모바일 동작을 검증한 것으로 재사용하지 않습니다. 현재 검증 결과와 산출물의 적용 버전은 [검증 기록](verification.md)에서 확인합니다.

공식 Space의 호스트·Docker·RUNNING 상태는 [출처](sources.md)의 메타데이터 근거로 확인합니다. 2026-09-10 실제 Chromium에서 교재 iframe의 공식 앱 로딩·키보드 이동, 직접 접속 대안, 오프라인·서비스 실패 안내를 별도로 검증했습니다. 모바일에서는 교재와 연결 안내의 레이아웃을 확인했으며 터치 보행 조작은 검증하지 않았습니다. 브라우저 검증도 AWS 학습·실물 시험의 성공을 증명하지 않습니다.
