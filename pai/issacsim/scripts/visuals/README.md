# 설명용 3D 실습장

실습 코드의 `make_layout(42)` 배치를 Three.js 메시로 보여 주는 학습용 자료입니다.
벽 4개·상자 8개, 로봇의 초기 XY·방향과 센서 오프셋은 실제 소스에서 읽습니다.
브라우저와 정지 그림은 같은 `scene.mjs`의 3D 형상을 사용합니다.

- [회전·확대 가능한 오프라인 뷰어](../../static/visuals/arena-3d.html)
- [교재용 PNG](../../static/images/concepts/sim-arena-3d.png)
- [편집 가능한 벡터 SVG](../../static/images/concepts/sim-arena-3d.svg)
- [Three.js 라이선스](../../static/visuals/THIRD_PARTY_LICENSES.txt)

## 무엇을 보여 주나요?

실습장 안쪽은 6×6 m이고, 상자는 각각 0.45×0.45×0.50 m입니다.
로봇 위치를 표시하는 고리는 차체나 충돌 경계가 아닙니다.
근사 로봇 형상은 TurtleBot3 Burger를 참고해 직접 만든 메시이며 공식 USD 자산이 아닙니다.
정지 그림 오른쪽 로봇은 별도 배율로 확대했습니다.

센서의 base_footprint 기준 오프셋은 `(−0.032, 0, 0.182) m`입니다.
이 시각화에서는 base_footprint를 바닥 `z=0`에 두며, XY·yaw는 실제 seed 42 값을 유지합니다.
실제 시뮬레이터는 초기 자세·접촉·물리 해석으로 높이가 달라질 수 있습니다.

표시 광선은 72개이며 실습 런타임의 360개 중 일부 방향을 보여 줍니다.
각 수평 광선은 첫 벽·상자 또는 최대 3.5 m에서 끝납니다.
주황색은 전방 두 구역, 청록색은 나머지 방향입니다.
벽 표시를 꺼도 광선의 교차 계산에는 벽이 계속 포함됩니다.

**설명용 3D 모델 · 실제 Isaac Sim 실행 화면이 아닙니다.**
이 뷰어는 물리 엔진·주행 정책·실제 센서·학습 데이터 생성 기능을 실행하지 않습니다.
실제 Camera 결과는 교재의 Isaac Sim 실습을 실행하여 얻어야 합니다.

## 조작

- 마우스 드래그 또는 한 손가락: 회전. 휠 또는 두 손가락: 확대·축소.
- 오른쪽 드래그: 화면 안에서 이동.
- **기본 시점 / 위에서 보기 / 로봇 확대**: 정해진 카메라 위치로 이동.
- 장면에 키보드 초점을 둔 뒤 방향키: 회전. `+`/`−`: 확대·축소.
- `1`/`2`/`3`: 시점 선택. `Home`: 기본 시점. **처음으로**: 표시 옵션도 복원.
- 교재의 iframe 안에서는 `Escape`로 교재에 닫기 요청을 보냅니다. 단독 파일에서는 보내지 않습니다.

자동 회전이나 유휴 상태의 반복 렌더링이 없습니다. 조작·크기 변경 때만 그립니다.
WebGL을 시작하지 못하면 같은 배치의 정지 이미지와 안내 문구를 표시합니다.

## 재생성

필요 도구는 **Node.js 22 이상**, Python 3.10 이상과 NumPy,
`rsvg-convert`(librsvg), 한국어 글꼴입니다. 생성 환경은 Node.js 22.22.2,
NumPy 2.4.2이며 PNG는 Apple SD Gothic Neo로 렌더링했습니다.
글꼴이 없는 Linux에서는 Noto Sans CJK KR을 준비하세요.

저장소 루트에서:

```bash
cd scripts/visuals
npm ci --no-audit --no-fund
npm run build
npm run check
```

