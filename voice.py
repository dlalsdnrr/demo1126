from __future__ import annotations

import os
import threading
import time
from typing import Optional, Dict, Any

from flask import Blueprint, jsonify, request
from config import (
    GEMINI_API_KEY as DEFAULT_GEMINI_API_KEY,
    VOICE_WAKE_MODEL,
    VOICE_CONV_MODEL,
    VAD_AGGRESSIVENESS,
    SILENCE_THRESHOLD as CONFIG_SILENCE_THRESHOLD,
    SILENCE_DURATION as CONFIG_SILENCE_DURATION
)

# --- STT (Faster Whisper) 및 오디오 입력 (sounddevice) ---
try:
    import sounddevice as sd
    from faster_whisper import WhisperModel
    import numpy as np
except Exception:  # pragma: no cover
    sd = None
    WhisperModel = None
    np = None
    print("Warning: sounddevice or faster-whisper not installed. Voice input unavailable.")

# --- TTS (gTTS + pydub) ---
try:
    from gtts import gTTS
    from pydub import AudioSegment
    from pydub.playback import play
    from pydub.effects import speedup
    TTS_AVAILABLE = True
except Exception: # pragma: no cover
    gTTS = None
    AudioSegment = None
    play = None
    speedup = None
    TTS_AVAILABLE = False
    print("Warning: gTTS or pydub not installed, or FFmpeg is missing. TTS unavailable.")

# --- Gemini API ---
try:
    import google.generativeai as genai  # Gemini API
except Exception:  # pragma: no cover
    genai = None

# --- VAD (Voice Activity Detection) ---
try:
    import webrtcvad
    VAD_AVAILABLE = True
except Exception:  # pragma: no cover
    webrtcvad = None
    VAD_AVAILABLE = False
    print("Warning: webrtcvad not installed. VAD unavailable.")

RESPEAKER_INDEX = 1

# --- 새로운 STT 설정 ---
SAMPLE_RATE = 16000
WHISPER_WAKE_MODEL = None      # tiny 모델 (트리거 감지용)
WHISPER_CONV_MODEL = None      # base 모델 (대화용)

# --- 실시간 VAD 설정 ---
CHUNK_DURATION_MS = 30         # 30ms 청크
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
SILENCE_THRESHOLD = CONFIG_SILENCE_THRESHOLD    # 에너지 임계값 (RMS)
SILENCE_DURATION = CONFIG_SILENCE_DURATION      # 무음 감지 시간 (초)

def load_whisper_models():
    """하이브리드 Whisper 모델을 로드하는 함수"""
    global WHISPER_WAKE_MODEL, WHISPER_CONV_MODEL
    
    if WhisperModel is None:
        return False
    
    try:
        # 1. Wake 모델 (tiny) - 트리거 감지용
        if WHISPER_WAKE_MODEL is None:
            print(f"--- INFO: Loading wake model ({VOICE_WAKE_MODEL})...")
            WHISPER_WAKE_MODEL = WhisperModel(
                VOICE_WAKE_MODEL, 
                device="cpu", 
                compute_type="int8", 
                cpu_threads=2
            )
            print(f"--- INFO: Wake model ({VOICE_WAKE_MODEL}) loaded successfully.")
        
        # 2. Conversation 모델 (base) - 대화용
        if WHISPER_CONV_MODEL is None:
            print(f"--- INFO: Loading conversation model ({VOICE_CONV_MODEL})...")
            WHISPER_CONV_MODEL = WhisperModel(
                VOICE_CONV_MODEL,
                device="cpu",
                compute_type="int8",
                cpu_threads=4
            )
            print(f"--- INFO: Conversation model ({VOICE_CONV_MODEL}) loaded successfully.")
        
        return True
    except Exception as e:
        print(f"--- ERROR: Failed to load Whisper models: {e}")
        return False


