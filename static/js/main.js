// main.js (야구 + 시리얼 + PTT 버튼)
(() => {
    const POLL_MS = 2000;
    const HARDCODED_GAME_ID = '80099695';
    let currentGameId = HARDCODED_GAME_ID || null;
    let lastPlayText = ''; 

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

    window.addEventListener('DOMContentLoaded', () => {
        tick();
    });
})();

// --- Serial Panel Logic (변경 없음) ---
function initSerialPanel() {
    const btn = document.getElementById('serial-btn');
    const panel = document.getElementById('serial-panel');
    const closeBtn = document.getElementById('serial-close');
    const sendBtn = document.getElementById('serial-send');
    const macrosBtn = document.getElementById('serial-macros');
    const motorInput = document.getElementById('serial-motor-id');
    const posInput = document.getElementById('serial-position');

    async function getJSON(url, options) {
        const res = await fetch(url, { cache: 'no-store', ...options });
        return await res.json();
    }

    async function sendCommand() {
        const motor_id = parseInt(motorInput.value, 10);
        const position = parseInt(posInput.value, 10);
        if (Number.isNaN(motor_id) || Number.isNaN(position)) { alert('ID와 위치를 숫자로 입력하세요.'); return; }
        const data = await getJSON('/api/serial/send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ motor_id, position }) });
        if (!data.ok) alert('전송 실패: ' + (data.error || ''));
    }

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


// --- Voice Button Logic (변경 없음) ---
function initVoiceButton() {
    const btn = document.getElementById('voice-btn');
    if (!btn) return;

    btn.addEventListener('click', () => {
        if (window.VoiceOverlay) {
            window.VoiceOverlay.show();
        } else {
            alert("음성 오버레이를 로드하지 못했습니다.");
        }
    });
}
window.addEventListener('DOMContentLoaded', initVoiceButton);
