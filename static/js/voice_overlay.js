// voice_overlay.js - 클릭-클릭 토글 음성 인식
(() => {
    let mediaStream = null;
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let isProcessing = false;
    let currentAudio = null; // 현재 재생 중인 오디오 객체

    // === CSS 주입 ===
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

    // === UI 생성 ===
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
        dot.id = 'va-record-btn';
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
            cleanup();
            hideOverlay();
        });
        modal.appendChild(closeBtn);

        modal.appendChild(center);
        modal.appendChild(labelWrap);
        root.appendChild(modal);
        document.body.appendChild(root);
        return root;
    }

    // === UI 상태 변경 ===
    function showOverlay() {
        const root = ensureOverlay();
        root.classList.add('show');
        clearConvo();
        setStatus('버튼을 클릭하여 녹음 시작');
        requestMicrophone();
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
        const dot = document.getElementById('va-record-btn');
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

    // === 마이크 초기화 (노이즈 캔슬레이션 강화) ===
    async function requestMicrophone() {
        if (mediaStream) return; // 이미 초기화됨

        try {
            // 노이즈 제거 및 에코 캔슬레이션 활성화
            mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,        // 에코 제거
                    noiseSuppression: true,        // 노이즈 억제
                    autoGainControl: true,         // 자동 게인 조절 (목소리 크기 자동 조정)
                    sampleRate: 16000,             // 16kHz (Whisper 최적)
                    channelCount: 1                // 모노
                }
            });
            console.log('✓ 마이크 권한 획득 (노이즈 캔슬레이션 활성화)');
            setupRecordButton();
        } catch (err) {
            console.error('✗ 마이크 접근 실패:', err);
            setStatus('마이크 권한이 필요합니다');
            const dot = document.getElementById('va-record-btn');
            if (dot) dot.classList.add('disabled');
        }
    }

    // === 녹음 버튼 이벤트 설정 ===
    function setupRecordButton() {
        const dot = document.getElementById('va-record-btn');
        if (!dot) return;

        // 기존 이벤트 제거 (중복 방지)
        const newDot = dot.cloneNode(true);
        dot.parentNode.replaceChild(newDot, dot);

        // 클릭 이벤트 등록
        newDot.addEventListener('click', handleRecordClick);
    }

    // === 녹음 토글 핸들러 ===
    function handleRecordClick(e) {
        e.preventDefault();
        
        if (isProcessing) {
            console.log('처리 중...');
            return;
        }

        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    }

    // === 녹음 시작 ===
    function startRecording() {
        if (!mediaStream || isRecording) return;

        try {
            // 새 MediaRecorder 생성
            mediaRecorder = new MediaRecorder(mediaStream, {
                mimeType: 'audio/webm'
            });

            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                handleRecordingStop();
            };

            mediaRecorder.onerror = (event) => {
                console.error('✗ MediaRecorder 오류:', event.error);
                resetRecording();
            };

            // 녹음 시작
            mediaRecorder.start();
            isRecording = true;
            
            clearConvo();
            setStatus('🔴 녹음 중... (다시 클릭하면 종료)');
            setRecordingState(true);
            
            console.log('✓ 녹음 시작');

        } catch (err) {
            console.error('✗ 녹음 시작 실패:', err);
            setStatus('녹음 시작 실패');
            resetRecording();
        }
    }

    // === 녹음 중지 ===
    function stopRecording() {
        if (!mediaRecorder || !isRecording) return;

        try {
            mediaRecorder.stop();
            isRecording = false;
            setStatus('⏳ 처리 중...');
            setRecordingState(false);
            console.log('✓ 녹음 중지');
        } catch (err) {
            console.error('✗ 녹음 중지 실패:', err);
            resetRecording();
        }
    }

    // === 녹음 종료 후 처리 ===
    async function handleRecordingStop() {
        if (audioChunks.length === 0) {
            console.warn('녹음된 데이터 없음');
            setStatus('녹음 데이터가 없습니다');
            resetRecording();
            return;
        }

        isProcessing = true;

        try {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            console.log(`✓ 오디오 생성: ${audioBlob.size} bytes`);
            
            await sendAudioToServer(audioBlob);
            
        } catch (err) {
            console.error('✗ 오디오 처리 실패:', err);
            setStatus('오류 발생');
            addConvoMessage('오류: ' + err.message, 'ai');
        } finally {
            resetRecording();
        }
    }

    // === 서버로 전송 ===
    async function sendAudioToServer(audioBlob) {
        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
            setStatus('⏳ 서버 처리 중...');

            const response = await fetch('/api/voice/process_ptt', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`서버 오류: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.ok) {
                throw new Error(data.error || '서버 처리 실패');
            }

            // 사용자 텍스트 표시
            if (data.display_user_text) {
                addConvoMessage(data.display_user_text, 'user');
            }
            
            // AI 응답 텍스트 표시
            if (data.reply_text) {
                addConvoMessage(data.reply_text, 'ai');
            }
            
            // 팝업 표시 (안녕/하이파이브/파이팅)
            if (data.popup_text) {
                // main.js의 showPopup 함수 사용
                if (window.showPopup) {
                    window.showPopup(data.popup_text, false);
                }
            }
            
            // 오디오 재생
            if (data.audio_base64) {
                await playAudioResponse(data.audio_base64);
            } else {
                setStatus('버튼을 클릭하여 녹음 시작');
            }

        } catch (error) {
            console.error('✗ 서버 통신 실패:', error);
            setStatus('오류 발생');
            addConvoMessage('오류: ' + error.message, 'ai');
        }
    }

    // === 오디오 응답 재생 ===
    async function playAudioResponse(base64Audio) {
        return new Promise((resolve) => {
            // 진행 중인 오디오가 있다면 중지
            if (currentAudio) {
                currentAudio.pause();
                currentAudio = null;
            }

            try {
                setStatus('🔊 응답 재생 중...');
                
                currentAudio = new Audio("data:audio/mpeg;base64," + base64Audio);
                
                currentAudio.onended = () => {
                    setStatus('버튼을 클릭하여 녹음 시작');
                    currentAudio = null;
                    resolve();
                };
                
                currentAudio.onerror = (err) => {
                    console.error('✗ 오디오 재생 실패:', err);
                    setStatus('버튼을 클릭하여 녹음 시작');
                    currentAudio = null;
                    resolve();
                };
                
                currentAudio.play().catch(err => {
                    console.error('✗ 재생 시작 실패:', err);
                    setStatus('버튼을 클릭하여 녹음 시작');
                    currentAudio = null;
                    resolve();
                });
                
            } catch (err) {
                console.error('✗ 오디오 생성 실패:', err);
                setStatus('버튼을 클릭하여 녹음 시작');
                currentAudio = null;
                resolve();
            }
        });
    }

    // === 녹음 상태 초기화 ===
    function resetRecording() {
        isRecording = false;
        isProcessing = false;
        audioChunks = [];
        mediaRecorder = null;
        setRecordingState(false);
        console.log('✓ 녹음 상태 초기화');
    }

    // === 완전 정리 ===
    function cleanup() {
        // 1. 진행 중인 녹음 중단
        if (mediaRecorder && isRecording) {
            try {
                // onstop 핸들러가 서버로 전송하지 않도록 이벤트 리스너를 제거
                mediaRecorder.onstop = null;
                mediaRecorder.stop();
                console.log('✓ 진행 중인 녹음 강제 중단');
            } catch (e) {
                console.error('녹음 중단 실패', e);
            }
        }
        
        // 2. 진행 중인 TTS 오디오 재생 중단
        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
            console.log('✓ TTS 오디오 재생 강제 중단');
        }

        // 3. 마이크 스트림 끄기 (리소스 해제)
        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
            console.log('✓ 마이크 스트림 해제');
        }
        
        // 4. 모든 상태 초기화
        resetRecording();
        console.log('✓ 모든 음성 처리 리소스 정리 완료');
    }

    // === 전역 노출 ===
    window.VoiceOverlay = {
        show: showOverlay,
        hide: hideOverlay,
    };

    window.addEventListener('DOMContentLoaded', () => {
        ensureOverlay();
    });

    // 페이지 종료 시 정리
    window.addEventListener('beforeunload', cleanup);
})();
