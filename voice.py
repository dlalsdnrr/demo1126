from __future__ import annotations

import os
import threading
import io
import base64
from typing import Optional, Dict, Any
import time
import difflib

from flask import Blueprint, jsonify, request

# --- STT (Faster Whisper) ---
try:
    from faster_whisper import WhisperModel
    import numpy as np
except Exception: # pragma: no cover
    WhisperModel = None
    np = None
    print("Warning: faster-whisper or numpy not installed. Voice input unavailable.")

# --- TTS (edge-tts + pydub) 통합 ---
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
    
# Whisper 모델은 "base" 모델 설정을 유지하여 속도와 정확도의 균형을 맞춥니다.
WHISPER_MODEL = None

def load_whisper_model():
    """Faster Whisper 모델을 로드하는 함수"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None and WhisperModel is not None:
        try:
            WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
            print("--- INFO: Faster Whisper 'base' model loaded successfully.")
        except Exception as e:
            print(f"--- ERROR: Failed to load Whisper model: {e}")
            pass
    return WHISPER_MODEL

async def speak_edge_tts_to_base64(text: str, voice="ko-KR-SunHiNeural", speed_factor=1.1) -> Optional[str]:
    """edge-tts를 사용하여 텍스트를 음성으로 변환하고 Base64 MP3를 반환합니다."""
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
        song.export(output_buffer, format="mp3") 
        output_buffer.seek(0)
        
        return base64.b64encode(output_buffer.read()).decode('utf-8')
        
    except Exception as e:
        print(f"--- ERROR: edge-tts failed: {e}")
        return None

def get_tts_base64(text: str) -> Optional[str]:
    """asyncio.run을 사용하여 비동기 TTS 함수를 실행합니다."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(speak_edge_tts_to_base64(text))


