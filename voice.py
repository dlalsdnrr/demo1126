from __future__ import annotations

import os
import threading
import io
import base64
from typing import Optional, Dict, Any
import time
import difflib
# import subprocess # espeak-ng 사용을 위해 제거

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
    # from pydub.playback import play # 웹 API 환경에서는 play 대신 Base64 인코딩 사용
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
    
# Whisper 모델 로드는 두 번째 코드와 동일하게 유지
WHISPER_MODEL = None

def load_whisper_model():
    """Faster Whisper 모델을 로드하는 함수"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None and WhisperModel is not None:
        try:
            # 두 번째 코드의 설정 ("base" 모델) 유지
            WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=4)
            print("--- INFO: Faster Whisper 'base' model loaded successfully.")
        except Exception as e:
            print(f"--- ERROR: Failed to load Whisper model: {e}")
            pass
    return WHISPER_MODEL

# 💡 [TTS 변경] espeak-ng 대신 edge-tts를 사용하며, 결과를 Base64 WAV/MP3로 반환합니다.
async def speak_edge_tts_to_base64(text: str, voice="ko-KR-SunHiNeural", speed_factor=1.1) -> Optional[str]:
    """edge-tts를 사용하여 텍스트를 음성으로 변환하고 Base64 MP3를 반환합니다."""
    if not USE_EDGE_TTS or not AudioSegment:
        print("--- ERROR: edge-tts or pydub not available.")
        return None
    
    print(f"--- INFO: TTS generation (edge-tts) for: {text[:30]}...")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        
        # 1. 오디오 데이터를 메모리 버퍼에 저장
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        # 2. pydub으로 MP3 로드 및 속도 조절
        audio_io = io.BytesIO(audio_data)
        song = AudioSegment.from_mp3(audio_io)
        
        if speed_factor != 1.0:
            # from pydub.effects import speedup (speedup 함수 사용)
            # 1.1배속으로 빠르게 (세 번째 코드의 설정 적용)
            song = speedup(song, playback_speed=speed_factor)
        
        # 3. 오디오를 메모리에 WAV 또는 MP3로 인코딩 (웹 환경에 맞게 MP3/WAV 선택 가능)
        output_buffer = io.BytesIO()
        # MP3로 인코딩 (Base64 크기를 줄이기 위해)
        song.export(output_buffer, format="mp3") 
        output_buffer.seek(0)
        
        # 4. Base64 인코딩 및 반환
        return base64.b64encode(output_buffer.read()).decode('utf-8')
        
    except Exception as e:
        print(f"--- ERROR: edge-tts failed: {e}")
        return None

# 💡 비동기 함수를 동기로 감싸는 헬퍼 함수 (Flask API는 동기적이므로 필요)
def get_tts_base64(text: str) -> Optional[str]:
    """asyncio.run을 사용하여 비동기 TTS 함수를 실행합니다."""
    # 윈도우 환경에서 asyncio.run을 스레드 내에서 호출할 때의 오류를 방지
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    return loop.run_until_complete(speak_edge_tts_to_base64(text))


class VoiceAssistant:
    def __init__(self) -> None:
        self._whisper_model = load_whisper_model()

        # 두 번째 코드의 키워드 및 데이터 유지
        self._exit_keywords = [
            "종료", "그만", "대화 종료", "끝", "나가기",
            "종료해", "종료요", "이제 그만", "종뇨","종요", "이제됐어"
        ]
        self.KEYWORDS = {
            "타율": ["타율", "타이율", "타유율", "타위", "타이위", "타유", "다율", "타뉼", "타룰", "타유를", "타유리", "타율은", "타율이"],
            "홈런": ["홈런", "홍런", "홈롬", "홍론", "훔는", "홈론", "홈눈", "험론", "호너", "홈너", "홈넌", "홈런은", "홈런이", "홈런개수"],
            "안타": ["안타", "앙타", "안 타", "암타", "안탈", "안탑", "아타", "안타는", "안타가", "아안타", "안타개수"]
        }
        self.PLAYER_ALIASES = {
            "김지찬": ["김지찬", "김지창", "김지차", "김지차니", "김지찬이", "김지청", "김지차는", "김지찬은", "기지찬", "김지찾"],
            "구자욱": ["구자욱", "구자옥", "구자우", "구자오", "구자욱이", "구자오기", "고자욱", "구자욱은", "구자우기", "구자운", "구자구"],
            "류현진": ["류현진", "유현진", "뉴현진", "유현신", "류현신", "유현지", "류현지", "유현지는", "류현지는", "유현지니", "루현진"]
        }
        self.PLAYERS_DATA = {
            "김지찬": { "타율": 0.285, "홈런": 1, "안타": 80 },
            "구자욱": { "타율": 0.315, "홈런": 22, "안타": 155 },
            "류현진": { "타율": 0.150, "홈런": 0, "안타": 5 }
        }

    # --- 유틸리티 함수 (두 번째 코드의 퍼지 매칭 로직 유지) ---
    def _fuzzy_match(self, text: str, candidates: list[str], threshold=0.7) -> bool:
        """퍼지 매칭을 통해 텍스트와 후보 단어를 비교합니다."""
        for word in candidates:
            if word in text:
                return True
        for candidate in candidates:
             if difflib.SequenceMatcher(None, text, candidate).ratio() > threshold:
                return True
        return False

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        # 두 번째 코드의 STT 로직 유지 (base 모델, 공백 유지)
        if self._whisper_model is None:
            return None
        try:
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
        # 두 번째 코드의 NLU 로직 유지 (퍼지 매칭 사용)
        if not text: return None
        for canonical_name, aliases in self.PLAYER_ALIASES.items():
            if self._fuzzy_match(text, aliases):
                return canonical_name
        return None

    def _find_keyword(self, text: str) -> Optional[str]:
        # 두 번째 코드의 NLU 로직 유지 (퍼지 매칭 사용)
        if not text: return None
        for keyword, similar_words in self.KEYWORDS.items():
            if self._fuzzy_match(text, similar_words):
                return keyword
        return None

    def _get_reply(self, text: str, player_name: Optional[str], keyword: Optional[str]) -> str:
        # 두 번째 코드의 응답 생성 로직 유지
        if not text:
            return "잘 못 들었어요. 다시 말씀해 주시겠어요?"
        if any(self._fuzzy_match(text, [exit_kw]) for exit_kw in self._exit_keywords):
            return "네. 대화를 종료합니다."
        if not player_name:
            return "죄송해요, 선수 이름을 말씀해주세요."
        if not keyword:
            return f"{player_name} 선수의 어떤 정보가 궁금하신가요?"
        player_info = self.PLAYERS_DATA.get(player_name)
        value = player_info.get(keyword)
        if value is None:
            return f"죄송해요, {player_name} 선수의 {keyword} 정보가 없습니다."
        
        # 타율은 .3f 포맷 유지
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
                    # 두 번째 코드의 표시 텍스트 형식 유지
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
        # 💡 [TTS 변경] edge-tts로 변경하여 Base64 오디오 생성
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
