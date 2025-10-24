(() => {
  const POLL_MS = 2000;
  let currentGameId = null; // 서버 설정(.env)에서 로드됩니다.
  let lastPlayText = ''; // 이전 플레이 텍스트 저장용

  const el = {
      nameAway: document.getElementById('name-away'),
      nameHome: document.getElementById('name-home'),
      runsAway: document.getElementById('runs-away'),
      runsHome: document.getElementById('runs-home'),
      hitsAway: document.getElementById('hits-away'),
      hitsHome: document.getElementById('hits-home'),
      errorsAway: document.getElementById('errors-away'),
      errorsHome: document.getElementById('errors-home'),
      inningNumber: document.getElementById('inning-number'),
      halfIndicator: document.getElementById('half-indicator'),
      lastPlayText: document.getElementById('last-play-text'),
      bases: [
          document.getElementById('base-1'),
          document.getElementById('base-2'),
          document.getElementById('base-3')
      ],
      balls: [
          document.getElementById('ball-1'),
          document.getElementById('ball-2'),
          document.getElementById('ball-3')
      ],
      strikes: [
          document.getElementById('strike-1'),
          document.getElementById('strike-2')
      ],
      outs: [
          document.getElementById('out-1'),
          document.getElementById('out-2'),
          document.getElementById('out-3')
      ],
      ballEl: document.getElementById('ball'),
      fielders: {
          p: document.getElementById('fielder-p'),
          c: document.getElementById('fielder-c'),
          '1b': document.getElementById('fielder-1b'),
          '2b': document.getElementById('fielder-2b'),
          '3b': document.getElementById('fielder-3b'),
          ss: document.getElementById('fielder-ss'),
          lf: document.getElementById('fielder-lf'),
          cf: document.getElementById('fielder-cf'),
          rf: document.getElementById('fielder-rf')
      },
      fielderNames: {
          p: document.getElementById('fielder-name-p'),
          c: document.getElementById('fielder-name-c'),
          '1b': document.getElementById('fielder-name-1b'),
          '2b': document.getElementById('fielder-name-2b'),
          '3b': document.getElementById('fielder-name-3b'),
          ss: document.getElementById('fielder-name-ss'),
          lf: document.getElementById('fielder-name-lf'),
          cf: document.getElementById('fielder-name-cf'),
          rf: document.getElementById('fielder-name-rf')
      }
  };

  async function fetchState() {
      // 게임ID가 있으면 DAUM 프록시, 없으면 로컬 Mock 사용
      if (currentGameId) {
          const url = `/api/daum-state?gameId=${encodeURIComponent(currentGameId)}`;
          const res = await fetch(url, { cache: 'no-store' });
          if (!res.ok) return null;
          return await res.json();
      } else {
          const res = await fetch('/api/game-state?advance=1', { cache: 'no-store' });
          if (!res.ok) return null;
          return await res.json();
      }
  }

  function setDots(dots, n) {
      dots.forEach((d, i) => {
          if (!d) return;
          d.classList.toggle('on', i < n);
      });
  }

  function updateBases(bases) {
      const occupied = [bases.first, bases.second, bases.third];
      el.bases.forEach((b, i) => b && b.classList.toggle('occupied', Boolean(occupied[i])));
  }

  function updateFielders(fielders) {
      if (!fielders) return;
      for (const pos in fielders) {
          const fielderData = fielders[pos];
          if (el.fielders[pos]) {
              el.fielders[pos].classList.toggle('occupied', fielderData.active);
              if (el.fielderNames[pos]) {
                  el.fielderNames[pos].textContent = fielderData.name || '';
              }
          }
      }
  }

  function showPopup(text) {
      const overlay = document.getElementById('popup-overlay');
      const content = document.getElementById('popup-content');

      if (!overlay || !content || !text || text === '경기 시작') return;

      content.textContent = text;
      overlay.classList.add('show');

      // 3초 후 자동으로 숨김
      setTimeout(() => {
          overlay.classList.remove('show');
      }, 3000);
  }

  function updateHalf(half) {
      el.halfIndicator.textContent = half === 'T' ? '▲' : '▼';
      el.halfIndicator.classList.toggle('half-top', half === 'T');
      el.halfIndicator.classList.toggle('half-bottom', half !== 'T');
  }

  function animatePitchIfNeeded(lastEvent) {
      if (!lastEvent || lastEvent.type !== 'pitch') return;
      const ball = el.ballEl;
      if (!ball) return;
      // 애니메이션 재시작
      ball.classList.remove('pitching');
      void ball.offsetWidth; // reflow
      ball.classList.add('pitching');
      ball.addEventListener('animationend', () => {
          ball.classList.remove('pitching');
      }, { once: true });
  }

  function render(state) {
      if (!state) return;
      const { teams, inning, half, count, bases, fielders, last_event } = state;
      el.nameAway.textContent = teams.away.name;
      el.nameHome.textContent = teams.home.name;
      el.runsAway.textContent = teams.away.runs;
      el.runsHome.textContent = teams.home.runs;
      el.hitsAway.textContent = teams.away.hits;
      el.hitsHome.textContent = teams.home.hits;
      el.errorsAway.textContent = teams.away.errors;
      el.errorsHome.textContent = teams.home.errors;
      el.inningNumber.textContent = inning;
      updateHalf(half);
      setDots(el.balls, count.balls);
      setDots(el.strikes, count.strikes);
      setDots(el.outs, count.outs);
      updateBases(bases);
      updateFielders(fielders);

      // 플레이 텍스트 업데이트 및 팝업 표시
      const currentPlayText = last_event?.description ?? '';
      if (currentPlayText && currentPlayText !== lastPlayText && lastPlayText !== '') {
          showPopup(currentPlayText);
      }
      lastPlayText = currentPlayText;
      el.lastPlayText.textContent = currentPlayText;

      animatePitchIfNeeded(last_event);
      maybeSendAction(last_event);
  }

  async function tick() {
      try {
          const state = await fetchState();
          render(state);
      } catch (e) {
          console.error(e);
      } finally {
          setTimeout(tick, POLL_MS);
      }
  }

  // 서버 설정에서 게임 ID를 로드합니다.
  async function loadConfig() {
      try {
          const res = await fetch('/api/config', { cache: 'no-store' });
          if (res.ok) {
              const data = await res.json();
              if (data.ok && data.gameId) {
                  currentGameId = data.gameId;
                  console.log('게임 ID 로드됨:', currentGameId);
              }
          }
      } catch (e) {
          console.error('설정 로드 실패:', e);
      }
  }

  // 시작
  window.addEventListener('DOMContentLoaded', async () => {
      await loadConfig(); // 설정 먼저 로드
      tick(); // 그 다음 게임 상태 폴링 시작
  });
})();

