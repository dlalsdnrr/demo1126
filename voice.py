from __future__ import annotations

import os
import threading
import io 
import base64 # 💡 [복원] Base64 임포트
from typing import Optional, Dict, Any

from flask import Blueprint, jsonify, request 

# --- STT (Faster Whisper) ---
try:
    from faster_whisper import WhisperModel
    import numpy as np 
except Exception: # pragma: no cover
    WhisperModel = None
    np = None
    print("Warning: faster-whisper or numpy not installed. Voice input unavailable.")

# 💡 [복원] gTTS 및 Pydub 임포트
try:
    from gtts import gTTS
    from pydub import AudioSegment
    from pydub.effects import speedup
    TTS_AVAILABLE = True
except Exception: # pragma: no cover
    gTTS = None
    AudioSegment = None
    speedup = None
    TTS_AVAILABLE = False
    print("Warning: gTTS or pydub not installed, or FFmpeg is missing. TTS unavailable.")

try:
    import librosa
except Exception: # pragma: no cover
    librosa = None
    print("Warning: librosa not installed. VAD (Trimming) will be disabled.")


WHISPER_MODEL = None 

def load_whisper_model():
    """Faster Whisper 모델을 로드하는 함수"""
    global WHISPER_MODEL
    if WHISPER_MODEL is None and WhisperModel is not None:
        try:
            # 💡💡💡 --- [속도 최적화 1] --- 💡💡💡
            # "base" -> "tiny"로 변경하여 STT 속도를 높입니다.
            WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4)
            print("--- INFO: Faster Whisper 'tiny' model loaded successfully.")
            # 💡💡💡 --- [최적화 완료] --- 💡💡💡
        except Exception as e:
            print(f"--- ERROR: Failed to load Whisper model: {e}")
            pass
    return WHISPER_MODEL


class VoiceAssistant:
    def __init__(self) -> None:
        self._gtts_lang = "ko"
        self._whisper_model = load_whisper_model()

        # (키워드 목록은 변경 없이 그대로 유지)
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

    # 💡💡💡 --- [gTTS 함수 복원] --- 💡💡💡
    def _say(self, text: str) -> Optional[io.BytesIO]:
        """텍스트를 gTTS MP3 오디오 버퍼로 변환합니다."""
        if not text or not TTS_AVAILABLE:
            return None
        print(f"--- INFO: TTS generation for: {text}")
        try:
            tts_buffer = io.BytesIO()
            gTTS(text=text, lang=self._gtts_lang).write_to_fp(tts_buffer)
            tts_buffer.seek(0)
            song = AudioSegment.from_mp3(tts_buffer)
            song = speedup(song, playback_speed=1.2)
            final_buffer = io.BytesIO()
            song.export(final_buffer, format="mp3")
            final_buffer.seek(0)
            return final_buffer
        except Exception as e:
            print(f"--- ERROR: gTTS/pydub failed: {e}")
            return None
    # 💡💡💡 --- [복원 완료] --- 💡💡💡

    def _transcribe(self, audio: np.ndarray) -> Optional[str]:
        """오디오를 텍스트로 변환하고 공백을 제거합니다."""
        if self._whisper_model is None:
            return None
        try:
            segments, _ = self._whisper_model.transcribe(
                audio, language="ko", beam_size=5, best_of=5,
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}
            )
            text = " ".join(segment.text.strip() for segment in segments).replace(" ", "")
            return text if text else None
        except Exception as e:
            print(f"--- ERROR: Transcription failed: {e}")
            return None

    def _find_player(self, text: str) -> Optional[str]:
        if not text: return None
        for canonical_name, aliases in self.PLAYER_ALIASES.items():
            for alias in aliases:
                if alias in text:
                    return canonical_name 
        return None

    def _find_keyword(self, text: str) -> Optional[str]:
        if not text: return None
        for keyword, similar_words in self.KEYWORDS.items():
            for word in similar_words:
                if word in text:
                    return keyword
        return None

    def _get_reply(self, text: str, player_name: Optional[str], keyword: Optional[str]) -> str:
        if not text:
            return "잘 못 들었어요. 다시 말씀해 주시겠어요?"
        if any(exit_kw in text for exit_kw in self._exit_keywords):
            return "네. 대화를 종료합니다."
        if not player_name:
            return "죄송해요, 선수 이름을 말씀해주세요."
        if not keyword:
            return f"{player_name} 선수의 어떤 정보가 궁금하신가요?"
        player_info = self.PLAYERS_DATA.get(player_name)
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
        """
        PTT 오디오를 처리하고, 텍스트와 Base64 오디오가 포함된 JSON을 반환합니다.
        """
        user_text = None
        reply_text = None
        player_name = None
        keyword = None
        display_user_text = "..." 
        
        if not self._whisper_model or not TTS_AVAILABLE or not np:
            reply_text = "음성 처리 모듈(Whisper/Pydub)이 준비되지 않았습니다."
        else:
            try:
                # --- 1. 오디오 로드 및 변환 (pydub) ---
                audio_segment = AudioSegment.from_file(audio_file_storage)
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                samples = np.array(audio_segment.get_array_of_samples())
                audio_float = samples.astype(np.float32) / 32768.0

                # 💡💡💡 --- [속도 최적화 2] --- 💡💡💡
                # Librosa 묵음 제거를 비활성화합니다. (주석 처리)
                audio_to_transcribe = audio_float
                # if librosa:
                #     audio_float_trimmed, _ = librosa.effects.trim(audio_float, top_db=20)
                #     if len(audio_float_trimmed) > 1600: 
                #         audio_to_transcribe = audio_float_trimmed
                # 💡💡💡 --- [최적화 완료] --- 💡💡💡
                
                # --- 2. STT (음성 -> 텍스트) ---
                user_text = self._transcribe(audio_to_transcribe) 
                print(f"--- INFO: STT Raw Text: {user_text}")

                # --- 3. NLU (텍스트 -> 의도) ---
                if user_text:
                    player_name = self._find_player(user_text)
                    keyword = self._find_keyword(user_text)

                # --- 4. 텍스트 보정 (NLU -> UI Text) ---
                if player_name and keyword:
                    display_user_text = f"{player_name} 선수 {keyword} 알려줘"
                elif user_text:
                    display_user_text = user_text
                
                # --- 5. 응답 생성 (의도 -> AI 텍스트) ---
                reply_text = self._get_reply(user_text, player_name, keyword)

            except Exception as e:
                print(f"--- ERROR: Failed to process PTT audio: {e}")
                reply_text = "오디오 처리 중 오류가 발생했습니다."

        # 💡💡💡 --- [gTTS 로직 복원] --- 💡💡💡
        # --- 6. TTS (AI 텍스트 -> AI 음성) 및 Base64 인코딩 ---
        audio_response_buffer = self._say(reply_text)
        audio_base64 = None
        if audio_response_buffer:
            audio_base64 = base64.b64encode(audio_response_buffer.read()).decode('utf-8')
        # 💡💡💡 --- [복원 완료] --- 💡💡💡
        
        # --- 7. 최종 JSON 반환 ---
        return {
            "ok": True,
            "display_user_text": display_user_text,
            "reply_text": reply_text,
            "audio_base64": audio_base64 # 💡 [복원] Base64 오디오 포함
        }


# --- 싱글톤 및 Blueprint ---
_singleton: Optional[VoiceAssistant] = None

def get_assistant() -> VoiceAssistant:
    """VoiceAssistant 싱글톤 객체를 반환합니다."""
    global _singleton
    if _singleton is None:
        _singleton = VoiceAssistant() # (서버 오류 수정됨)
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
