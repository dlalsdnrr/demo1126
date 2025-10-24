from __future__ import annotations

from flask import Blueprint, jsonify, request

import platform

try:
    from smbus2 import SMBus, i2c_msg
except Exception:  # pragma: no cover
    SMBus = None
    i2c_msg = None

from config import I2C_BUS_INDEX, I2C_ARDUINO_ADDR, I2C_MODE


bldc_bp = Blueprint("bldc", __name__)

_bus = None
_last_mock_commands = []  # 최근 전송 기록 (mock 모드 시 확인용)


def _is_raspberry_pi() -> bool:
    # 간단 판별: 머신명/플랫폼으로 확인
    uname = platform.uname()
    return any(x in uname.machine.lower() for x in ["arm", "aarch64"]) or "rasp" in uname.node.lower()


def _effective_mode() -> str:
    mode = (I2C_MODE or "auto").lower()
    if mode == "i2c":
        return "i2c" if SMBus is not None else "mock"
    if mode == "mock":
        return "mock"
    # auto: 라즈베리파이에서만 I2C, 그 외 mock
    if _is_raspberry_pi() and SMBus is not None:
        return "i2c"
    return "mock"


def _ensure_bus():
    global _bus
    if _effective_mode() != "i2c":
        return  # mock 모드에서는 버스 필요 없음
    if SMBus is None:
        raise RuntimeError("smbus2_not_installed")
    if _bus is None:
        _bus = SMBus(I2C_BUS_INDEX)


def _i2c_send_text(text: str) -> None:
    mode = _effective_mode()
    if mode == "i2c":
        _ensure_bus()
        data = list(text.encode("euc-kr", errors="ignore"))
        if len(data) > 32:
            data = data[:32]
        write = i2c_msg.write(I2C_ARDUINO_ADDR, data)
        _bus.i2c_rdwr(write)
    else:
        # mock: 기록만 남김
        _last_mock_commands.append(text)
        if len(_last_mock_commands) > 20:
            _last_mock_commands.pop(0)


@bldc_bp.route("/api/bldc/command", methods=["POST"])
def api_bldc_command():
    body = request.get_json(silent=True) or {}
    cmd = str(body.get("command") or "").strip().lower()
    if not cmd:
        return jsonify({"ok": False, "error": "missing_command"}), 400
    if cmd not in {"front", "back", "left", "right", "stop"}:
        return jsonify({"ok": False, "error": "invalid_command"}), 400
    try:
        _i2c_send_text(cmd)
        return jsonify({"ok": True, "mode": _effective_mode()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e) or "send_failed", "mode": _effective_mode()}), 500


@bldc_bp.route("/api/bldc/ping", methods=["GET"])
def api_bldc_ping():
    try:
        _i2c_send_text(" ")
        return jsonify({"ok": True, "mode": _effective_mode()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e) or "unavailable", "mode": _effective_mode()}), 500


@bldc_bp.route("/api/bldc/status", methods=["GET"])
def api_bldc_status():
    return jsonify({
        "ok": True,
        "mode": _effective_mode(),
        "lastMockCommands": list(_last_mock_commands),
        "i2c": {
            "addr": I2C_ARDUINO_ADDR,
            "bus": I2C_BUS_INDEX,
            "available": SMBus is not None,
        }
    })


@bldc_bp.route("/api/bldc/batch", methods=["POST"])
def api_bldc_batch():
    body = request.get_json(silent=True) or {}
    commands = body.get("commands") or []
    if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
        return jsonify({"ok": False, "error": "invalid_commands"}), 400
    try:
        for c in commands:
            c = c.strip().lower()
            if c in {"front", "back", "left", "right", "stop"}:
                _i2c_send_text(c)
        return jsonify({"ok": True, "mode": _effective_mode()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e) or "send_failed", "mode": _effective_mode()}), 500
