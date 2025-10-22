import os
from typing import Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM5")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))
BASEBALL_ID = os.getenv("BASEBALL_ID", "")
MOTOR_ID_MAP: Dict[str, int] = {
    "R1": int(os.getenv("MOTOR_ID_R1", "25")),
    "R2": int(os.getenv("MOTOR_ID_R2", "50")),
    "RE": int(os.getenv("MOTOR_ID_RE", "75")),
    "L1": int(os.getenv("MOTOR_ID_L1", "100")),
    "L2": int(os.getenv("MOTOR_ID_L2", "125")),
    "LE": int(os.getenv("MOTOR_ID_LE", "150")),
}

# 음성 인식 설정
VOICE_WAKE_MODEL = "tiny"          # 대기/트리거 감지용 (빠름)
VOICE_CONVERSATION_MODEL = "base"  # 실제 대화용 (정확)
VAD_AGGRESSIVENESS = 2             # 0~3 (높을수록 민감)
WAKE_WORD_CONFIDENCE = 0.3         # 트리거 민감도

