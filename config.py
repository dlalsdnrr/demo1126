import os
from typing import Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 날씨 API 키 (OpenWeatherMap)
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
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
VOICE_CONV_MODEL = "base"          # Whisper 모델 (모든 모드에서 사용)
VAD_AGGRESSIVENESS = 2             # 0~3 (높을수록 민감)
WAKE_WORD_CONFIDENCE = 0.3         # 트리거 민감도

# 실시간 스트리밍 VAD 설정
SILENCE_THRESHOLD = int(os.getenv("SILENCE_THRESHOLD", "500"))  # 음성 감지 임계값 (RMS)
SILENCE_DURATION = float(os.getenv("SILENCE_DURATION", "1.0"))  # 무음 판정 시간 (초)

# BLDC I2C 설정 (라즈베리파이에서 아두이노로)
I2C_BUS_INDEX = int(os.getenv("I2C_BUS_INDEX", "1"))  # 일반적으로 라즈베리파이는 1
I2C_ARDUINO_ADDR = int(os.getenv("I2C_ARDUINO_ADDR", "8"))  # 0x08

# I2C 실행 모드: auto | i2c | mock
I2C_MODE = os.getenv("I2C_MODE", "auto").lower()  # auto: 라즈베리파이에서만 I2C 사용, 그 외 mock

# BLE 브릿지 설정 (선택 사용)
BLE_ADAPTER_ADDR = os.getenv("BLE_ADAPTER_ADDR", "2C:CF:67:E9:50:B5")
BLE_SERVICE_UUID = os.getenv("BLE_SERVICE_UUID", "12345678-1234-5678-1234-56789abcdef0")
BLE_CHAR_UUID = os.getenv("BLE_CHAR_UUID", "abcdef01-1234-5678-1234-56789abcdef0")

