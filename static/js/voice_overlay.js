// voice_overlay.js (즉시 반응 + 버그 완벽 수정 버전)
(() => {
  let isManuallyClosing = false; // ✨ [추가] 수동으로 닫고 있는지 상태를 저장할 '깃발'

  // ✨ [추가] 버튼 상태 동기화를 위해 이전 상태를 기억합니다.
  let lastKnownRunningState = false;
  let lastKnownActiveState = false; // 💡 [추가] '활성' 상태도 기억

  function createBars(n = 20) {
      const wave = document.createElement('div');
      wave.className = 'va-wave';
      for (let i = 0; i < n; i++) {
          const bar = document.createElement('div');
          bar.className = 'va-bar';
          wave.appendChild(bar);
      }
      return wave;
  }

  function el(tag, cls) {
      const e = document.createElement(tag);
      if (cls) e.className = cls;
      return e;
  }

  function ensureOverlay() {
      let root = document.getElementById('va-root');
      if (root) return root;

      root = el('div', 'va-overlay');
      root.id = 'va-root';

      const modal = el('div', 'va-modal');
      const center = el('div', 'va-center');
      const ring1 = el('div', 'va-ring');
      const ring2 = el('div', 'va-ring r2');
      const dot = el('div', 'va-dot');
      dot.appendChild(createBars(24));
      center.appendChild(ring1);
      center.appendChild(ring2);
      center.appendChild(dot);

      const labelWrap = el('div', 'va-label');
      const status = el('div', 'va-status');
      status.id = 'va-status';
      status.textContent = '로봇이 듣고 있어요…';
      const hint = el('div', 'va-hint');
      hint.textContent = '“종료”라고 말하면 대화를 종료합니다.';
      labelWrap.appendChild(status);
      labelWrap.appendChild(hint);

      const closeBtn = el('button', 'va-close-btn');
      closeBtn.textContent = '✕';
      closeBtn.title = '닫기';
      closeBtn.addEventListener('click', () => {
          stopVoice(); // 💡 [수정] 이 함수는 이제 'standby'를 호출합니다.
      });
      modal.appendChild(closeBtn);

      modal.appendChild(center);
      modal.appendChild(labelWrap);
      root.appendChild(modal);
      document.body.appendChild(root);
      return root;
  }

  function showOverlay() {
      const root = ensureOverlay();
      root.classList.add('show');
  }

  function hideOverlay() {
      const root = ensureOverlay();
      root.classList.remove('show');
  }

  async function postJSON(url, body) {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
      return await res.json();
  }

  async function getJSON(url) {
      const res = await fetch(url, { cache: 'no-store' });
      return await res.json();
  }

  async function startVoice(options) {
      const payload = {};
      if (options?.apiKey) payload.apiKey = options.apiKey;
      if (options?.model) payload.model = options.model;
      if (options?.requireTrigger !== undefined) payload.requireTrigger = !!options.requireTrigger;
      const data = await postJSON('/api/voice/start', payload);
      if (data.ok) {
          // 팝업은 syncLoop가 띄웁니다.
      } else {
          alert('음성 시작 실패: ' + (data.error || ''));
      }
  }

  // 💡💡💡 --- 여기가 "X 버튼" 수정 부분입니다 --- 💡💡💡
  async function stopVoice() {
      isManuallyClosing = true; // 1. '깃발'을 들어서 syncLoop를 잠시 멈춥니다.

      // 2. UI를 즉시 숨깁니다.
      hideOverlay();

      // 💡 [수정] 'X' 버튼을 누르면 '활성' 상태가 아니므로,
      // main.js의 버튼 상태를 갱신하라는 신호를 보냅니다.
      window.dispatchEvent(new CustomEvent('voiceStateChanged', { detail: { active: false } }));
      lastKnownActiveState = false; // 💡 내부 상태도 즉시 갱신

      try {
          // 3. [핵심 수정] /api/voice/stop 대신 /api/voice/standby 를 호출합니다.
          await postJSON('/api/voice/standby');
      } catch (error) {
          console.error("음성 대기 API 호출 실패:", error);
      } finally {
          // 4. 서버 통신이 끝나면 '깃발'을 내려서 syncLoop를 다시 활성화합니다.
          isManuallyClosing = false;
      }
  }

  //
  // 💡💡💡 --- 여기가 "오버레이 표시" 수정 부분입니다 --- 💡💡💡
  //
  async function syncLoop() {
      // '깃발'이 들려있으면 상태 동기화를 건너뜁니다.
      if (isManuallyClosing) {
          setTimeout(syncLoop, 500); // 👈 1500 -> 500 (반응성 향상)
          return;
      }

      try {
          const data = await getJSON('/api/voice/status');
          const isCurrentlyRunning = !!data?.status?.running;
          const isCurrentlyActive = !!data?.status?.active; // 💡 '활성' 상태

          const root = ensureOverlay();

          // [수정] '활성' 상태일 때만 오버레이를 보여줍니다.
          if (isCurrentlyActive) {
              root.classList.add('show');
          } else {
              root.classList.remove('show');
          }

          // 💡 [수정] '활성' 상태가 변경되었으면, '대화' 버튼에 신호를 보냅니다.
          if (lastKnownActiveState !== isCurrentlyActive) {
               window.dispatchEvent(new CustomEvent('voiceStateChanged', { detail: { active: isCurrentlyActive } }));
          }

          // 💡 [수정] '전원' 상태가 변경되었으면, '대화' 버튼에 신호를 보냅니다.
          if (lastKnownRunningState !== isCurrentlyRunning) {
               window.dispatchEvent(new CustomEvent('voiceStateChanged', { detail: { active: false } })); // 전원이 꺼지면 무조건 비활성
          }

          lastKnownRunningState = isCurrentlyRunning;
          lastKnownActiveState = isCurrentlyActive; // 💡 활성 상태 저장

      } catch (e) {
          // 네트워크 오류는 무시
      } finally {
          setTimeout(syncLoop, 500); // 👈 1500 -> 500 (반응성 향상)
      }
  }
  // 💡💡💡 --- 수정 끝 --- 💡💡💡
  //

  window.VoiceOverlay = {
      show: showOverlay,
      hide: hideOverlay,
      start: startVoice,
      stop: stopVoice,
  };

  window.addEventListener('DOMContentLoaded', () => {
      ensureOverlay();
      syncLoop();
  });
})();