// --- Serial Panel Logic ---
function initSerialPanel() {
  const btn = document.getElementById('serial-btn');
  const panel = document.getElementById('serial-panel');
  const closeBtn = document.getElementById('serial-close');
  const sendBtn = document.getElementById('serial-send');
  const macrosBtn = document.getElementById('serial-macros');
  const motorInput = document.getElementById('serial-motor-id');
  const posInput = document.getElementById('serial-position');
  const speedInput = document.getElementById('serial-speed');

  async function getJSON(url, options) {
      const res = await fetch(url, { cache: 'no-store', ...options });
      return await res.json();
  }

  async function sendCommand() {
      const motor_id = parseInt(motorInput.value, 10);
      const position = parseInt(posInput.value, 10);
      const speed = parseInt(speedInput.value, 10) || 0;
      if (Number.isNaN(motor_id) || Number.isNaN(position)) { 
          alert('ID와 위치를 숫자로 입력하세요.'); 
          return; 
      }
      const data = await getJSON('/api/serial/send', { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify({ motor_id, position, speed }) 
      });
      if (!data.ok) alert('전송 실패: ' + (data.error || ''));
      else console.log('전송 성공:', data);
  }

  // UI 바인딩
  if (btn && panel) {
      btn.addEventListener('click', async () => {
          panel.classList.toggle('open');
      });
  }
  if (closeBtn) closeBtn.addEventListener('click', () => panel.classList.remove('open'));
  if (sendBtn) sendBtn.addEventListener('click', sendCommand);
  if (macrosBtn) macrosBtn.addEventListener('click', () => { window.open('/macros', '_blank'); });
}

