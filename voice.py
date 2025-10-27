from __future__ import annotations

import os
import io
import base64
import tempfile
import time
import difflib
import subprocess
import json
import requests
from typing import Optional, Dict, Any

from flask import Blueprint, jsonify, request
import google.generativeai as genai

from config import GEMINI_API_KEY, WEATHER_API_KEY

# ============================================================================
# API 및 모듈 초기화
# ============================================================================

# --- Gemini API ---
GEMINI_AVAILABLE = False
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print("✓ Gemini API 설정 완료")
    except Exception as e:
        print(f"✗ Gemini API 설정 실패: {e}")
else:
    print("✗ Gemini API Key 없음 (GEMINI_API_KEY 환경변수 필요)")

# --- STT: Faster Whisper ---
STT_AVAILABLE = False
WHISPER_MODEL = None
try:
    from faster_whisper import WhisperModel
    STT_AVAILABLE = True
    print("✓ Faster Whisper STT 로드 성공")
except ImportError:
    print("✗ faster-whisper 미설치. 실행: pip install faster-whisper")
    WhisperModel = None
except Exception as e:
    print(f"✗ Faster Whisper 초기화 실패: {e}")
    WhisperModel = None

# --- 오디오 처리: ffmpeg ---
FFMPEG_AVAILABLE = False
FFMPEG_PATH = None
def find_ffmpeg():
    global FFMPEG_PATH, FFMPEG_AVAILABLE
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        FFMPEG_PATH = env_path
        FFMPEG_AVAILABLE = True
        return True
    try:
        result = subprocess.run(["where" if os.name == "nt" else "which", "ffmpeg"], capture_output=True, text=True, check=True)
        path = result.stdout.strip().split('\n')[0]
        if path and os.path.exists(path):
            FFMPEG_PATH = path
            FFMPEG_AVAILABLE = True
            return True
    except: pass
    return False

if find_ffmpeg():
    print(f"✓ ffmpeg 찾음: {FFMPEG_PATH}")
else:
    print("✗ ffmpeg 없음. 다운로드: https://www.gyan.dev/ffmpeg/builds/")

# --- TTS: gTTS & edge-tts ---
GTTS_AVAILABLE = False
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    print("✓ gTTS 로드 성공")
except:
    print("✗ gTTS 미설치. 실행: pip install gTTS")
    gTTS = None

EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    import asyncio
    EDGE_TTS_AVAILABLE = True
    print("✓ edge-tts 로드 성공")
except:
    print("ℹ edge-tts 미사용 (gTTS로 대체)")
    edge_tts, asyncio = None, None
    
# ============================================================================
# 외부 서비스 호출 (날씨)
# ============================================================================

def get_yongin_weather() -> Optional[Dict[str, Any]]:
    if not WEATHER_API_KEY:
        print("✗ 날씨 API Key 없음 (WEATHER_API_KEY 환경변수 필요)")
        return None
    
    # 용인시청 좌표
    lat, lon = 37.2215, 127.1873
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric&lang=kr"
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        # 필요한 정보만 간추리기
        return {
            "상태": data["weather"][0]["description"],
            "온도": f"{data['main']['temp']:.1f}°C",
            "체감온도": f"{data['main']['feels_like']:.1f}°C",
            "습도": f"{data['main']['humidity']}%",
            "풍속": f"{data['wind']['speed']:.1f}m/s"
        }
    except Exception as e:
        print(f"✗ 날씨 정보 조회 실패: {e}")
        return None

# ============================================================================
# 핵심 기능 (STT, TTS, 오디오 변환)
# ============================================================================

