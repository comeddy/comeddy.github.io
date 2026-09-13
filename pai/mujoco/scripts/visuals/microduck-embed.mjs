// Shared by the standalone page and the handbook dialog. No provider assets are bundled.
export const MICRODUCK_SPACE = 'https://huggingface.co/spaces/pollen-robotics/microduck-simulator';
export const MICRODUCK_EMBED = 'https://pollen-robotics-microduck-simulator.hf.space';

export function mountMicroduck(container, {autoStart = false} = {}) {
  container.innerHTML = `<section class="microduck-embed" aria-label="공식 Microduck 시뮬레이터">
    <div class="microduck-intro"><div><span class="microduck-kicker">POLLEN ROBOTICS · LIVE SIMULATOR</span>
    <h2>Microduck을 직접 움직여 보세요.</h2>
    <p>앱에서 <b>WADDLE IN</b>을 누른 뒤 방향키로 이동, 드래그로 회전, 스크롤로 확대합니다.</p></div>
    <div class="microduck-actions"><button type="button" data-sim-start>시뮬레이터 실행</button>
    <a href="${MICRODUCK_SPACE}" target="_blank" rel="noopener noreferrer">공식 Space 새 탭 ↗</a>
    <button type="button" data-sim-stop hidden>실행 종료</button></div></div>
    <p class="microduck-status" role="status" aria-live="polite">실행하면 Hugging Face의 외부 앱을 불러옵니다. 인터넷 연결이 필요합니다.</p>
    <div class="microduck-stage"><div class="microduck-placeholder"><b>공식 Microduck · MuJoCo + ONNX</b><span>실행 버튼을 눌러 브라우저에서 로봇을 만나세요.</span></div></div>
    <p class="microduck-footnote">공식 데모의 사전학습 정책을 체험합니다. AWS 실습 체크포인트나 실물 로봇에는 연결되지 않습니다.
    화면이 열리지 않거나 느리면 공식 Space를 새 탭에서 여세요. 데모는 다른 방문자와 가상 로봇 위치를 공유할 수 있습니다.</p>
  </section>`;
  const stage = container.querySelector('.microduck-stage');
  const status = container.querySelector('.microduck-status');
  const start = container.querySelector('[data-sim-start]');
  const stop = container.querySelector('[data-sim-stop]');
  let timer;
  function stopApp() {
    clearTimeout(timer);
    stage.innerHTML = '<div class="microduck-placeholder"><b>시뮬레이터가 종료되었습니다.</b><span>다시 실행할 수 있습니다.</span></div>';
    stop.hidden = true;
    start.textContent = '시뮬레이터 실행';
    status.textContent = '실행을 종료했습니다. 이 페이지의 외부 시뮬레이터 연결을 닫았습니다.';
  }
  function startApp() {
    clearTimeout(timer);
    if (!navigator.onLine) {
      status.textContent = '현재 오프라인입니다. 인터넷에 연결한 뒤 다시 실행하거나 공식 Space를 새 탭에서 여세요.';
      return;
    }
    const frame = document.createElement('iframe');
    frame.title = 'Pollen Robotics 공식 Microduck 시뮬레이터';
    frame.src = MICRODUCK_EMBED;
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-pointer-lock');
    frame.setAttribute('allow', 'fullscreen; gamepad');
    frame.referrerPolicy = 'no-referrer';
    stage.replaceChildren(frame);
    stop.hidden = false;
    start.textContent = '다시 불러오기';
    status.textContent = '공식 앱을 불러오는 중입니다. 앱의 WADDLE IN 버튼을 눌러 시작하세요. 첫 실행에는 모델 로딩 시간이 필요합니다.';
    // Cross-origin iframe load events cannot establish that its physics/policy is ready.
    timer = setTimeout(() => {
      status.textContent = '앱이 표시되면 WADDLE IN을 눌러 시작하세요. 화면이 비어 있거나 로딩이 계속되면 공식 Space를 새 탭에서 여세요.';
    }, 20000);
  }
  start.addEventListener('click', startApp);
  stop.addEventListener('click', stopApp);
  if (autoStart) startApp();
  return () => { clearTimeout(timer); container.replaceChildren(); };
}
