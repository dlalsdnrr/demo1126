from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Dict, Any, List, Optional


# macros.json 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MACROS_PATH = os.path.join(BASE_DIR, "macros.json")

# 모터 ID 매핑 가져오기
from config import MOTOR_ID_MAP


def resolve_motor_id(motor_id_value: Any) -> int:
    """
    motor_id 값을 실제 모터 ID 숫자로 변환합니다.
    - 숫자인 경우: 그대로 반환 (하위 호환성)
    - 문자열인 경우: MOTOR_ID_MAP에서 조회
    """
    if isinstance(motor_id_value, int):
        return motor_id_value
    
    if isinstance(motor_id_value, str):
        # 문자열이 숫자인 경우
        if motor_id_value.isdigit():
            return int(motor_id_value)
        # 문자열 키로 매핑 테이블 조회
        motor_id_value_upper = motor_id_value.upper()
        if motor_id_value_upper in MOTOR_ID_MAP:
            return MOTOR_ID_MAP[motor_id_value_upper]
        raise ValueError(f"Unknown motor ID key: {motor_id_value}")
    
    # 기타 타입은 정수로 변환 시도
    return int(motor_id_value)


def _load_macros() -> Dict[str, Any]:
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


def _normalize_event_name(text: str) -> str:
    """
    다양한 원본 텍스트(예: '삼진 아웃', '삼진아웃', '홈런', 'HR', 'strikeout', '볼넷', 'walk')를
    매크로 키로 사용할 표준 명칭으로 변환합니다.
    우선순위: 한국어 키워드 우선, 이후 영어/코드 매핑.
    """
    if not text:
        return ""
    t = str(text).strip().lower()

    # 한글 키워드 우선 매핑
    ko_map = {
        "홈런": "홈런",
        "아웃": "아웃",
        "삼진": "삼진아웃",
        "삼진아웃": "삼진아웃",
        "스트라이크": "스트라이크",
        "볼": "볼",
        "볼넷": "볼넷",
        "안타": "1루타",
        "1루타": "1루타",
        "2루타": "2루타",
        "3루타": "3루타",
        "도루": "도루",
        "에러": "에러",
        "실책": "에러",
    }
    for k, v in ko_map.items():
        if k in t:
            return v

    # 영문/코드 패턴 매핑
    patterns = [
        (r"\bhr\b|home\s*run|homerun", "홈런"),
        (r"\bso\b|strike\s*out|strikeout", "삼진아웃"),
        (r"\bout\b", "아웃"),
        (r"\bwalk\b|base\s*on\s*balls|bb\b", "볼넷"),
        (r"\berror\b|e\b", "에러"),
        (r"\bsingle\b|1b\b", "1루타"),
        (r"\bdouble\b|2b\b", "2루타"),
        (r"\btriple\b|3b\b", "3루타"),
        (r"\bsteal\b|sb\b", "도루"),
        (r"\bstrike\b", "스트라이크"),
        (r"\bball\b", "볼"),
    ]
    for pat, name in patterns:
        if re.search(pat, t):
            return name

    return ""


def _get_macro_steps_by_name(name: str) -> List[Dict[str, Any]]:
    data = _load_macros()
    return data.get("macros", {}).get(name) or []


def _get_macro_steps_by_event_text(event_text: str) -> List[Dict[str, Any]]:
    key = _normalize_event_name(event_text)
    if not key:
        return []
    return _get_macro_steps_by_name(key)


try:
    from serial_api import _send_command  # type: ignore
except Exception:  # pragma: no cover
    _send_command = None  # type: ignore


def _run_steps_blocking(steps: List[Dict[str, Any]]) -> None:
    if _send_command is None:
        return
    for s in steps:
        motor_id = resolve_motor_id(s.get("motor_id"))
        position = int(s.get("position"))
        speed = int(s.get("speed", 0)) if str(s.get("speed", "")).isdigit() else 0
        delay_ms = int(s.get("delay_ms")) if str(s.get("delay_ms")).isdigit() else 200
        try:
            _send_command(motor_id, position, speed)
        finally:
            time.sleep(max(0, delay_ms) / 1000.0)


def _run_steps_blocking_strict(steps: List[Dict[str, Any]]) -> None:
    """시리얼이 불가하면 예외를 발생시켜 호출자가 실패를 알 수 있게 합니다."""
    if _send_command is None:
        raise RuntimeError("serial_unavailable")
    for s in steps:
        motor_id = resolve_motor_id(s.get("motor_id"))
        position = int(s.get("position"))
        speed = int(s.get("speed", 0)) if str(s.get("speed", "")).isdigit() else 0
        delay_ms = int(s.get("delay_ms")) if str(s.get("delay_ms")).isdigit() else 200
        try:
            _send_command(motor_id, position, speed)
        finally:
            time.sleep(max(0, delay_ms) / 1000.0)


def run_macro_by_name_async(name: str) -> bool:
    steps = _get_macro_steps_by_name(name)
    if not steps:
        return False
    th = threading.Thread(target=_run_steps_blocking, args=(steps,), daemon=True)
    th.start()
    return True


def run_macro_by_event_text_async(event_text: str) -> bool:
    steps = _get_macro_steps_by_event_text(event_text)
    if not steps:
        return False
    th = threading.Thread(target=_run_steps_blocking, args=(steps,), daemon=True)
    th.start()
    return True


def run_macro_by_name_blocking(name: str) -> None:
    """매크로를 동기적으로 실행합니다. 실패 시 예외를 던집니다."""
    steps = _get_macro_steps_by_name(name)
    if not steps:
        raise ValueError("not_found_or_empty")
    _run_steps_blocking_strict(steps)


def last_event_to_trigger_text(last_event: Optional[Dict[str, Any]]) -> str:
    """
    game_routes/daum_routes의 last_event 구조를 받아 트리거 문자열을 뽑습니다.
    우선순위: type 우선, 없으면 description 사용.
    """
    if not last_event or not isinstance(last_event, dict):
        return ""
    ev_type = str(last_event.get("type") or "").strip()
    desc = str(last_event.get("description") or "").strip()

    # game_routes의 타입 코드 매핑
    type_map = {
        "hr": "홈런",
        "out": "아웃",
        "strikeout": "삼진아웃",
        "strike": "스트라이크",
        "ball": "볼",
        "walk": "볼넷",
        "single": "1루타",
        "double": "2루타",
        "triple": "3루타",
        "error": "에러",
    }
    if ev_type:
        key = type_map.get(ev_type.lower())
        if key:
            return key
    return desc