class VoiceAssistant:
    def __init__(self) -> None:
        self._whisper_model = load_whisper_model()

        self._exit_keywords = []
        
        # 💡 [개선] 키워드 유사어를 최대한 많이 추가
        self.KEYWORDS = {
            "타율": ["타율", "타이율", "타유율", "타위", "타이위", "타유", "다율", "타뉼", "타룰", "타유를", "타유리", "타율은", "타율이", 
                     "다요래", "타이유", "타요를", "타요율", "다육", "다이율", "다이유", "다유"],
            "홈런": ["홈런", "홍런", "홈롬", "홍론", "훔는", "홈론", "홈눈", "험론", "호너", "홈너", "홈넌", "홈런은", "홈런이", "홈런개수",
                     "홍남", "홈남", "홍럼", "홈넘", "흠런", "음란", "엄남"],
            "안타": ["안타", "앙타", "안 타", "암타", "안탈", "안탑", "아타", "안타는", "안타가", "아안타", "안타개수",
                     "안나", "안타로", "안다", "안달", "았다"]
        }
        
        # 💡 [개선] 모든 선수 별명에 오인식 가능성이 높은 별명 추가
        self.PLAYER_ALIASES = {
            "김영웅": ["김영웅", "기명웅", "김형웅", "김영", "기명", "김용웅", "김여운", "김영웅이", "김이용", "김이웅", "이명우", "김여름"],
            "리베라토": ["리베라토", "이베라토", "리베라", "이베라", "이베라도", "리베라토는", "리베라토의", "리배라토", "니베라도", "이베라도", "리베라도"],
            "하주석": ["하주석", "아주석", "화주석", "하주소", "하주", "하주석이", "하주석은", "하즈석", "하나 투속", "하나투속", "아나 투속", "아주석"],
            "김태훈": ["김태훈", "김태운", "김태희", "김대훈", "김대운", "김태훈이", "김태훈은", "김대훈이", "김태우", "김태", "김대운"],
            "최재훈": ["최재훈", "체재훈", "췌재훈", "최재", "최재훈이", "최재훈은", "최대훈", "최정은", "채재훈", "체제훈", "최저온"]
        }
        
        self.PLAYERS_DATA = {
            "김영웅": { "타율": 0.643, "홈런": 3, "안타": 9 },
            "리베라토": { "타율": 0.467, "홈런": 1, "안타": 7 },
            "하주석": { "타율": 0.438, "홈런": 0, "안타": 7 },
            "김태훈": { "타율": 0.429, "홈런": 2, "안타": 6 },
            "최재훈": { "타율": 0.385, "홈런": 0, "안타": 5 }
        }

    # --- 유틸리티 함수 ---
    def _fuzzy_match(self, text: str, candidates: list[str], threshold=0.65) -> bool: # 임계값 0.65로 유지
        """퍼지 매칭을 통해 텍스트와 후보 단어를 비교합니다."""
        for word in candidates:
            if word in text:
                return True
        for candidate in candidates:
            if difflib.SequenceMatcher(None, text, candidate).ratio() > threshold:
                return True
        return False

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        if self._whisper_model is None:
            return None
        try:
            # beam_size=5 유지
            segments, _ = self._whisper_model.transcribe(
                audio, language="ko", beam_size=5, best_of=5,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}
            )
            text = " ".join(segment.text.strip() for segment in segments).lower() 
            return text if text else None
        except Exception as e:
            print(f"--- ERROR: Transcription failed: {e}")
            return None

    def _find_player(self, text: str) -> Optional[str]:
        if not text: return None
        for canonical_name, aliases in self.PLAYER_ALIASES.items():
            if self._fuzzy_match(text, aliases):
                return canonical_name
        return None

    def _find_keyword(self, text: str) -> Optional[str]:
        if not text: return None
        
        # 💡 [개선] '다요래'가 발견되면 '타율'로 강제 매핑 (이전 오류 패턴 반영)
        if "다요래" in text:
            return "타율"
            
        for keyword, similar_words in self.KEYWORDS.items():
            if self._fuzzy_match(text, similar_words):
                return keyword
        return None

    def _get_reply(self, text: str, player_name: Optional[str], keyword: Optional[str]) -> str:
        if not text:
            return "잘 못 들었어요. 다시 말씀해 주시겠어요?"
        
        if not player_name:
            return "죄송해요, 선수 이름을 말씀해주세요."
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
            
    def process_ptt_audio(self, audio_file_storage) -> Dict[str, Any]:
        """PTT 오디오를 처리하고, 텍스트와 Base64 오디오가 포함된 JSON을 반환합니다."""
        start_time = time.time()

        user_text = None
        reply_text = None
        player_name = None
        keyword = None
        display_user_text = "..."
        audio_base64 = None
            
        if self._whisper_model is None or not np or not TTS_AVAILABLE:
            reply_text = "음성 처리 모듈(Whisper/Pydub/Edge-TTS)이 준비되지 않았습니다."
        else:
            try:
                # --- 1. 오디오 로드 및 변환 (pydub) ---
                load_start = time.time()
                audio_segment = AudioSegment.from_file(audio_file_storage)
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                samples = np.array(audio_segment.get_array_of_samples())
                audio_float = samples.astype(np.float32) / 32768.0
                audio_to_transcribe = audio_float
                print(f"--- TIME: Audio Load/Convert: {time.time() - load_start:.3f}s")
                
                # --- 2. STT (음성 -> 텍스트) ---
                stt_start = time.time()
                user_text = self._transcribe(audio_to_transcribe)
                print(f"--- TIME: STT Transcription: {time.time() - stt_start:.3f}s")
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
                
                # --- 5. 응답 생성 ---
                reply_text = self._get_reply(user_text, player_name, keyword)
                
            except Exception as e:
                print(f"--- ERROR: Failed to process PTT audio: {e}")
                reply_text = "오디오 처리 중 오류가 발생했습니다."

        # --- 6. TTS (AI 텍스트 -> AI 음성) 및 Base64 인코딩 ---
        tts_start = time.time()
        if TTS_AVAILABLE:
            audio_base64 = get_tts_base64(reply_text)
        else:
            audio_base64 = None
            print("--- WARNING: TTS is not available, skipping audio generation.")
            
        print(f"--- TIME: TTS Generation: {time.time() - tts_start:.3f}s")
        
        total_time = time.time() - start_time
        print(f"--- TIME: Total process time: {total_time:.3f}s")
            
        # --- 7. 최종 JSON 반환 ---
        return {
            "ok": True,
            "display_user_text": display_user_text,
            "reply_text": reply_text,
            "audio_base64": audio_base64 # Base64 오디오 데이터
        }


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
