(() => {
  const POLL_MS = 2000;
  let currentGameId = null; // 서버 설정(.env)에서 로드됩니다.
  let lastPlayText = ''; // 이전 플레이 텍스트 저장용
  let lastPopupText = ''; // 이전 팝업 텍스트 저장용
  let victoryPopupDismissed = false; // 우승 팝업이 닫혔는지 여부
  let demoRunning = false;
  let demoPaused = false;
  let forceDemoMode = false;

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
      runnerNames: [
          document.getElementById('runner-name-1'),
          document.getElementById('runner-name-2'),
          document.getElementById('runner-name-3')
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
      },
      batter: document.getElementById('batter'),
      batterName: document.getElementById('batter-name')
  };

  async function fetchState() {
      const useLocal = demoRunning || forceDemoMode || !currentGameId;
      if (!useLocal) {
          const url = `/api/daum-state?gameId=${encodeURIComponent(currentGameId)}`;
          const res = await fetch(url, { cache: 'no-store' });
          if (!res.ok) return null;
          return await res.json();
      }
      // 데모가 실행 중이거나 일시정지 중이면 자동 진행 비활성화
      // 초기 상태에서도 자동 진행 비활성화 (데모 시작 전까지 멈춤)
      const advanceParam = (demoRunning || forceDemoMode) ? '' : '';
      const res = await fetch(`/api/game-state${advanceParam}`, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
  }

  function setDots(dots, n) {
      dots.forEach((d, i) => {
          if (!d) return;
          d.classList.toggle('on', i < n);
      });
  }

  function updateBases(bases, state) {
      const occupied = [bases.first, bases.second, bases.third];
      const runners = state?.runners || {first: "", second: "", third: ""};
      const runnerNames = [runners.first, runners.second, runners.third];
      const half = state?.half || 'T';
      const teamSide = half === 'T' ? 'away' : 'home';
      
      el.bases.forEach((b, i) => {
          if (!b) return;
          const isOccupied = Boolean(occupied[i]);
          b.classList.toggle('occupied', isOccupied);
          
          // 주자 이름 표시
          const runnerNameEl = el.runnerNames[i];
          if (runnerNameEl) {
              if (isOccupied && runnerNames[i]) {
                  runnerNameEl.textContent = runnerNames[i];
              } else if (isOccupied) {
                  // last_event에서 선수 이름 추출 시도
                  const eventDesc = state?.last_event?.description || '';
                  const nameMatch = eventDesc.match(/^([가-힣]{2,4})[,\s]/);
                  if (nameMatch) {
                      runnerNameEl.textContent = nameMatch[1];
                  } else {
                      runnerNameEl.textContent = '주자';
                  }
              } else {
                  runnerNameEl.textContent = '';
              }
          }
      });
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

  function updateBatter(batter) {
      if (!batter) return;
      if (el.batter) {
          el.batter.classList.toggle('active', batter.active || false);
          if (el.batterName) {
              el.batterName.textContent = batter.name || '';
          }
      }
  }
  
  function updateTeamColors(teams, half) {
      // half가 'T'면 away팀이 공격, 'B'면 home팀이 공격
      const battingTeam = half === 'T' ? teams.away.name : teams.home.name;
      const fieldingTeam = half === 'T' ? teams.home.name : teams.away.name;
      
      // 삼성 = 파란색, 기아 = 빨간색
      const battingColor = (battingTeam === '삼성') ? 'blue' : 'red';
      const fieldingColor = (fieldingTeam === '삼성') ? 'blue' : 'red';
      
      // 타자 색상 업데이트
      if (el.batter) {
          el.batter.classList.remove('team-red', 'team-blue');
          el.batter.classList.add(`team-${battingColor}`);
      }
      if (el.batterName) {
          el.batterName.classList.remove('team-red', 'team-blue');
          el.batterName.classList.add(`team-${battingColor}`);
      }
      
      // 주자 색상 업데이트
      el.runnerNames.forEach(runnerNameEl => {
          if (runnerNameEl) {
              runnerNameEl.classList.remove('team-red', 'team-blue');
              runnerNameEl.classList.add(`team-${battingColor}`);
          }
      });
      
      // 수비수 색상 업데이트
      Object.values(el.fielders).forEach(fielderEl => {
          if (fielderEl) {
              fielderEl.classList.remove('team-red', 'team-blue');
              fielderEl.classList.add(`team-${fieldingColor}`);
          }
      });
      
      // 수비수 이름 색상 업데이트
      Object.values(el.fielderNames).forEach(fielderNameEl => {
          if (fielderNameEl) {
              fielderNameEl.classList.remove('team-red', 'team-blue');
              fielderNameEl.classList.add(`team-${fieldingColor}`);
          }
      });
      
      // 팀명 색상 업데이트 (왼쪽 위 메뉴)
      const awayTeamColor = (teams.away.name === '삼성') ? 'blue' : 'red';
      const homeTeamColor = (teams.home.name === '삼성') ? 'blue' : 'red';
      
      if (el.nameAway) {
          el.nameAway.classList.remove('team-red', 'team-blue');
          el.nameAway.classList.add(`team-${awayTeamColor}`);
      }
      if (el.nameHome) {
          el.nameHome.classList.remove('team-red', 'team-blue');
          el.nameHome.classList.add(`team-${homeTeamColor}`);
      }
  }

  const NON_GAME_POPUP_TYPES = new Set(['info', 'chant']);
  
  // 경기 플레이 이벤트만 팝업 표시 (경기 내용 관련)
  const GAME_PLAY_EVENTS = new Set(['start', 'strikeout', 'hr', 'single', 'double', 'triple', 'out', 'sac_fly', 'walk', 'error', 'live', 'change', 'ball', 'strike']);

  function isGameEvent(event) {
      if (!event || !event.type) return false;
      return !NON_GAME_POPUP_TYPES.has(event.type);
  }
  
  function isGamePlayEvent(event) {
      if (!event || !event.type) return false;
      return GAME_PLAY_EVENTS.has(event.type);
  }

  function showPopup(text, isVictory = false) {
      const overlay = document.getElementById('popup-overlay');
      const content = document.getElementById('popup-content');
      const stage = document.querySelector('.stage');

      if (!overlay || !content || !text || text.trim() === '') return;

      content.textContent = text;
      
      // 우승 모드 설정
      if (isVictory) {
          overlay.classList.add('victory');
          if (stage) {
              stage.classList.add('victory-mode');
          }
          
          // 기존 이벤트 리스너 제거 (중복 방지)
          overlay.onclick = null;
          overlay.ontouchstart = null;
          
          // 우승 팝업은 클릭/터치로만 닫기 가능 (자동으로 사라지지 않음)
          // 명시적으로 setTimeout을 사용하지 않아 계속 표시됨
          const closeVictoryPopup = function(e) {
              if (e) {
                  e.stopPropagation();
                  e.preventDefault();
              }
              overlay.classList.remove('show');
              overlay.classList.remove('victory');
              if (stage) {
                  stage.classList.remove('victory-mode');
              }
              overlay.onclick = null;
              overlay.ontouchstart = null;
              // 우승 팝업이 닫혔음을 표시하여 다시 표시되지 않도록 함
              victoryPopupDismissed = true;
              lastPopupText = ''; // 팝업 텍스트도 리셋
          };
          
          overlay.onclick = closeVictoryPopup;
          overlay.ontouchstart = closeVictoryPopup;
          
          // 자동으로 사라지지 않도록 명시적으로 설정
          // setTimeout을 사용하지 않음
      } else {
          overlay.classList.remove('victory');
          if (stage) {
              stage.classList.remove('victory-mode');
          }
          overlay.onclick = null;
          overlay.ontouchstart = null;
          
          // 일반 팝업은 3초 후 자동으로 숨김
          setTimeout(() => {
              overlay.classList.remove('show');
          }, 3000);
      }
      
      overlay.classList.add('show');
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
      const { teams, inning, half, count, bases, fielders, batter, last_event } = state;
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
      updateBases(bases, state);
      updateFielders(fielders);
      updateBatter(batter);
      
      // 팀별 색상 업데이트 (삼성=파란색, 기아=빨간색)
      updateTeamColors(teams, half);

      // 플레이 텍스트 업데이트 및 팝업 표시
      const currentPlayText = last_event?.description ?? '';
      const popupText = last_event?.popup_description;  // None이거나 문자열
      const hasPopupText = popupText && popupText.trim() !== '';
      const isVictory = last_event?.type === 'end' || (hasPopupText && popupText.includes('우승'));
      const overlay = document.getElementById('popup-overlay');
      const isVictoryPopupShowing = overlay && overlay.classList.contains('show') && overlay.classList.contains('victory');
      
      // 경기 플레이 이벤트인지 확인
      const isGamePlay = isGamePlayEvent(last_event);
      
      // 팝업에 표시할 텍스트: popup_description이 있으면 그것을, 없으면 description 사용
      const displayText = hasPopupText ? popupText : currentPlayText;
      
      // 왼쪽 아래 경기 진행 텍스트: 경기 플레이 이벤트만 표시
      // 응원가(chant), 휴식(info) 등은 완전히 무시 (이전 텍스트 유지)
      if (isGamePlay) {
          el.lastPlayText.textContent = displayText || '';
      } else if (isVictory && hasPopupText && popupText.includes('우승')) {
          // 우승 팝업 텍스트만 표시
          el.lastPlayText.textContent = popupText;
      }
      // 응원가, 휴식 등은 진행중 텍스트를 업데이트하지 않음 (이전 텍스트 유지)
      
      // 우승 팝업은 항상 표시하고, 다른 팝업으로 덮어씌우지 않음
      // 단, 이미 닫힌 경우 다시 표시하지 않음
      if (isVictory && hasPopupText && !victoryPopupDismissed) {
          // 이미 우승 팝업이 표시 중이면 새로 표시하지 않음
          if (!isVictoryPopupShowing || popupText !== lastPopupText) {
              showPopup(popupText, true);
              lastPopupText = popupText;
          }
      } 
      // 경기 플레이 이벤트면 무조건 팝업 표시 (경기 진행 텍스트와 동일한 텍스트)
      // 단, 우승 팝업이 표시 중이면 일반 팝업은 표시하지 않음
      // 응원가(chant), 휴식(info) 등은 팝업 표시 안 함
      else if (isGamePlay && !isVictoryPopupShowing) {
          // 경기 진행 텍스트가 변경되었으면 팝업도 표시 (싱크 맞추기)
          // 공수 교대(change)도 팝업으로 표시
          // currentPlayText와 lastPlayText를 비교하여 변경되었으면 팝업 표시
          if (displayText && displayText.trim() !== '') {
              // 이전 경기 이벤트와 다른 텍스트면 팝업 표시
              // lastPlayText가 빈 문자열이면 첫 이벤트이므로 팝업 표시
              // displayText와 lastPopupText를 비교하여 중복 방지
              const textChanged = displayText !== lastPopupText;
              if (textChanged || lastPlayText === '' || lastPopupText === '') {
                  showPopup(displayText, false);
                  lastPopupText = displayText;
              }
          }
      }
      // 응원가, 휴식 등은 팝업 표시 안 함 (아무것도 하지 않음)
      
      // 경기 플레이 이벤트일 때만 lastPlayText 업데이트 (응원가 등은 업데이트 안 함)
      // 이렇게 하면 응원가 step이 lastPlayText를 변경하지 않아서 다음 경기 이벤트 팝업이 정상 표시됨
      if (isGamePlay) {
          lastPlayText = currentPlayText;
      }
      
      // 경기 이벤트가 아니면 lastPopupText는 리셋하지 않음 (다음 경기 이벤트 팝업을 위해 유지)
      // 경기 이벤트가 아니고 popup_description도 없으면 lastPopupText 리셋 (단, 우승 팝업은 유지)
      if (!isGamePlay && !hasPopupText && !isVictory) {
          lastPopupText = '';
      }

      animatePitchIfNeeded(last_event);
      maybeSendAction(last_event);

      if (typeof state.demo_active === 'boolean' && state.demo_active !== demoRunning) {
          demoRunning = state.demo_active;
          updateDemoButton();
          // 데모가 끝났을 때 경기 종료 상태로 유지
          if (!demoRunning && last_event && last_event.type === 'end') {
              forceDemoMode = true;
          }
      }
      if (typeof state.demo_paused === 'boolean' && state.demo_paused !== demoPaused) {
          demoPaused = state.demo_paused;
          updateDemoButton();
      }
      if (Object.prototype.hasOwnProperty.call(state, 'demo_step')) {
          updateDemoCaption(state.demo_step);
      }
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

  async function fetchDemoStatus() {
      try {
          const res = await fetch('/api/demo/status', { cache: 'no-store' });
          if (!res.ok) return;
          const data = await res.json();
          demoRunning = Boolean(data.running);
          demoPaused = Boolean(data.paused);
          updateDemoButton();
          updateDemoCaption(data.step);
      } catch (err) {
          console.warn('데모 상태 조회 실패:', err);
      }
  }

  function updateDemoCaption(stepText) {
      const caption = document.querySelector('.demo-caption');
      if (!caption) return;
      if (demoRunning && stepText) {
          caption.textContent = `진행 중: ${stepText}`;
      } else if (demoRunning) {
          caption.textContent = '데모 시퀀스 진행 중...';
      } else {
          caption.textContent = '버튼을 눌러 시나리오를 재생하세요';
      }
  }

  function updateDemoButton() {
      const btn = document.getElementById('demo-start-btn');
      if (!btn) return;
      if (demoRunning) {
          btn.disabled = false;
          btn.textContent = demoPaused ? '데모 재시작' : '데모 멈춤';
      } else {
          btn.disabled = false;
          btn.textContent = '데모 시작';
      }
  }

  async function toggleDemo() {
      const btn = document.getElementById('demo-start-btn');
      if (!btn) return;
      
      // 데모가 실행 중이면 멈춤/재시작
      if (demoRunning) {
          if (demoPaused) {
              // 재시작
              try {
                  const res = await fetch('/api/demo/resume', { method: 'POST' });
                  if (!res.ok) {
                      const err = await res.json().catch(() => ({}));
                      alert('데모 재시작에 실패했습니다.' + (err.error ? ` (${err.error})` : ''));
                      return;
                  }
                  demoPaused = false;
                  updateDemoButton();
              } catch (err) {
                  console.error('데모 재시작 실패:', err);
                  alert('데모 재시작 요청 중 오류가 발생했습니다.');
              }
          } else {
              // 멈춤
              try {
                  const res = await fetch('/api/demo/pause', { method: 'POST' });
                  if (!res.ok) {
                      const err = await res.json().catch(() => ({}));
                      alert('데모 멈춤에 실패했습니다.' + (err.error ? ` (${err.error})` : ''));
                      return;
                  }
                  demoPaused = true;
                  updateDemoButton();
              } catch (err) {
                  console.error('데모 멈춤 실패:', err);
                  alert('데모 멈춤 요청 중 오류가 발생했습니다.');
              }
          }
      } else {
          // 데모 시작
          btn.disabled = true;
          updateDemoCaption('데모 준비 중...');
          // 데모 시작 시 우승 팝업 관련 상태 리셋 (다시 팝업이 뜰 수 있도록)
          victoryPopupDismissed = false;
          lastPopupText = '';
          // 팝업 오버레이도 닫힌 상태로 리셋
          const overlay = document.getElementById('popup-overlay');
          if (overlay) {
              overlay.classList.remove('show', 'victory');
              const stage = document.querySelector('.stage');
              if (stage) {
                  stage.classList.remove('victory-mode');
              }
          }
          try {
              const res = await fetch('/api/demo/start', { method: 'POST' });
              if (!res.ok) {
                  const err = await res.json().catch(() => ({}));
                  alert('데모 시작에 실패했습니다.' + (err.error ? ` (${err.error})` : ''));
                  demoRunning = false;
                  updateDemoCaption(null);
                  updateDemoButton();
                  return;
              }
              demoRunning = true;
              demoPaused = false;
              forceDemoMode = true;
          } catch (err) {
              console.error('데모 시작 실패:', err);
              alert('데모 시작 요청 중 오류가 발생했습니다.');
          } finally {
              updateDemoButton();
          }
      }
  }

  function initDemoButton() {
      const btn = document.getElementById('demo-start-btn');
      if (!btn) return;
      btn.addEventListener('click', toggleDemo);
      updateDemoButton();
  }

  // 시작
  window.addEventListener('DOMContentLoaded', async () => {
      await loadConfig(); // 설정 먼저 로드
      initDemoButton();
      await fetchDemoStatus();
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


// --------------------------------------------------------------------------------
// 🌟 PTT 방식 통합: Voice Button Logic 🌟
// 첫 번째 코드의 '활성/비활성' 토글 대신, 두 번째 코드의 '팝업 표시' 로직을 사용합니다.
// --------------------------------------------------------------------------------
function initVoiceButton() {
    const btn = document.getElementById('voice-btn');
    if (!btn) return;

    // 마이크 버튼 클릭 시, PTT 기능을 가진 음성 오버레이 팝업을 표시합니다.
    btn.addEventListener('click', () => {
        // 'window.VoiceOverlay'는 외부 스크립트(예: voice_overlay.js)에 정의되어 있어야 합니다.
        if (window.VoiceOverlay) {
            window.VoiceOverlay.show(); // 팝업(오버레이) 표시
        } else {
            alert("음성 오버레이를 로드하지 못했습니다. (PTT 기능 스크립트 누락)");
        }
    });
    
    // 참고: PTT 팝업 방식에서는 활성 상태를 동기화하는 기존 로직(refresh, voiceStateChanged)은 제거했습니다.
}

window.addEventListener('DOMContentLoaded', initVoiceButton);


// --- BLDC Panel Logic ---
function initBLDCPanel() {
// ... (BLDC Panel Logic은 변경 없음)
  const btn = document.getElementById('bldc-btn');
  const panel = document.getElementById('bldc-panel');
  const closeBtn = document.getElementById('bldc-close');

  async function postJSON(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    return await res.json();
  }

  let holdTimer = null;
  let holdCmd = null;
  let sending = false;

  async function sendCommand(cmd) {
    if (sending) return; // 간단한 동시 전송 방지
    sending = true;
    try {
      const data = await postJSON('/api/bldc/command', { command: cmd });
      if (!data.ok) console.warn('전송 실패:', data.error);
    } catch (err) {
      console.warn('전송 오류:', err);
    } finally {
      sending = false;
    }
  }

  function startHold(cmd) {
    if (!cmd) return;
    if (holdCmd === cmd && holdTimer) return;
    stopHold(true);
    holdCmd = cmd;
    // 즉시 한 번 전송 후 주기 전송 (아두이노 200ms 타임아웃 대비)
    sendCommand(cmd);
    holdTimer = setInterval(() => sendCommand(cmd), 150);
  }

  function stopHold(silent) {
    if (holdTimer) {
      clearInterval(holdTimer);
      holdTimer = null;
    }
    const hadCmd = !!holdCmd;
    holdCmd = null;
    if (!silent && hadCmd) {
      sendCommand('stop');
    }
  }

  function onPointerDown(e) {
    const el = e.target.closest('[data-cmd]');
    if (!el || !panel || !panel.contains(el)) return;
    e.preventDefault();
    const cmd = el.getAttribute('data-cmd');
    if (cmd === 'stop') {
      stopHold(true);
      sendCommand('stop');
      return;
    }
    startHold(cmd);
  }

  function onPointerUp() {
    stopHold(false);
  }

  if (btn && panel) {
    btn.addEventListener('click', () => {
      if (!panel.classList.contains('open')) {
        panel.classList.add('open');
      } else {
        stopHold(false);
        panel.classList.remove('open');
      }
    });
  }
  if (closeBtn) closeBtn.addEventListener('click', () => { stopHold(false); panel.classList.remove('open'); });

  if (panel) {
    panel.addEventListener('pointerdown', onPointerDown);
  }
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', () => stopHold(false));
  window.addEventListener('blur', () => stopHold(false));
}

window.addEventListener('DOMContentLoaded', initBLDCPanel);

// --- BLE Panel Logic ---
function initBLEPanel() {
// ... (BLE Panel Logic은 변경 없음)
  const btn = document.getElementById('ble-btn');
  const panel = document.getElementById('ble-panel');
  const closeBtn = document.getElementById('ble-close');
  const el = {
    mode: document.getElementById('ble-mode'),
    running: document.getElementById('ble-running'),
    adv: document.getElementById('ble-adv'),
    last: document.getElementById('ble-last'),
    start: document.getElementById('ble-start'),
    stop: document.getElementById('ble-stop'),
    refresh: document.getElementById('ble-refresh'),
    msg: document.getElementById('ble-msg'),
    send: document.getElementById('ble-send'),
  };

  function setPanelOpen(open) {
    if (!panel) return;
    panel.classList.toggle('open', open);
  }

  async function getJSON(url, options) {
    const res = await fetch(url, { cache: 'no-store', ...options });
    return await res.json();
  }
  async function postJSON(url, body) {
    const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
    return await res.json();
  }

  async function refresh() {
    try {
      const data = await getJSON('/api/ble/status');
      if (data && data.ok) {
        if (el.mode) el.mode.textContent = data.mode || '-';
        if (el.running) el.running.textContent = data.running ? 'ON' : 'OFF';
        if (el.adv) el.adv.textContent = data.advertising ? 'ON' : 'OFF';
        if (el.last) el.last.textContent = data.last_received || '';
      }
    } catch (e) {
      console.warn('BLE status error', e);
    }
  }

  if (btn) btn.addEventListener('click', async () => { setPanelOpen(!panel.classList.contains('open')); if (panel.classList.contains('open')) await refresh(); });
  if (closeBtn) closeBtn.addEventListener('click', () => setPanelOpen(false));
  if (el.refresh) el.refresh.addEventListener('click', refresh);
  if (el.start) el.start.addEventListener('click', async () => { const r = await postJSON('/api/ble/start'); if (!r.ok) alert('시작 실패'); else refresh(); });
  if (el.stop) el.stop.addEventListener('click', async () => { const r = await postJSON('/api/ble/stop'); if (!r.ok) alert('중지 실패'); else refresh(); });
  if (el.send) el.send.addEventListener('click', async () => { const msg = (el.msg && el.msg.value || '').trim(); if (!msg) return; const r = await postJSON('/api/ble/simulate-write', { message: msg }); if (!r.ok) alert('전송 실패'); else refresh(); });
}

window.addEventListener('DOMContentLoaded', initBLEPanel);
