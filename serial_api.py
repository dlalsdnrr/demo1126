from __future__ import annotations

from flask import Blueprint, jsonify, request

import time

try:
    import serial as pyserial
    from serial.tools import list_ports
except Exception:  # pragma: no cover
    pyserial = None
    list_ports = None

from config import SERIAL_PORT as PORT, SERIAL_BAUD as BAUDRATE

# 전역 시리얼 핸들 (필요 시 열기)
ser = None
_detected_port = None


def _find_serial_port():
    """시리얼 포트를 자동으로 찾습니다."""
    global _detected_port
    
    # 이미 찾은 포트가 있고 사용 가능하면 재사용
    if _detected_port:
        try:
            test_ser = pyserial.Serial(_detected_port, BAUDRATE, timeout=1)
            test_ser.close()
            return _detected_port
        except (pyserial.SerialException, OSError):
            _detected_port = None  # 포트가 더 이상 사용 불가능하면 재검색
    
    # config에서 지정된 포트가 있으면 먼저 시도
    if PORT:
        try:
            test_ser = pyserial.Serial(PORT, BAUDRATE, timeout=1)
            test_ser.close()
            _detected_port = PORT
            print(f"✓ 지정된 포트 사용: {PORT}")
            return PORT
        except (pyserial.SerialException, OSError):
            print(f"⚠ 지정된 포트 {PORT} 사용 불가, 자동 검색 중...")
    
    # 자동 검색
    if list_ports is None:
        return None
    
    ports = list_ports.comports()
    
    # Linux: ttyACM, ttyUSB 우선
    for port in ports:
        port_name = port.device
        if 'ttyACM' in port_name or 'ttyUSB' in port_name:
            try:
                test_ser = pyserial.Serial(port_name, BAUDRATE, timeout=1)
                test_ser.close()
                _detected_port = port_name
                print(f"✓ 자동 검색된 포트: {port_name}")
                return port_name
            except (pyserial.SerialException, OSError):
                continue
    
    # Windows: COM 포트
    for port in ports:
        port_name = port.device
        if port_name.startswith('COM'):
            try:
                test_ser = pyserial.Serial(port_name, BAUDRATE, timeout=1)
                test_ser.close()
                _detected_port = port_name
                print(f"✓ 자동 검색된 포트: {port_name}")
                return port_name
            except (pyserial.SerialException, OSError):
                continue
    
    return None


def _ensure_open():
    """시리얼 포트가 열려 있는지 확인하고, 필요 시 엽니다."""
    global ser
    if pyserial is None:
        raise RuntimeError("pyserial_not_installed")
    if ser is None or not getattr(ser, "is_open", False):
        # 포트 자동 검색
        detected_port = _find_serial_port()
        if not detected_port:
            error_msg = "시리얼 포트를 찾을 수 없습니다"
            print(f"✗ {error_msg}")
            raise RuntimeError(error_msg)
        
        try:
            ser = pyserial.Serial(detected_port, BAUDRATE, timeout=1)
            # 아두이노 리셋 대기
            time.sleep(2)
            print(f"✓ 시리얼 포트 연결 성공: {detected_port} ({BAUDRATE} baud)")
        except pyserial.SerialException as e:
            error_msg = f"시리얼 포트 연결 실패: {detected_port} - {str(e)}"
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
