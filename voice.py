from __future__ import annotations

import os
import threading
import io
import base64
from typing import Optional, Dict, Any
import time
import difflib
import requests # <-- requests 라이브러리 추가
import tempfile # 💡 [추가됨] Faster Whisper가 파일 경로를 사용하므로 임시 파일 생성을 위해 추가

from flask import Blueprint, jsonify, request

# --- 💡 config 모듈에서 설정 가져오기 ---
import config 

# --- STT 모듈 변경 (ETRI -> Faster Whisper) ---
STT_AVAILABLE = False
WHISPER_MODEL = None # 💡 [수정됨] Faster Whisper 모델을 저장할 전역 변수

try:
    from faster_whisper import WhisperModel # 💡 [수정됨] faster_whisper 임포트
    STT_AVAILABLE = True
    print("--- INFO: Faster Whisper STT module loaded.")
except ImportError:
    print("Warning: 'faster-whisper' module not installed. STT unavailable.")
    print("--- Please run: pip install faster-whisper ---")
    WhisperModel = None # type: ignore
except Exception as e: # pragma: no cover
    print(f"Error during Faster Whisper initialization: {e}")
    WhisperModel = None # type: ignore


# --- TTS (edge-tts + pydub) 통합 (변경 없음) ---
try:
    import edge_tts
    import asyncio
    from pydub import AudioSegment
    from pydub.effects import speedup
    TTS_AVAILABLE = True
    USE_EDGE_TTS = True
    print("--- INFO: edge-tts module loaded.")
except Exception: # pragma: no cover
    edge_tts = None
    AudioSegment = None
    speedup = None
    TTS_AVAILABLE = False
    USE_EDGE_TTS = False
    print("Warning: edge-tts, pydub or FFmpeg not installed. Audio processing/TTS unavailable.")
    

# ===================================================================
# 💡 [수정됨] load_whisper_model 함수 (Faster Whisper 로직으로)
# ===================================================================
def load_whisper_model(model_name: str = "base") -> Optional[Any]:
    """Faster Whisper 모델을 로드하는 함수"""
    global WHISPER_MODEL, STT_AVAILABLE

    if not STT_AVAILABLE:
        print("--- ERROR: Faster Whisper module not imported. Cannot load model.")
        return None
    
    if WHISPER_MODEL is None:
        try:
            print(f"--- INFO: Loading Faster Whisper STT model ('{model_name}')...")
            # 💡 CPU에 최적화된 "base" 모델을 로드합니다 (Code 2의 설정과 동일)
            WHISPER_MODEL = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=4)
            print("--- INFO: Faster Whisper model loaded successfully.")
        except Exception as e:
            print(f"--- ERROR: Failed to load Faster Whisper model: {e}")
            STT_AVAILABLE = False # 로드 실패 시 STT 비활성화
            WHISPER_MODEL = None
            
    return WHISPER_MODEL
# ===================================================================


# --- TTS 함수 (변경 없음) ---
async def speak_edge_tts_to_base64(text: str, voice="ko-KR-SunHiNeural", speed_factor=1.1) -> Optional[str]:
    if not USE_EDGE_TTS or not AudioSegment:
        print("--- ERROR: edge-tts or pydub not available.")
        return None
    print(f"--- INFO: TTS generation (edge-tts) for: {text[:30]}...")
    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        audio_io = io.BytesIO(audio_data)
        song = AudioSegment.from_mp3(audio_io)
        if speed_factor != 1.0:
            song = speedup(song, playback_speed=speed_factor)
        output_buffer = io.BytesIO()
        song.export(output_buffer, format="mp3", bitrate="64k") # 💡 저용량 MP3로 변경
        output_buffer.seek(0)
        return base64.b64encode(output_buffer.read()).decode('utf-8')
    except Exception as e:
        print(f"--- ERROR: edge-tts failed: {e}")
        return None

def get_tts_base64(text: str) -> Optional[str]:
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(speak_edge_tts_to_base64(text))


