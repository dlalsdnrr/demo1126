from __future__ import annotations

import os
import threading
import time
from typing import Optional, Dict, Any

from flask import Blueprint, jsonify, request

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

RESPEAKER_INDEX = 1

# --- 새로운 STT 설정 ---
SAMPLE_RATE = 16000
RECORD_SECONDS = 4.0 # 인식 시간을 4초로 설정
WHISPER_MODEL = None # 모델은 처음 로드 시에 초기화됩니다.

def load_whisper_model():
    """Faster Whisper 모델을 로드하는 함수"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None and WhisperModel is not None:
        try:
            # 모델을 'base'로 유지 (성능 우선)
            WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
            print("--- INFO: Faster Whisper model loaded successfully.")
        except Exception as e:
            print(f"--- ERROR: Failed to load Whisper model: {e}")
            pass
    return WHISPER_MODEL


class VoiceAssistant:
    def __init__(
        self,
        trigger_phrase: str = "안녕",
        default_model_name: str = "gemini-1.5-flash",
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
        self._whisper_model = load_whisper_model()


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
            if not self._whisper_model:
                print("--- ERROR: STT is not ready. Cannot start assistant.")
                return

            self._stop_event.clear()
            self._running = True
            self._require_trigger = bool(require_trigger)

            if not self._require_trigger:
                self._active_conversation = True

            if model_name:
                self._model_name = model_name
            self._gemini_api_key = api_key or os.getenv("GEMINI_API_KEY")

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
                "stt_ready": bool(self._whisper_model is not None),
                "tts_ready": TTS_AVAILABLE,
                "gemini_ready": bool(genai is not None),
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

    def _record_audio(self) -> Optional[np.ndarray]:
        if sd is None:
            self._last_error = "sounddevice is not installed."
            return None

        try:
            device_info = sd.query_devices(RESPEAKER_INDEX, 'input')
            print(f"--- INFO: Recording using device: {device_info['name']}")
            audio = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE),
                           samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                           device=RESPEAKER_INDEX)
            sd.wait()
            return audio.squeeze().astype(np.float32) / 32768.0
        except Exception as e:
            self._last_error = f"Audio record failed: {e}"
            print(f"--- ERROR: Audio record failed: {e}")
            return None

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        if self._whisper_model is None:
            return None

        try:
            segments, _ = self._whisper_model.transcribe(
                audio,
                language="ko",
                beam_size=5, best_of=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500}
            )
            text = " ".join(segment.text.strip() for segment in segments).lower()
            return text if text else None
        except Exception as e:
            print(f"--- ERROR: Transcription failed: {e}")
            return None

    def _listen_once(self, timeout: Optional[float] = None, phrase_time_limit: Optional[float] = None) -> Optional[str]:
        audio = self._record_audio()
        if audio is None:
            return None
        return self._transcribe(audio)

    def _listen_loop(self) -> None:
        self._ensure_gemini_model()

        while not self._stop_event.is_set():
            if self._whisper_model is None or sd is None:
                time.sleep(1.0)
                continue

            utterance: Optional[str] = None

            print("--- INFO: Listening...")
            utterance = self._listen_once()

            if utterance:
                print(f"--- INFO: Transcribed Text: {utterance}")

            if not self.is_active():
                if self._require_trigger:
                    if not utterance:
                        time.sleep(0.5)
                        continue

                    normalized = utterance.replace(" ", "")

                    if any(kw in normalized for kw in self.trigger_keywords):
                        with self._lock:
                            self._active_conversation = True
                            self._last_user_text = utterance

                        if self._gemini_model is None:
                            self._say("Gemini 설정에 문제가 있습니다. API 키를 확인해주세요.")
                            with self._lock:
                                self._active_conversation = False
                            continue

                        threading.Timer(0.5, self._say, args=["네, 반가워요. 말씀해주세요."]).start()

                        continue
                    else:
                        time.sleep(0.5)
                        continue
                else: # 트리거 불필요 모드
                    with self._lock:
                        self._active_conversation = True
                    continue

            # --- 대화 활성 모드 ---
            if not utterance:
                time.sleep(0.5)
                continue

            # '종료' 명령어 (대기 모드로 전환)
            if any(exit_kw in utterance for exit_kw in self.exit_keywords):
                # TTS 호출을 go_to_standby 메소드로 이전하여 일관성을 유지합니다.
                self.go_to_standby()
                continue # 루프 계속 (대기)

            # Gemini API 호출
            with self._lock:
                self._last_user_text = utterance

            reply_text: Optional[str] = None
            try:
                resp = self._gemini_model.generate_content(utterance)
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
