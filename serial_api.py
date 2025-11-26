from __future__ import annotations

from flask import Blueprint, jsonify, request

import time

try:
    import serial as pyserial
except Exception:  # pragma: no cover
    pyserial = None

from config import SERIAL_PORT as PORT, SERIAL_BAUD as BAUDRATE

# 전역 시리얼 핸들 (필요 시 열기)
ser = None


def _ensure_open():
    """시리얼 포트가 열려 있는지 확인하고, 필요 시 엽니다."""
    global ser
    if pyserial is None:
        raise RuntimeError("pyserial_not_installed")
    if ser is None or not getattr(ser, "is_open", False):
        try:
            ser = pyserial.Serial(PORT, BAUDRATE, timeout=1)
            # 아두이노 리셋 대기
            time.sleep(2)
            print(f"✓ 시리얼 포트 연결 성공: {PORT} ({BAUDRATE} baud)")
        except pyserial.SerialException as e:
            error_msg = f"시리얼 포트 연결 실패: {PORT} - {str(e)}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"시리얼 포트 열기 중 오류: {str(e)}"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg) from e


def _send_command(motor_id: int, position: int, speed: int) -> str:
    """
    'ID,위치,속도\n' 형식으로 명령을 전송하고, 아두이노로부터 응답을 받습니다.
    """
    _ensure_open()
    command = f"{motor_id},{position},{speed}\n".encode("utf-8")
    ser.write(command)
    resp = ser.readline().decode("utf-8", errors="ignore").strip()
    return resp


serial_bp = Blueprint("serial", __name__)


@serial_bp.route("/api/serial/send", methods=["POST"])
def api_serial_send():
    """
    JSON 형식의 데이터를 받아 다이나믹셀 제어 명령을 전송합니다.
    요청 데이터: {"motor_id": int, "position": int, "speed": int}
    """
    data = request.get_json(silent=True) or {}
    try:
        motor_id = int(data.get("motor_id"))
        position = int(data.get("position"))
        speed = int(data.get("speed", 0))  # 속도, 기본값 0
    except Exception:
        return jsonify({"ok": False, "error": "invalid_params"}), 400
    try:
        resp = _send_command(motor_id, position, speed)
        return jsonify({"ok": True, "response": resp})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e) or "send_failed"}), 500


@serial_bp.route("/api/serial/close", methods=["POST"])
def api_serial_close():
    """시리얼 포트를 닫습니다."""
    global ser
    try:
        if ser and getattr(ser, "is_open", False):
            ser.close()
            ser = None
    except Exception:
        pass
    return jsonify({"ok": True})