최초 `npm ci`는 네트워크가 필요합니다. 의존성 설치 후 빌드에는 외부 서비스가 필요 없습니다.
생성한 `arena-3d.html`은 JavaScript·정지 PNG·라이선스를 모두 내장합니다.
CDN·외부 이미지·fetch·worker·저장소 API를 사용하지 않으며 `file://`에서 열 수 있습니다.
교재는 이 전체 HTML을 `sandbox="allow-scripts"`인 iframe의 `srcdoc`에 넣을 수 있습니다.
`Escape` 입력 시 부모에게 `{type: "physical-ai-scene-close"}` 메시지를 보냅니다.
호스트는 현재 iframe의 `contentWindow`와 `event.source`가 일치하는지 및 정확한 메시지 타입을 확인한 뒤 닫아야 합니다.

고정 의존성은 `three@0.180.0`, `esbuild@0.25.9`, `jsdom@26.1.0`입니다.
`package-lock.json`으로 하위 의존성도 고정했습니다. `node_modules/`는 배포하지 않습니다.

## 소스와 생성물

| 파일 | 역할 |
|---|---|
| `export_layout.py` | 실제 `make_layout(42)`·공통 상수·센서 오프셋 읽기 |
| `layout.json` | 추출한 배치·자세·72개 기준 거리·원본 SHA-256 |
| `scene.mjs` | 브라우저와 SVG가 함께 사용하는 Three.js 메시·광선 |
| `viewer.mjs` | WebGL·OrbitControls·버튼·키보드·실패 시 정지 이미지 |
| `build.mjs` | SVGRenderer → SVG → PNG, IIFE와 PNG를 단일 HTML에 내장 |
| `verify.mjs` | 형상·광선·파일·오프라인 구성·UI 이벤트 검사 |

생성물은 `static/visuals/arena-3d.html`, `static/visuals/THIRD_PARTY_LICENSES.txt`,
`static/images/concepts/sim-arena-3d.svg`, `static/images/concepts/sim-arena-3d.png`입니다.
HTML과 PNG·SVG는 자동 생성물이므로 소스를 고친 후 `npm run build`로 다시 만드세요.

## 검증 범위

`npm run check`는 원본 해시, 12개 상자의 위치·크기, 로봇 자세,
72개 광선과 Python `expected_scan()`의 독립 거리 비교를 검사합니다.
PNG CRC·픽셀 크기·압축 데이터와 SVG XML·실제 투영 경로, HTML 스크립트 문법,
외부 리소스 부재, 내장 PNG 일치와 라이선스도 확인합니다.

JSDOM에서는 WebGL 실패 시 정지 이미지와 안내가 나오는지 실행합니다.
Three.js와 OrbitControls를 유지하고 렌더러만 대체한 이벤트 검사로 시점 버튼·키보드·
광선/벽 표시·초기화 및 유휴 프레임 0을 확인합니다.
뒤로가기 캐시에 보존된 페이지를 두 번 복원한 뒤 휠 조작이 유지되는지, 실제 종료에서만
렌더러를 해제하는지도 이벤트로 검사합니다.
**이 검사는 실제 브라우저의 WebGL·GPU·마우스·터치 렌더링 검사를 대신하지 않습니다.**
실제 AWS·Isaac Sim·ROS·로봇 동작 역시 이 생성 도구의 검증 대상이 아닙니다.

## 출처와 라이선스

- 배치: `static/code/sim/scene_math.py`의 `make_layout(42)`.
- 거리·구역: `static/code/workshop_core.py`의 `MAX_RANGE`, `NUM_SECTORS`.
- 센서 위치: `static/code/sim/run_sim.py`의 `SCAN_OFFSET`.
- [Three.js r180 SVGRenderer](https://github.com/mrdoob/three.js/blob/r180/examples/jsm/renderers/SVGRenderer.js): 실제 3D 메시를 SVG에 투영. SVG 출력에는 WebGL의 그림자가 없습니다.
- [Three.js r180 OrbitControls](https://github.com/mrdoob/three.js/blob/r180/examples/jsm/controls/OrbitControls.js): 카메라 조작. 자동 회전·damping은 끄고 변경 이벤트에만 렌더링합니다.

Three.js와 동봉된 OrbitControls는 MIT 라이선스입니다.
전체 고지문은 단일 HTML의 라이선스 펼침 영역과 별도 `THIRD_PARTY_LICENSES.txt`에 포함했습니다.
JSDOM·esbuild는 빌드·검증에만 사용하며 브라우저 파일에 포함하지 않습니다.
