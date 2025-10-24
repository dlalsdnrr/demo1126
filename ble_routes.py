from __future__ import annotations

from flask import Blueprint, jsonify, request

import threading
import time
import platform

try:
    from bluezero import peripheral as ble_peripheral
except Exception:  # pragma: no cover
    ble_peripheral = None

try:
    from smbus2 import SMBus, i2c_msg
except Exception:  # pragma: no cover
    SMBus = None
    i2c_msg = None

from config import (
    BLE_ADAPTER_ADDR,
    BLE_SERVICE_UUID,
    BLE_CHAR_UUID,
    I2C_BUS_INDEX,
    I2C_ARDUINO_ADDR,
)


ble_bp = Blueprint("ble", __name__)

_state_lock = threading.Lock()
_thread: threading.Thread | None = None
_running = False
_advertising = False
_last_received = "Hello from Pi"
_bus = None
_periph = None


def _is_raspberry_pi() -> bool:
    uname = platform.uname()
    return any(x in uname.machine.lower() for x in ["arm", "aarch64"]) or "rasp" in uname.node.lower()


def _effective_mode() -> str:
    if ble_peripheral is not None and _is_raspberry_pi():
        return "ble"
    return "mock"


def _ensure_bus():
    global _bus
    if SMBus is None:
        return None
    if _bus is None:
        _bus = SMBus(I2C_BUS_INDEX)
    return _bus


def _i2c_send_text(text: str) -> None:
    bus = _ensure_bus()
    if bus is None:
        return  # mock I2C
    data = list(text.encode("euc-kr", errors="ignore"))
    if len(data) > 32:
        data = data[:32]
    write = i2c_msg.write(I2C_ARDUINO_ADDR, data)
    bus.i2c_rdwr(write)


def _ble_thread_main():
    global _periph, _advertising, _running, _last_received
    if _effective_mode() != "ble":
        # mock loop
        with _state_lock:
            _advertising = True
        try:
            while True:
                with _state_lock:
                    if not _running:
                        break
                time.sleep(0.5)
        finally:
            with _state_lock:
                _advertising = False
        return

    if ble_peripheral is None:
        return

    def read_callback(options):
        with _state_lock:
            return (_last_received or "").encode("utf-8")

    def write_callback(value, options):
        try:
            msg = value.decode("utf-8", errors="ignore")
        except Exception:
            msg = str(value)
        with _state_lock:
            _last_received = f"Pi received: {msg}"
        try:
            _i2c_send_text(msg)
        except Exception:
            pass

    try:
        _periph = ble_peripheral.Peripheral(BLE_ADAPTER_ADDR, local_name='kimjunha-desktop')
        _periph.add_service(srv_id=1, uuid=BLE_SERVICE_UUID, primary=True)
        _periph.add_characteristic(
            srv_id=1,
            chr_id=1,
            uuid=BLE_CHAR_UUID,
            value=bytearray(b'Hello from Pi'),
            notifying=False,
            flags=['read', 'write', 'write-without-response'],
            read_callback=read_callback,
            write_callback=write_callback,
        )
        _periph.publish()
        time.sleep(0.5)
        _periph.advertise(name='kimjunha-desktop')
        with _state_lock:
            _advertising = True
        while True:
            with _state_lock:
                if not _running:
                    break
            time.sleep(0.5)
    finally:
        try:
            if _periph is not None and hasattr(_periph, 'stop'):
                _periph.stop()
        except Exception:
            pass
        with _state_lock:
            _advertising = False


@ble_bp.route('/api/ble/start', methods=['POST'])
def api_ble_start():
    global _thread, _running
    with _state_lock:
        if _running:
            return jsonify({"ok": True, "mode": _effective_mode(), "running": True, "advertising": _advertising})
        _running = True
    t = threading.Thread(target=_ble_thread_main, daemon=True)
    _thread = t
    t.start()
    return jsonify({"ok": True, "mode": _effective_mode(), "running": True})


@ble_bp.route('/api/ble/stop', methods=['POST'])
def api_ble_stop():
    global _running
    with _state_lock:
        _running = False
    return jsonify({"ok": True})


@ble_bp.route('/api/ble/status', methods=['GET'])
def api_ble_status():
    with _state_lock:
        return jsonify({
            "ok": True,
            "mode": _effective_mode(),
            "running": _running,
            "advertising": _advertising,
            "adapter": BLE_ADAPTER_ADDR,
            "service": BLE_SERVICE_UUID,
            "characteristic": BLE_CHAR_UUID,
            "last_received": _last_received,
            "i2c": {"available": SMBus is not None, "addr": I2C_ARDUINO_ADDR, "bus": I2C_BUS_INDEX},
        })


@ble_bp.route('/api/ble/simulate-write', methods=['POST'])
def api_ble_simulate_write():
    body = request.get_json(silent=True) or {}
    msg = str(body.get('message') or '').strip()
    if not msg:
        return jsonify({"ok": False, "error": "missing_message"}), 400
    with _state_lock:
        global _last_received
        _last_received = f"Pi received: {msg}"
    try:
        _i2c_send_text(msg)
    except Exception:
        pass
    return jsonify({"ok": True})