def convert_audio_to_wav(input_bytes: bytes) -> Optional[bytes]:
    """ffmpeg로 오디오를 16kHz mono WAV로 변환"""
    if not FFMPEG_AVAILABLE:
        print("✗ ffmpeg 없음")
        return None
    
    input_file = None
    output_file = None
    
    try:
        # 입력 임시 파일
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
            f.write(input_bytes)
            input_file = f.name
        
        # 출력 임시 파일
        output_file = tempfile.mktemp(suffix=".wav")
        
        # ffmpeg 변환
        cmd = [
            FFMPEG_PATH,
            "-i", input_file,
            "-ar", "16000",  # 16kHz
            "-ac", "1",       # mono
            "-sample_fmt", "s16",  # 16-bit
            "-f", "wav",
            "-y",  # 덮어쓰기
            output_file
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True
        )
        
        # 출력 파일 읽기
        with open(output_file, "rb") as f:
            return f.read()
            
    except Exception as e:
        print(f"✗ ffmpeg 변환 실패: {e}")
        return None
    finally:
        # 임시 파일 정리
        if input_file and os.path.exists(input_file):
            try:
                os.remove(input_file)
            except:
                pass
        if output_file and os.path.exists(output_file):
            try:
                os.remove(output_file)
            except:
                pass

def speak_gtts(text: str) -> Optional[str]:
    """gTTS로 음성 합성 후 base64 반환"""
    if not GTTS_AVAILABLE:
        return None
    
    try:
        print(f"→ gTTS 생성: {text[:30]}...")
        buffer = io.BytesIO()
        tts = gTTS(text=text, lang='ko')
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode('utf-8')
    except Exception as e:
        print(f"✗ gTTS 실패: {e}")
        return None

def speak_edge_tts(text: str) -> Optional[str]:
    """edge-tts로 음성 합성 후 base64 반환"""
    if not EDGE_TTS_AVAILABLE:
        return None
    
    try:
        print(f"→ edge-tts 생성: {text[:30]}...")
        
        async def generate():
            communicate = edge_tts.Communicate(text, "ko-KR-SunHiNeural", rate="+10%")
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            return base64.b64encode(audio_data).decode('utf-8')
        
        # 이벤트 루프 실행
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(generate())
        
    except Exception as e:
        print(f"✗ edge-tts 실패: {e}")
        return None

def get_tts_audio(text: str) -> Optional[str]:
    """TTS 오디오 생성 (edge-tts 우선, 실패 시 gTTS)"""
    # 1순위: edge-tts
    result = speak_edge_tts(text)
    if result:
        return result
    
    # 2순위: gTTS
    result = speak_gtts(text)
    if result:
        return result
    
    print("✗ 모든 TTS 엔진 실패")
    return None

def load_whisper_model() -> Optional[Any]:
    """Faster Whisper 모델 초기화"""
    global WHISPER_MODEL, STT_AVAILABLE
    
    if not STT_AVAILABLE:
        return None
    
    if WHISPER_MODEL is None:
        try:
            model_name = "small"
            print(f"→ Whisper 모델 로딩 중 ({model_name})...")
            WHISPER_MODEL = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                cpu_threads=4
            )
            print("✓ Whisper 모델 로드 완료")
        except Exception as e:
            print(f"✗ Whisper 모델 로드 실패: {e}")
            STT_AVAILABLE = False
            WHISPER_MODEL = None
    
    return WHISPER_MODEL

# ============================================================================
# VoiceAssistant 클래스
# ============================================================================