class VoiceAssistant:
    def __init__(self) -> None:
        # 💡 [수정됨] Faster Whisper 모델을 로드합니다.
        self._whisper_model = load_whisper_model("base")
        self._exit_keywords = []
        
        # --- 키워드 및 선수 데이터 (변경 없음) ---
        self.KEYWORDS = {
            "타율": ["타율", "타이율", "타유율", "타위", "타이위", "타유", "다율", "타뉼", "타룰", "타유를", "타유리", "타율은", "타율이", 
                   "다요래", "타이유", "타요를", "타요율", "다육", "다이율", "다이유", "다유"],
            "홈런": ["홈런", "홍런", "홈롬", "홍론", "훔는", "홈론", "홈눈", "험론", "호너", "홈너", "홈넌", "홈런은", "홈런이", "홈런개수",
                   "홍남", "홈남", "홍럼", "홈넘", "흠런", "음란", "엄남"],
            "안타": ["안타", "앙타", "안 타", "암타", "안탈", "안탑", "아타", "안타는", "안타가", "아안타", "안타개수",
                   "안나", "안타로", "안다", "안달", "았다"]
        }
        self.PLAYER_ALIASES = {
            "김영웅": ["김영웅", "기명웅", "김형웅", "삼성 김영웅", "김영웅이", "기영웅", "김영", "영웅", "영웅이", "김여웅"],
            "문현빈": ["문현빈", "문현빈이", "문현빈은", "한화 문현빈", "무년빈", "문현민", "무현빈", "현빈", "현빈이", "문현"],
            "노시환": ["노시환", "노시환이", "노시환은", "한화 노시환", "노시완", "노시한", "요시환", "시환", "시환이", "롯시환"],
            "리베라토": ["리베라토", "이베라토", "리베라", "이베라", "한화 리베라토", "리베라도", "이베라도", "니베라토", "니베라도"],
            "김태훈": ["김태훈", "김태운", "김태희", "삼성 김태훈", "김대훈", "김태후", "태훈", "태훈이", "김태"],
            "최재훈": ["최재훈", "체재훈", "췌재훈", "한화 최재훈", "최제훈", "채재훈", "재훈", "재훈이", "최재"],
            "채은성": ["채은성", "채은성이", "한화 채은성", "최은성", "체은성", "은성", "은성이", "채은"],
            "하주석": ["하주석", "아주석", "화주석", "한화 하주석", "하주서", "하주", "주석", "주석이", "아주석"],
            "구자욱": ["구자욱", "구자욱이", "삼성 구자욱", "자욱이", "구자우", "구자옥", "자욱", "고자욱", "구자"],
            "이재현": ["이재현", "이재현이", "삼성 이재현", "이재형", "이재연", "재현", "재현이", "이제현"],
            "디아즈": ["디아즈", "디아스", "삼성 디아즈", "디아즈는", "디아스", "디아지", "디아", "디아즈가"],
            "손아섭": ["손아섭", "손아섭이", "한화 손아섭", "소나섭", "손아", "아섭", "아섭이", "손아선"],
            "김성윤": ["김성윤", "김성윤이", "삼성 김성윤", "김성용", "김성유", "성윤", "성윤이", "김성"],
            "김지찬": ["김지찬", "김지찬이", "삼성 김지찬", "김희찬", "김기찬", "김주찬", "지찬", "지찬이", "김지"],
            "강민호": ["강민호", "강민호는", "삼성 강민호", "강미노", "강민", "민호", "민호가"],
            "심우준": ["심우준", "심우준이", "한화 심우준", "신우준", "시무준", "우준", "우준이", "시무"]
        }
        self.PLAYERS_DATA = {
            "김영웅": { "타율": 0.625, "홈런": 3, "안타": 10 },
            "문현빈": { "타율": 0.444, "홈런": 2, "안타": 8 },
            "노시환": { "타율": 0.429, "홈런": 2, "안타": 9 },
            "리베라토": { "타율": 0.389, "홈런": 1, "안타": 7 },
            "김태훈": { "타율": 0.353, "홈런": 2, "안타": 6 },
            "최재훈": { "타율": 0.353, "홈런": 0, "안타": 6 },
            "채은성": { "타율": 0.350, "홈런": 0, "안타": 7 },
            "하주석": { "타율": 0.350, "홈런": 0, "안타": 7 },
            "구자욱": { "타율": 0.313, "홈런": 0, "안타": 5 },
            "이재현": { "타율": 0.294, "홈런": 1, "안타": 5 },
            "디아즈": { "타율": 0.278, "홈런": 0, "안타": 5 },
            "손아섭": { "타율": 0.263, "홈런": 0, "안타": 5 },
            "김성윤": { "타율": 0.261, "홈런": 0, "안타": 6 },
            "김지찬": { "타율": 0.190, "홈런": 0, "안타": 4 },
            "강민호": { "타율": 0.188, "홈런": 1, "안타": 3 },
            "심우준": { "타율": 0.077, "홈런": 0, "안타": 1 }
        }

    # --- 유틸리티 함수 (변경 없음) ---
    def _fuzzy_match(self, text: str, candidates: list[str], threshold=0.65) -> bool:
        for word in candidates:
            if word in text:
                return True
        for candidate in candidates:
            if difflib.SequenceMatcher(None, text, candidate).ratio() > threshold:
                return True
        return False

    # ===================================================================
    # 💡 [STT 함수 교체] _transcribe_faster_whisper
    # ===================================================================
    def _transcribe_faster_whisper(self, wav_audio_bytes: bytes) -> Optional[str]:
        """Faster Whisper를 사용하여 오디오 바이트를 텍스트로 변환합니다."""
        if not STT_AVAILABLE or not self._whisper_model:
            print("--- ERROR: Faster Whisper STT not available or model not loaded.")
            return None
            
        print("--- INFO: Transcribing audio with Faster Whisper...")
        
        temp_file_path = None
        try:
            # 1. 임시 파일 생성 (WAV 바이트 사용)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
                temp_file.write(wav_audio_bytes)
                temp_file_path = temp_file.name
            
            # 2. Faster Whisper로 파일 변환 (Code 2의 VAD 옵션 사용)
            segments, _ = self._whisper_model.transcribe(
                temp_file_path,
                language="ko", # 한국어
                beam_size=5,
                vad_filter=True, # 음성 구간 감지(VAD) 활성화
                vad_parameters={"min_silence_duration_ms": 500} # 0.5초 묵음
            )
            
            # 3. 인식된 텍스트 조립
            text = " ".join(segment.text.strip() for segment in segments).lower()
            return text if text else None

        except Exception as e:
            print(f"--- ERROR: Faster Whisper transcription failed: {e}")
            print("--- INFO: This might be due to 'ffmpeg' not being installed on your system.")
            return None
        finally:
            # 4. 임시 파일 삭제
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception: # pragma: no cover
                    pass # 임시 파일 삭제 실패 시에도 프로그램은 계속되어야 함
            
    def _transcribe(self, audio: Any) -> Optional[str]:
        """STT 엔진 변경으로 사용되지 않음."""
        print("--- WARNING: _transcribe function called, but Faster Whisper is active.")
        return None
    # ===================================================================

    # --- _find_player, _find_keyword, _get_reply (변경 없음) ---
    def _find_player(self, text: str) -> Optional[str]:
        if not text: return None
        for canonical_name, aliases in self.PLAYER_ALIASES.items():
            if self._fuzzy_match(text, aliases):
                return canonical_name
        return None

    def _find_keyword(self, text: str) -> Optional[str]:
        if not text: return None
        if "다요래" in text: 
            return "타율"
        for keyword, similar_words in self.KEYWORDS.items():
            if self._fuzzy_match(text, similar_words):
                return keyword
        return None

    def _get_reply(self, text: str, player_name: Optional[str], keyword: Optional[str]) -> str:
        # 💡 [수정됨] STT 실패 시(None) 응답
        if not text:
            return "음성 인식이 잘 되지 않았어요. 다시 말씀해 주시겠어요?"
        if not player_name:
            # 💡 [개선] STT 결과를 그대로 보여주기
            return f"죄송해요, 선수 이름을 찾지 못했어요. (인식된 내용: {text})"
        if not keyword:
            return f"{player_name} 선수의 어떤 정보가 궁금하신가요?"
            
        player_info = self.PLAYERS_DATA.get(player_name)
        if player_info is None:
            return f"죄송해요, {player_name} 선수의 기록 정보가 없습니다."
        value = player_info.get(keyword)
        if value is None:
            return f"죄송해요, {player_name} 선수의 {keyword} 정보가 없습니다."
        if keyword == "타율":
            return f"{player_name} 선수의 타율은 {value:.3f}입니다."
        elif keyword == "홈런":
            return f"{player_name} 선수의 홈런은 {value}개입니다."
        elif keyword == "안타":
            return f"{player_name} 선수의 안타는 {value}개입니다."
        else:
            return f"{player_name} 선수의 {keyword}은(는) {value}입니다."
            
    # ===================================================================
    # 💡 [수정됨] process_ptt_audio 함수 (Faster Whisper 로직으로)
    # ===================================================================
    def process_ptt_audio(self, audio_file_storage) -> Dict[str, Any]:
        """PTT 오디오를 처리하고, 텍스트와 Base64 오디오가 포함된 JSON을 반환합니다."""
        start_time = time.time()

        user_text = None
        reply_text = None
        player_name = None
        keyword = None
        display_user_text = "..."
        audio_base64 = None
                
        # 💡 [수정됨] STT_AVAILABLE (Faster Whisper) 기준으로 변경
        if not STT_AVAILABLE or not AudioSegment or not TTS_AVAILABLE:
            reply_text = "음성 처리 모듈(Faster Whisper/Pydub/Edge-TTS)이 준비되지 않았습니다."
            if not STT_AVAILABLE:
                reply_text += " (Whisper 모델 로드에 실패했을 수 있습니다. 서버 로그를 확인하세요.)"
        else:
            try:
                # --- 1. 오디오 로드 및 STT용 WAV 데이터로 변환 (pydub) ---
                load_start = time.time()
                audio_segment = AudioSegment.from_file(audio_file_storage)
                
                # 16kHz, Mono, 16-bit (Whisper 권장 스펙)
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                
                # 'wav' 포맷의 바이트로 추출
                wav_audio_io = io.BytesIO()
                audio_segment.export(wav_audio_io, format="wav")
                audio_data_for_stt = wav_audio_io.getvalue()
                
                print(f"--- TIME: Audio Load/Convert for STT (WAV): {time.time() - load_start:.3f}s")
                
                # --- 2. STT (음성 -> 텍스트) - Faster Whisper 사용 ---
                stt_start = time.time()
                # 💡 [수정됨] _transcribe_etri -> _transcribe_faster_whisper 호출
                user_text = self._transcribe_faster_whisper(audio_data_for_stt) 
                print(f"--- TIME: STT Transcription (Faster Whisper): {time.time() - stt_start:.3f}s")
                print(f"--- INFO: STT Text: {user_text}")

                # --- 3. NLU (텍스트 -> 의도) ---
                nlu_start = time.time()
                if user_text:
                    player_name = self._find_player(user_text)
                    keyword = self._find_keyword(user_text)
                print(f"--- TIME: NLU Processing: {time.time() - nlu_start:.3f}s")

                # --- 4. 텍스트 보정 ---
                if player_name and keyword:
                    display_user_text = f"{player_name} 선수 {keyword} 알려줘"
                elif user_text:
                    display_user_text = user_text
                else:
                    # 💡 STT가 실패(None)했거나 빈 텍스트일 때
                    display_user_text = "음성 인식 실패"
                
                # --- 5. 응답 생성 ---
                reply_text = self._get_reply(user_text, player_name, keyword)
                
            except Exception as e:
                print(f"--- ERROR: Failed to process PTT audio: {e}")
                reply_text = "오디오 처리 중 오류가 발생했습니다."

        # --- 6. TTS (AI 텍스트 -> AI 음성) 및 Base64 인코딩 ---
        tts_start = time.time()
        if TTS_AVAILABLE and reply_text:
            audio_base64 = get_tts_base64(reply_text) # <-- 실시간 생성
        else:
            audio_base64 = None
            if not TTS_AVAILABLE:
                print("--- WARNING: TTS is not available, skipping audio generation.")
        
        print(f"--- TIME: TTS Generation: {time.time() - tts_start:.3f}s")
        
        total_time = time.time() - start_time
        print(f"--- TIME: Total process time: {total_time:.3f}s")
                
        # --- 7. 최종 JSON 반환 ---
        return {
            "ok": True,
            "display_user_text": display_user_text,
            "reply_text": reply_text,
            "audio_base64": audio_base64
        }
    # ===================================================================


# --- 싱글톤 및 Blueprint (변경 없음) ---
_singleton: Optional[VoiceAssistant] = None

def get_assistant() -> VoiceAssistant:
    """VoiceAssistant 싱글톤 객체를 반환합니다."""
    global _singleton
    if _singleton is None:
        _singleton = VoiceAssistant()
    return _singleton


voice_bp = Blueprint("voice", __name__)


@voice_bp.route("/api/voice/process_ptt", methods=["POST"])
def api_voice_process_ptt():
    """PTT 오디오 파일을 받아 처리하고 JSON 응답을 반환하는 API"""
    va = get_assistant()
    
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({"ok": False, "error": "No audio file provided"}), 400

    response_data = va.process_ptt_audio(audio_file)

    if not response_data.get("ok"):
        return jsonify({"ok": False, "error": "Failed to process audio"}), 500

    return jsonify(response_data)
