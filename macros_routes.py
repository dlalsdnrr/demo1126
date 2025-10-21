from __future__ import annotations

import json
import os
import time
from typing import List, Dict, Any

from flask import Blueprint, jsonify, request, render_template
from macros_executor import run_macro_by_name_async, run_macro_by_event_text_async, run_macro_by_name_blocking
from motor_config import MOTOR_ID_MAP

try:
    from serial_api import _send_command
except Exception:
    _send_command = None  # pragma: no cover


macros_bp = Blueprint("macros", __name__)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MACROS_PATH = os.path.join(BASE_DIR, "macros.json")


def load_macros() -> Dict[str, Any]:
    if not os.path.exists(MACROS_PATH):
        return {"macros": {}}
    try:
        with open(MACROS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "macros" not in data:
                return {"macros": {}}
            return data
    except Exception:
        return {"macros": {}}


def save_macros(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MACROS_PATH), exist_ok=True)
    with open(MACROS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@macros_bp.route("/macros")
def page_macros():
    return render_template("macro.html")


@macros_bp.route("/api/macros", methods=["GET"])
def api_list_macros():
    data = load_macros()
    return jsonify({"ok": True, "macros": data.get("macros", {})})


@macros_bp.route("/api/macros/<name>", methods=["GET"])
def api_get_macro(name: str):
    data = load_macros()
    steps = data.get("macros", {}).get(name)
    if steps is None:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "name": name, "steps": steps})


@macros_bp.route("/api/macros", methods=["POST"])
def api_save_macro():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    steps = body.get("steps") or []
    if not name:
        return jsonify({"ok": False, "error": "missing_name"}), 400
    if not isinstance(steps, list) or any(
        not isinstance(s, dict) or not ("motor_id" in s and "position" in s) for s in steps
    ):
        return jsonify({"ok": False, "error": "invalid_steps"}), 400

    data = load_macros()
    data.setdefault("macros", {})[name] = steps
    save_macros(data)
    return jsonify({"ok": True})


@macros_bp.route("/api/macros/<name>", methods=["DELETE"])
def api_delete_macro(name: str):
    data = load_macros()
    if name in data.get("macros", {}):
        del data["macros"][name]
        save_macros(data)
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not_found"}), 404


@macros_bp.route("/api/macros/run", methods=["POST"])
def api_run_macro():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "missing_name"}), 400
    data = load_macros()
    steps: List[Dict[str, Any]] = data.get("macros", {}).get(name) or []
    if not steps:
        return jsonify({"ok": False, "error": "not_found_or_empty"}), 404

    # 비동기로 실행을 전환하여 HTTP 응답 지연 최소화
    ok = run_macro_by_name_async(name)
    if not ok:
        return jsonify({"ok": False, "error": "run_failed"}), 500
    return jsonify({"ok": True})


@macros_bp.route("/api/macros/run-sync", methods=["POST"])
def api_run_macro_sync():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "missing_name"}), 400
    try:
        run_macro_by_name_blocking(name)
        return jsonify({"ok": True})
    except ValueError as ve:
        return jsonify({"ok": False, "error": str(ve) or "not_found_or_empty"}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e) or "run_failed"}), 500
@macros_bp.route("/api/macros/export", methods=["GET"])
def api_export_macros():
    data = load_macros()
    return jsonify({"ok": True, **data})


@macros_bp.route("/api/macros/import", methods=["POST"])
def api_import_macros():
    body = request.get_json(silent=True) or {}
    macros = body.get("macros")
    if not isinstance(macros, dict):
        return jsonify({"ok": False, "error": "invalid_macros"}), 400
    save_macros({"macros": macros})
    return jsonify({"ok": True})


@macros_bp.route("/api/macros/run-event", methods=["POST"])
def api_run_event_macro():
    body = request.get_json(silent=True) or {}
    text = str(body.get("event") or body.get("text") or body.get("name") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "missing_event"}), 400
    ok = run_macro_by_event_text_async(text)
    if not ok:
        return jsonify({"ok": False, "error": "not_found_or_empty"}), 404
    return jsonify({"ok": True})


@macros_bp.route("/api/motor-config", methods=["GET"])
def api_get_motor_config():
    """모터 ID 매핑 설정을 반환합니다."""
    # MOTOR_ID_MAP을 역으로 변환: { id: key } 형태로 반환
    motor_map_list = []
    for key, motor_id in MOTOR_ID_MAP.items():
        motor_map_list.append({
            "key": key,
            "id": motor_id,
            "label": get_motor_label(key, motor_id)
        })
    return jsonify({"ok": True, "motors": motor_map_list})


def get_motor_label(key: str, motor_id: int) -> str:
    """모터 키에 대한 설명 레이블을 반환합니다."""
    labels = {
        "R1": "오른쪽 어깨1",
        "R2": "오른쪽 어깨2", 
        "RE": "오른쪽 팔꿈치",
        "L1": "왼쪽 어깨1",
        "L2": "왼쪽 어깨2",
        "LE": "왼쪽 팔꿈치",
    }
    desc = labels.get(key, "")
    return f"{key} · {desc}" if desc else f"{key} (ID:{motor_id})"