class VoiceAssistant:
    def __init__(
        self,
        trigger_phrase: str = "안녕",
        default_model_name: str = "gemini-2.5-flash",
    ) -> None:
        self.trigger_phrase = trigger_phrase
        self.default_model_name = default_model_name

        # "안녕" 관련 키워드 목록
        self.trigger_keywords = ["안녕", "안뇽", "아니요", "안냥", "하이"]
        # "종료" 관련 키워드 목록
        self.exit_keywords = [
            "종료", "그만", "대화 종료", "끝", "나가기",
            "종료해", "종료요", "이제 그만", "종뇨","종요"
        ]

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._active_conversation = False
        self._lock = threading.Lock()

        self._tts_file_path = "tts_output.mp3" # 임시 파일 경로
        self._gtts_lang = "ko" # 한국어
        self._mic = None
        self._gemini_model = None
        self._gemini_api_key: Optional[str] = None
        self._model_name: str = self.default_model_name
        self._last_user_text: Optional[str] = None
        self._last_ai_text: Optional[str] = None
        self._last_error: Optional[str] = None
        self._require_trigger: bool = True
        self._current_mode: str = "wake"  # "wake" or "conversation"
        
        # 모델 로드
        self._models_loaded = load_whisper_models()
        
        # VAD 초기화
        if VAD_AVAILABLE:
            try:
                self._vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
                self._vad_enabled = True
            except:
                self._vad = None
                self._vad_enabled = False
        else:
            self._vad = None
            self._vad_enabled = False


    def start(self, api_key: Optional[str] = None, model_name: Optional[str] = None, require_trigger: Optional[bool] = True) -> None:
        with self._lock:
            # 1. 스레드가 이미 실행 중인 경우 (대기 모드에서 활성화)
            if self._running:
                if not require_trigger:
                    self._active_conversation = True
                    # 0.5초 지연 후 "듣고 있어요" TTS 재생
                    threading.Timer(0.5, self._say, args=["듣고 있어요. 말씀해 주세요."]).start()
                return

            # 2. 스레드가 꺼져있는 경우 (신규 시작)
            if not self._models_loaded:
                print("--- ERROR: STT models are not ready. Cannot start assistant.")
                return

            self._stop_event.clear()
            self._running = True
            self._require_trigger = bool(require_trigger)

            if not self._require_trigger:
                self._active_conversation = True

            if model_name:
                self._model_name = model_name
            self._gemini_api_key = api_key or DEFAULT_GEMINI_API_KEY

            self._thread = threading.Thread(target=self._listen_loop, name="VoiceAssistantThread", daemon=True)
            self._thread.start()

            if not self._require_trigger:
                # 0.5초 지연 후 "듣고 있어요" TTS 재생
                threading.Timer(0.5, self._say, args=["듣고 있어요. 말씀해 주세요."]).start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._lock:
            self._running = False
            self._active_conversation = False

    def go_to_standby(self) -> None:
        """대기 모드로 설정하고, 활성 상태였다면 음성 안내를 재생합니다."""
        with self._lock:
            if self._running: # 스레드가 실행 중일 때만
                # 대화가 활성 상태에서 대기 모드로 전환될 때만 음성 안내를 합니다.
                if self._active_conversation:
                    # TTS 호출이 API 응답을 지연시키지 않도록 별도 스레드에서 실행합니다.
                    threading.Thread(
                        target=self._say,
                        args=["다시 대화하고 싶으시면 안녕이라고 불러주세요."],
                        daemon=True
                    ).start()

                self._active_conversation = False
                self._current_mode = "wake"  # 즉시 wake 모드로 전환
                self._require_trigger = True # "안녕"을 다시 기다리도록 설정
                print("--- INFO: Assistant set to standby mode (waiting for trigger).")

    def is_running(self) -> bool:
        with self._lock:
            return self._running

    def is_active(self) -> bool:
        with self._lock:
            return self._active_conversation

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "active": self._active_conversation,
                "model": self._model_name,
                "trigger": self.trigger_phrase,
                "trigger_keywords": self.trigger_keywords,
                "exit_keywords": self.exit_keywords,
                "last_user_text": self._last_user_text,
                "last_ai_text": self._last_ai_text,
                "last_error": self._last_error,
                "current_mode": self._current_mode,
                "stt_ready": self._models_loaded,
                "tts_ready": TTS_AVAILABLE,
                "gemini_ready": bool(genai is not None),
                "vad_enabled": self._vad_enabled,
            }

    def set_trigger_phrase(self, phrase: str) -> None:
        with self._lock:
            self.trigger_phrase = phrase


    def _ensure_gemini_model(self) -> None:
        if self._gemini_model is not None:
            return
        if genai is None:
            self._last_error = "google-generativeai not installed"
            return
        if not self._gemini_api_key:
            self._last_error = "GEMINI_API_KEY not set"
            return
        try:
            genai.configure(api_key=self._gemini_api_key)
            self._gemini_model = genai.GenerativeModel(self._model_name)
        except Exception as e:  # pragma: no cover
            self._last_error = f"Gemini init failed: {e}"

    def _say(self, text: str) -> None:
        if not text:
            return
        if not TTS_AVAILABLE:
            print("--- ERROR: gTTS/pydub not available. Skipping TTS.")
            return

        print(f"--- INFO: TTS generation for: {text}")

        if os.path.exists(self._tts_file_path):
            try:
                os.remove(self._tts_file_path)
            except Exception:
                pass

        try:
            tts = gTTS(text=text, lang=self._gtts_lang)
            tts.save(self._tts_file_path)
            song = AudioSegment.from_mp3(self._tts_file_path)
            FASTER_FACTOR = 1.2
            if FASTER_FACTOR != 1.0:
                song = speedup(song, playback_speed=FASTER_FACTOR)
            play(song)
            if os.path.exists(self._tts_file_path):
                os.remove(self._tts_file_path)
        except Exception as e:
            self._last_error = f"gTTS/pydub error: {e}"
            print(f"--- ERROR: gTTS/pydub failed (Check FFmpeg/ffplay): {e}")
            if os.path.exists(self._tts_file_path):
                try:
                    os.remove(self._tts_file_path)
                except Exception:
                    pass

    def _calculate_rms(self, audio_chunk: np.ndarray) -> float:
        """오디오 청크의 RMS(Root Mean Square) 에너지 계산"""
        return np.sqrt(np.mean(audio_chunk ** 2)) * 32768.0

    def _record_audio(self) -> Optional[np.ndarray]:
        """현재 모드에 맞는 시간으로 녹음 (Wake 모드 전용)"""
        if sd is None:
            self._last_error = "sounddevice is not installed."
            return None

        # Wake 모드에서만 사용 (2초 고정)
        record_seconds = 2.0

        try:
            device_info = sd.query_devices(RESPEAKER_INDEX, 'input')
            print(f"--- INFO: Recording (wake mode, {record_seconds}s) using device: {device_info['name']}")
            audio = sd.rec(int(record_seconds * SAMPLE_RATE),
                           samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                           device=RESPEAKER_INDEX)
            sd.wait()
            
            audio_float = audio.squeeze().astype(np.float32) / 32768.0
            
            # Wake 모드에서 VAD로 무음 체크
            if self._vad_enabled and self._vad is not None:
                audio_bytes = audio.tobytes()
                chunk_duration_ms = 30  # 30ms 청크
                chunk_size = int(SAMPLE_RATE * chunk_duration_ms / 1000) * 2  # 2 bytes per sample
                
                has_speech = False
                for i in range(0, len(audio_bytes) - chunk_size, chunk_size):
                    chunk = audio_bytes[i:i + chunk_size]
                    try:
                        if self._vad.is_speech(chunk, SAMPLE_RATE):
                            has_speech = True
                            break
                    except:
                        pass  # VAD 오류 무시
                
                if not has_speech:
                    # 무음이면 None 반환 (처리 생략)
                    return None
            
            return audio_float
        except Exception as e:
            self._last_error = f"Audio record failed: {e}"
            print(f"--- ERROR: Audio record failed: {e}")
            return None

    def _record_streaming_with_vad(self) -> Optional[np.ndarray]:
        """실시간 스트리밍 방식으로 음성 구간만 녹음 (Conversation 모드 전용)"""
        if sd is None or np is None:
            self._last_error = "sounddevice is not installed."
            return None

        try:
            print("--- INFO: Streaming mode - Waiting for speech...")
            
            audio_buffer = []
            is_speaking = False
            silence_chunks = 0
            max_silence_chunks = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)  # 1초 = ~33 청크
            
            # 스트림 시작
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='int16',
                device=RESPEAKER_INDEX,
                blocksize=CHUNK_SIZE
            ) as stream:
                while True:
                    # 대기 모드로 전환되었는지 체크 (X 버튼 눌림)
                    if not self.is_active():
                        print("--- INFO: Streaming interrupted - switched to standby")
                        return None
                    
                    # 청크 읽기
                    chunk, overflowed = stream.read(CHUNK_SIZE)
                    if overflowed:
                        print("--- WARNING: Audio buffer overflow")
                    
                    chunk_float = chunk.squeeze().astype(np.float32) / 32768.0
                    rms = self._calculate_rms(chunk_float)
                    
                    # 음성 감지
                    if rms > SILENCE_THRESHOLD:
                        if not is_speaking:
                            print(f"--- INFO: Speech detected (RMS: {rms:.0f})")
                            is_speaking = True
                        
                        audio_buffer.append(chunk_float)
                        silence_chunks = 0
                    else:
                        # 무음 구간
                        if is_speaking:
                            audio_buffer.append(chunk_float)
                            silence_chunks += 1
                            
                            # 1초 이상 무음이면 종료
                            if silence_chunks >= max_silence_chunks:
                                print(f"--- INFO: Silence detected for {SILENCE_DURATION}s, ending speech")
                                break
                        else:
                            # 아직 말을 시작하지 않음 - 최대 10초 대기
                            if len(audio_buffer) > (10 * SAMPLE_RATE / CHUNK_SIZE):
                                print("--- INFO: No speech detected in 10s, timeout")
                                return None
                            audio_buffer.append(chunk_float)
            
            # 버퍼가 비어있으면 None
            if not audio_buffer or not is_speaking:
                return None
            
            # 버퍼를 단일 배열로 결합
            result = np.concatenate(audio_buffer)
            duration = len(result) / SAMPLE_RATE
            print(f"--- INFO: Captured {duration:.2f}s of speech")
            
            return result
            
        except Exception as e:
            self._last_error = f"Streaming audio record failed: {e}"
            print(f"--- ERROR: Streaming audio record failed: {e}")
            return None

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """현재 모드에 맞는 모델로 transcribe"""
        # 모드에 따라 모델 선택
        if self._current_mode == "wake":
            model = WHISPER_WAKE_MODEL
            beam_size = 3
            best_of = 3
        else:
            model = WHISPER_CONV_MODEL
            beam_size = 5
            best_of = 5
        
        if model is None:
            return None

        try:
            segments, _ = model.transcribe(
                audio,
                language="ko",
                beam_size=beam_size,
                best_of=best_of,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500 if self._current_mode == "wake" else 300}
            )
            text = " ".join(segment.text.strip() for segment in segments).lower()
            return text if text else None
        except Exception as e:
            print(f"--- ERROR: Transcription failed: {e}")
            return None

    def _listen_once(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> Optional[str]:
        """현재 모드에 맞는 방식으로 녹음 및 transcribe"""
        # Conversation 모드: 스트리밍 방식
        if self._current_mode == "conversation":
            audio = self._record_streaming_with_vad()
        # Wake 모드: 고정 2초 방식
        else:
            audio = self._record_audio()
        
        if audio is None:
            return None
        return self._transcribe(audio)

    def _listen_loop(self) -> None:
        """하이브리드 모델을 사용한 메인 루프"""
        self._ensure_gemini_model()

        while not self._stop_event.is_set():
            if not self._models_loaded or sd is None:
                time.sleep(1.0)
                continue

            utterance: Optional[str] = None

            # 활성 상태가 아니면 wake 모드
            if not self.is_active():
                self._current_mode = "wake"  # tiny 모델 사용
                
                if self._require_trigger:
                    print("--- INFO: Wake mode - Listening for trigger (tiny model)...")
                    utterance = self._listen_once()

                    if not utterance:
                        time.sleep(0.3)  # 짧은 대기
                        continue

                    print(f"--- INFO: Transcribed Text (wake): {utterance}")
                    normalized = utterance.replace(" ", "")

                    if any(kw in normalized for kw in self.trigger_keywords):
                        with self._lock:
                            self._active_conversation = True
                            self._current_mode = "conversation"  # base 모델로 전환
                            self._last_user_text = utterance

                        if self._gemini_model is None:
                            self._say("Gemini 설정에 문제가 있습니다. API 키를 확인해주세요.")
                            with self._lock:
                                self._active_conversation = False
                                self._current_mode = "wake"
                            continue

                        print("--- INFO: Switched to conversation mode (base model)")
                        threading.Timer(0.5, self._say, args=["네, 반가워요. 말씀해주세요."]).start()
                        continue
                    else:
                        time.sleep(0.3)
                        continue
                else:  # 트리거 불필요 모드
                    with self._lock:
                        self._active_conversation = True
                        self._current_mode = "conversation"
                    continue
            
            # --- 대화 활성 모드 (base 모델) ---
            # 여기 도달했다는 것은 is_active() == True
            if self._current_mode != "conversation":
                self._current_mode = "conversation"
                
            print("--- INFO: Conversation mode - Listening (base model)...")
            utterance = self._listen_once()

            if not utterance:
                time.sleep(0.3)
                continue

            print(f"--- INFO: Transcribed Text (conversation): {utterance}")

            # '종료' 명령어 (대기 모드로 전환)
            if any(exit_kw in utterance for exit_kw in self.exit_keywords):
                self.go_to_standby()
                self._current_mode = "wake"  # 다시 tiny 모드로
                print("--- INFO: Switched back to wake mode (tiny model)")
                continue

            # Gemini API 호출
            with self._lock:
                self._last_user_text = utterance

            reply_text: Optional[str] = None
            try:
                # 간결한 답변을 위한 프롬프트 구성
                prompt = f"다음 대화에 대한 대답을 간결하게 대답해주세요.\n\n{utterance}"
                resp = self._gemini_model.generate_content(prompt)
                reply_text = getattr(resp, "text", None) or (resp.candidates[0].content.parts[0].text if getattr(resp, "candidates", None) else None)
            except Exception as e:  # pragma: no cover
                self._last_error = f"Gemini error: {e}"

            if not reply_text:
                reply_text = "죄송해요, 방금은 잘 알아듣지 못했어요. 다시 말씀해 주세요."

            with self._lock:
                self._last_ai_text = reply_text

            self._say(reply_text)


_singleton: Optional[VoiceAssistant] = None


def get_assistant() -> VoiceAssistant:
    global _singleton
    if _singleton is None:
        _singleton = VoiceAssistant()
    return _singleton


voice_bp = Blueprint("voice", __name__)


@voice_bp.route("/api/voice/status")
def api_voice_status():
    va = get_assistant()
    return jsonify({"ok": True, "status": va.status()})


@voice_bp.route("/api/voice/start", methods=["POST"])
def api_voice_start():
    va = get_assistant()
    data = request.get_json(silent=True) or {}
    api_key = data.get("apiKey")
    model = data.get("model")
    require_trigger = data.get("requireTrigger", True) # None이 넘어오면 True
    va.start(api_key=api_key, model_name=model, require_trigger=require_trigger)
    return jsonify({"ok": True, "status": va.status()})


@voice_bp.route("/api/voice/stop", methods=["POST"])
def api_voice_stop():
    va = get_assistant()
    va.stop()
    return jsonify({"ok": True, "status": va.status()})


@voice_bp.route("/api/voice/standby", methods=["POST"])
def api_voice_standby():
    """ 'X' 버튼 클릭 시 호출될 '대기 모드' API """
    va = get_assistant()
    va.go_to_standby() # go_to_standby 메소드 호출
    return jsonify({"ok": True, "status": va.status()})