class VoiceAssistant:
    def __init__(self):
        self.whisper_model = load_whisper_model()
        self.gemini_model = genai.GenerativeModel('gemini-2.5-flash') if GEMINI_AVAILABLE else None
        
        self.PLAYERS_DATA = {
            "김영웅": {"타율": 0.625, "홈런": 3, "안타": 10},
            "문현빈": {"타율": 0.444, "홈런": 2, "안타": 8},
            "노시환": {"타율": 0.429, "홈런": 2, "안타": 9},
            "리베라토": {"타율": 0.389, "홈런": 1, "안타": 7},
            "김태훈": {"타율": 0.353, "홈런": 2, "안타": 6},
            "최재훈": {"타율": 0.353, "홈런": 0, "안타": 6},
            "채은성": {"타율": 0.350, "홈런": 0, "안타": 7},
            "하주석": {"타율": 0.350, "홈런": 0, "안타": 7},
            "구자욱": {"타율": 0.313, "홈런": 0, "안타": 5},
            "이재현": {"타율": 0.294, "홈런": 1, "안타": 5},
            "디아즈": {"타율": 0.278, "홈런": 0, "안타": 5},
            "손아섭": {"타율": 0.263, "홈런": 0, "안타": 5},
            "김성윤": {"타율": 0.261, "홈런": 0, "안타": 6},
            "김지찬": {"타율": 0.190, "홈런": 0, "안타": 4},
            "강민호": {"타율": 0.188, "홈런": 1, "안타": 3},
            "심우준": {"타율": 0.077, "홈런": 0, "안타": 1}
        }
    
    def transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """오디오를 텍스트로 변환 (STT) - 노이즈 환경 최적화"""
        if not STT_AVAILABLE or not self.whisper_model:
            print("✗ STT 불가: Whisper 모델 없음")
            return None
        
        temp_path = None
        try:
            # 노이즈 제거 (설치된 경우)
            # processed_audio = reduce_noise_from_wav(audio_bytes) # 기존 노이즈 제거 로직 제거
            
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                f.write(audio_bytes)
                temp_path = f.name
            
            # Whisper 변환 (균형잡힌 설정)
            print("→ STT 처리 중...")
            segments, info = self.whisper_model.transcribe(
                temp_path,
                language="ko",
                beam_size=5,              # 더 정확한 디코딩
                best_of=5,                # 최상의 결과 선택
                temperature=0.0,          # 확정적 결과 (랜덤성 제거)
                vad_filter=True,          # 음성 구간만 감지
                vad_parameters={
                    "threshold": 0.3,                # 음성 감지 임계값 (관대하게)
                    "min_speech_duration_ms": 100,   # 최소 음성 길이 (짧은 말도 인식)
                    "max_speech_duration_s": 30,     # 최대 음성 길이
                    "min_silence_duration_ms": 300,  # 최소 묵음 길이
                    "speech_pad_ms": 300             # 음성 앞뒤 여유
                },
                condition_on_previous_text=False,  # 이전 텍스트 영향 제거
                compression_ratio_threshold=2.4,   # 반복/쓰레기 텍스트 제거
                log_prob_threshold=-1.0,           # 낮은 확률 세그먼트 제거
                no_speech_threshold=0.4            # 음성 없음 임계값 (관대하게)
            )
            
            # 세그먼트 수 확인
            segments_list = list(segments)
            print(f"  감지된 세그먼트: {len(segments_list)}개")
            
            if not segments_list:
                print("✗ STT 결과 없음 (음성 구간 미감지)")
                print("  → 더 크게 말씀해 주세요")
                return None
            
            # 텍스트 조립
            text = " ".join(s.text.strip() for s in segments_list).strip().lower()
            
            # 빈 결과 체크 (더 관대하게)
            if not text or len(text) < 1:
                print("✗ STT 결과 없음")
                return None
            
            print(f"✓ STT 결과: '{text}'")
            print(f"  언어: {info.language} (확률: {info.language_probability:.2%})")
            return text
            
        except Exception as e:
            print(f"✗ STT 실패: {e}")
            return None
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    def generate_gemini_response(self, user_query: str) -> str:
        if not self.gemini_model:
            return "Gemini AI 모델이 준비되지 않았습니다."

        weather_data = get_yongin_weather()
        player_data_str = json.dumps(self.PLAYERS_DATA, ensure_ascii=False, indent=2)
        
        prompt = f"""
        당신은 KBO 리그 삼성 라이온즈와 한화 이글스 선수들의 기록에 대해 답하고, 용인의 현재 날씨를 알려주는 친절한 AI 야구 비서입니다.

        # 지침:
        1. 반드시 한국어로, 어린 아이에게 말하듯 친절하고 간결하게 답변하세요.
        2. 답변은 1-2 문장으로 짧게 유지하세요.
        3. 선수 기록 질문은 아래 `선수 기록 데이터`를 기반으로만 답하세요. 데이터에 없는 선수는 "죄송해요, 그 선수의 정보는 아직 없어요."라고 답하세요.
        4. 날씨 질문은 아래 `실시간 용인 날씨` 데이터를 기반으로 답하세요. 날씨 데이터가 없으면 "날씨 정보를 가져올 수 없었어요."라고 답하세요.
        5. 대화의 맥락과 상관없는 일반적인 질문에는 "저는 야구 전문 비서예요."라고 답하세요.
        6. 음성이 오인식 될 수 있으니 비슷한 이름의 선수, 기능을 생각해서 답해주세요. ex) 날 쉬었대 -> 날씨어때, 김진찬 -> 김지찬 등

        ---
        # 선수 기록 데이터 (JSON):
        {player_data_str}
        ---
        # 실시간 용인 날씨:
        {json.dumps(weather_data, ensure_ascii=False, indent=2) if weather_data else "데이터 없음"}
        ---

        # 사용자 질문:
        "{user_query}"

        # AI 답변:
        """
        
        try:
            print("→ Gemini 응답 생성 중...")
            response = self.gemini_model.generate_content(prompt)
            reply = response.text.strip()
            print(f"✓ Gemini 응답: {reply}")
            return reply
        except Exception as e:
            print(f"✗ Gemini API 호출 실패: {e}")
            return "AI 응답 생성에 실패했어요."

    def process_audio(self, audio_file) -> Dict[str, Any]:
        """오디오 처리 메인 함수"""
        start_time = time.time()
        
        # 초기화
        user_text = None
        reply_text = None
        audio_base64 = None
        display_text = "..."
        
        # 필수 모듈 체크
        if not STT_AVAILABLE:
            reply_text = "STT 모듈(Faster Whisper)이 설치되지 않았습니다."
        elif not FFMPEG_AVAILABLE:
            reply_text = "ffmpeg가 설치되지 않았습니다. 다운로드: https://www.gyan.dev/ffmpeg/builds/"
        else:
            try:
                # 1. 오디오 디코딩 (webm → wav)
                print("→ 오디오 디코딩 중...")
                t1 = time.time()
                
                # 업로드된 파일을 바이트로 읽기
                audio_file.seek(0)
                input_bytes = audio_file.read()
                
                # ffmpeg로 변환
                wav_bytes = convert_audio_to_wav(input_bytes)
                
                if not wav_bytes:
                    raise RuntimeError("오디오 변환 실패")
                    
                print(f"✓ 디코딩 완료 ({time.time()-t1:.2f}s)")
                
                # 2. STT
                t2 = time.time()
                user_text = self.transcribe_audio(wav_bytes)
                print(f"✓ STT 완료 ({time.time()-t2:.2f}s)")
                
                # 3. NLU
                # player = self.find_player(user_text) if user_text else None # 기존 플레이어 찾기 로직 제거
                # keyword = self.find_keyword(user_text) if user_text else None # 기존 키워드 찾기 로직 제거
                
                # 4. 텍스트 보정
                # if player and keyword: # 기존 텍스트 보정 로직 제거
                #     display_text = f"{player} 선수 {keyword} 알려줘"
                # elif user_text:
                #     display_text = user_text
                # else:
                #     display_text = "음성 인식 실패"
                
                # 5. 응답 생성
                reply_text = self.generate_gemini_response(user_text)
                
            except Exception as e:
                print(f"✗ 처리 실패: {e}")
                import traceback
                traceback.print_exc()
                reply_text = f"오디오 처리 중 오류 발생: {str(e)}"
        
        # 6. TTS
        if reply_text:
            t3 = time.time()
            audio_base64 = get_tts_audio(reply_text)
            print(f"✓ TTS 완료 ({time.time()-t3:.2f}s)")
        
        total_time = time.time() - start_time
        print(f"✓ 전체 처리 시간: {total_time:.2f}s")
        
        return {
            "ok": True,
            "display_user_text": display_text,
            "reply_text": reply_text,
            "audio_base64": audio_base64
        }

# ============================================================================
# 싱글톤 및 Blueprint
# ============================================================================

_assistant: Optional[VoiceAssistant] = None
def get_assistant() -> VoiceAssistant:
    global _assistant
    if _assistant is None: _assistant = VoiceAssistant()
    return _assistant

voice_bp = Blueprint("voice", __name__)
@voice_bp.route("/api/voice/process_ptt", methods=["POST"])
def api_process_ptt():
    assistant = get_assistant()
    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({"ok": False, "error": "오디오 파일 없음"}), 400
    
    result = assistant.process_audio(audio_file)
    return jsonify(result)
