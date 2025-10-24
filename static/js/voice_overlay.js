// voice_overlay.js (PTT + 대화창 + Base64 오디오 재생)
(() => {
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    // --- 1. CSS 주입 (변경 없음) ---
    function injectStyles() {
        if (document.getElementById('va-styles')) return;
        const style = document.createElement('style');
        style.id = 'va-styles';
        style.innerHTML = `
            .va-convo {
                width: 100%;
                max-height: 100px;
                overflow-y: auto;
                padding: 10px;
                box-sizing: border-box;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                margin-top: 15px;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .va-convo-msg {
                padding: 8px 12px;
                border-radius: 12px;
                font-size: 15px;
                line-height: 1.4;
                max-width: 90%;
            }
            .va-convo-msg.user {
                background: #e1e1e1;
                color: #333;
                align-self: flex-end;
                text-align: right;
            }
            .va-convo-msg.ai {
                background: #3478f6;
                color: white;
                align-self: flex-start;
                text-align: left;
            }
        `;
        document.head.appendChild(style);
    }

    // --- 2. UI 생성 (변경 없음) ---
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

        injectStyles(); 

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
        status.textContent = '버튼을 눌러 대화를 시작하세요';
        
        const convo = el('div', 'va-convo');
        convo.id = 'va-convo';

        labelWrap.appendChild(status);
        labelWrap.appendChild(convo); 

        const closeBtn = el('button', 'va-close-btn');
        closeBtn.textContent = '✕';
        closeBtn.title = '닫기';
        closeBtn.addEventListener('click', () => {
            hideOverlay();
            if (isRecording) {
                mediaRecorder.stop();
                isRecording = false;
            }
        });
        modal.appendChild(closeBtn);

        modal.appendChild(center);
        modal.appendChild(labelWrap);
        root.appendChild(modal);
        document.body.appendChild(root);
        return root;
    }

    // --- 3. UI 상태 변경 (변경 없음) ---
    function showOverlay() {
        const root = ensureOverlay();
        root.classList.add('show');
        clearConvo(); 
        setStatus('버튼을 눌러 대화를 시작하세요');
        initVoicePTT(); 
    }

    function hideOverlay() {
        const root = ensureOverlay();
        root.classList.remove('show');
    }

    function setStatus(text) {
        const statusEl = document.getElementById('va-status');
        if (statusEl) statusEl.textContent = text;
    }

    function setRecordingState(isRec) {
        const dot = document.querySelector('.va-dot');
        if (dot) dot.classList.toggle('recording', isRec);
    }

    function addConvoMessage(text, type = 'user') {
        const convoEl = document.getElementById('va-convo');
        if (!convoEl) return;
        
        const msg = el('div', 'va-convo-msg');
        msg.classList.add(type);
        msg.textContent = text;
        
        convoEl.appendChild(msg);
        convoEl.scrollTop = convoEl.scrollHeight; 
    }

    function clearConvo() {
        const convoEl = document.getElementById('va-convo');
        if (convoEl) convoEl.innerHTML = '';
    }

    // --- 4. PTT 핵심 로직 (변경 없음) ---
    async function initVoicePTT() {
        if (mediaRecorder) return; 

        const dot = document.querySelector('.va-dot');
        if (!dot) return;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            const startRecording = () => {
                if (isRecording) return;
                isRecording = true;
                audioChunks = [];
                mediaRecorder.start();
                clearConvo(); 
                setStatus('듣고 있어요…');
                setRecordingState(true);
            };

            const stopRecording = () => {
                if (!isRecording) return;
                isRecording = false;
                mediaRecorder.stop(); 
                setStatus('처리 중…');
                setRecordingState(false);
            };

            dot.addEventListener('mousedown', startRecording);
            dot.addEventListener('mouseup', stopRecording);
            dot.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
            dot.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                await sendAudioToServer(audioBlob);
            };

        } catch (err) {
            console.error("마이크 접근 오류:", err);
            setStatus("마이크 권한이 필요합니다.");
            dot.classList.add('disabled');
        }
    }

    // 💡💡💡 --- [gTTS Base64 재생 로직으로 복원] --- 💡💡💡
    // --- 5. 오디오 전송 및 응답 처리 ---
    async function sendAudioToServer(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
            const response = await fetch('/api/voice/process_ptt', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('서버 응답 오류');
            
            const data = await response.json();
            
            if (!data.ok) throw new Error(data.error || '서버 처리 오류');

            // 1. 사용자 텍스트 표시
            if (data.display_user_text) {
                addConvoMessage(data.display_user_text, 'user');
            }
            
            // 2. AI 응답 텍스트 표시
            if (data.reply_text) {
                addConvoMessage(data.reply_text, 'ai');
            }
            
            // 3. 💡 [복원] Base64 오디오 디코딩 및 재생
            if (data.audio_base64) {
                const audio = new Audio("data:audio/mpeg;base64," + data.audio_base64);
                audio.play();

                audio.onended = () => {
                    setStatus('버튼을 눌러 대화를 시작하세요');
                };
            } else {
                setStatus('버튼을 눌러 대화를 시작하세요');
            }
            // 💡💡💡 --- [복원 완료] --- 💡💡💡

        } catch (error) {
            console.error("오디오 처리 실패:", error);
            setStatus("오류가 발생했습니다.");
            addConvoMessage("오류: " + error.message, 'ai');
        }
    }

    // --- 6. 전역 노출 ---
    window.VoiceOverlay = {
        show: showOverlay,
        hide: hideOverlay,
    };

    window.addEventListener('DOMContentLoaded', () => {
        ensureOverlay();
    });
})();