window.addEventListener('DOMContentLoaded', initSerialPanel);

function postJSON(url, body) {
  return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(r => r.json());
}

function actionCodeFromEvent(lastEvent) {
  if (!lastEvent || !lastEvent.type) return null;
  const t = lastEvent.type;
  if (t === 'hr') return 1;
  if (t === 'single' || t === 'double' || t === 'triple') return 2;
  if (t === 'ball' || t === 'walk') return 3;
  if (t === 'strike') return 4;
  if (t === 'out') return 5;
  if (t === 'strikeout') return 6;
  return null;
}

let lastActionCodeSent = null;
async function maybeSendAction(lastEvent) {
  const code = actionCodeFromEvent(lastEvent);
  if (code == null) return;
  if (code === lastActionCodeSent) return;
  lastActionCodeSent = code;
  try {
      const res = await postJSON('/api/serial/action', { code });
      if (!res.ok) {
          console.warn('Action send failed', res.error);
      }
  } catch (e) {
      console.warn('Action send error', e);
  }
}


// --- Voice Button Logic ---
function initVoiceButton() {
  const btn = document.getElementById('voice-btn');
  if (!btn) return;

  // 💡 [수정] '활성' 상태를 기준으로 버튼 UI를 토글합니다.
  let isActive = false;

  async function refresh() {
      try {
          const res = await fetch('/api/voice/status', { cache: 'no-store' });
          const data = await res.json();
          if (data && data.ok && data.status) {
              // 💡 [수정] '전원'(running)이 아닌 '활성'(active) 상태를 가져옵니다.
              isActive = !!data.status.active;
              btn.classList.toggle('active', isActive);
          }
      } catch (e) { /* noop */ }
  }

  // 💡💡💡 --- 여기가 "버튼 비활성화" 수정 부분입니다 --- 💡💡💡
  btn.addEventListener('click', async () => {
      // 1. 현재 서버 상태를 즉시 가져옵니다.
      await refresh();

      if (!isActive) {
          // 2. 비활성 상태면: 'start' (활성 모드)로 켭니다.
          const res = await postJSON('/api/voice/start', { requireTrigger: false });
          if (!res.ok) { alert('음성 시작 실패: ' + (res.error || '')); return; }
          btn.classList.add('active'); // 버튼 즉시 활성화
          isActive = true; // 내부 상태 갱신
      } else {
          // 3. 활성 상태면: 'standby' (대기 모드)로 전환합니다.
          const res = await postJSON('/api/voice/standby', {});
          if (!res.ok) { alert('음성 대기 실패: ' + (res.error || '')); return; }
          btn.classList.remove('active'); // 버튼 즉시 비활성화
          isActive = false; // 내부 상태 갱신
      }
  });

  // 💡 [수정] 'voice_overlay.js'의 'syncLoop'가 보내는 신호를 받습니다.
  window.addEventListener('voiceStateChanged', (event) => {
      if (event.detail) {
          isActive = !!event.detail.active;
          btn.classList.toggle('active', isActive);
      }
  });

  // 초기 상태 및 다른 창에서 복귀 시 상태 동기화
  window.addEventListener('focus', refresh);
  setTimeout(refresh, 100);
}

window.addEventListener('DOMContentLoaded', initVoiceButton);

// --- BLDC Panel Logic ---
function initBLDCPanel() {
  const btn = document.getElementById('bldc-btn');
  const panel = document.getElementById('bldc-panel');
  const closeBtn = document.getElementById('bldc-close');

  async function postJSON(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return await res.json();
  }

  async function onClickCommand(e) {
    const el = e.target.closest('[data-cmd]');
    if (!el) return;
    const cmd = el.getAttribute('data-cmd');
    try {
      const data = await postJSON('/api/bldc/command', { command: cmd });
      if (!data.ok) alert('전송 실패: ' + (data.error || ''));
    } catch (err) {
      alert('전송 오류: ' + err);
    }
  }

  if (btn && panel) {
    btn.addEventListener('click', () => {
      panel.classList.toggle('open');
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', () => panel.classList.remove('open'));

  if (panel) panel.addEventListener('click', onClickCommand);
}

window.addEventListener('DOMContentLoaded', initBLDCPanel);