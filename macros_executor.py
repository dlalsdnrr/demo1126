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

# 여러 매크로 파일 지원 (데모 시나리오용)
MACRO_FILES = {
    "hello": os.path.join(BASE_DIR, "hello.json"),
    "hifive": os.path.join(BASE_DIR, "hifive.json"),
    "fighting": os.path.join(BASE_DIR, "fighting.json"),
    "차렷자세": os.path.join(BASE_DIR, "hold.json"),
    "김지찬 응원가": os.path.join(BASE_DIR, "kimjichan.json"),
    "김도영 응원가": os.path.join(BASE_DIR, "kimdoyoung.json"),
    "아웃(삐끼삐끼)": os.path.join(BASE_DIR, "out.json"),
    "외쳐라 최강기아": os.path.join(BASE_DIR, "kia.json"),
    "홈런": os.path.join(BASE_DIR, "homerun.json"),
}

_macro_file_cache: Dict[str, Dict[str, Any]] = {}
_macro_file_mtime: Dict[str, Optional[float]] = {key: None for key in MACRO_FILES}
_macro_file_lock = threading.Lock()

_macro_file_cache: Dict[str, Dict[str, Any]] = {}
_macro_file_mtime: Dict[str, Optional[float]] = {key: None for key in MACRO_FILES}
_macro_file_lock = threading.Lock()

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

# 전역 포트 오류 표시 플래그 (한 번만 출력)
_global_port_error_shown = False
_port_error_lock = threading.Lock()


def calculate_macro_duration(file_key: str, macro_name: str) -> float:
    """매크로 실행 시간을 계산합니다 (초 단위)"""
    macros = load_macro_file(file_key)
    steps = macros.get(macro_name)
    if not steps:
        return 0.0
    
    total_ms = 0
    for step in steps:
        delay_ms = int(step.get("delay_ms", 200)) if str(step.get("delay_ms", "")).isdigit() else 200
        total_ms += delay_ms
    
    return total_ms / 1000.0  # 밀리초를 초로 변환


def load_macro_file(file_key: str) -> Dict[str, Any]:
    """특정 매크로 파일을 로드합니다 (캐싱 지원)"""
    path = MACRO_FILES.get(file_key)
    if not path:
        return {}
    
    with _macro_file_lock:
        try:
            mtime = os.path.getmtime(path)
        except FileNotFoundError:
            if file_key not in _macro_file_cache:
                print(f"⚠️ {path} 파일을 찾을 수 없습니다.")
            _macro_file_cache[file_key] = {}
            _macro_file_mtime[file_key] = None
            return _macro_file_cache[file_key]
        except Exception as e:
            print(f"✗ {path} 상태 확인 실패: {e}")
            _macro_file_cache[file_key] = {}
            _macro_file_mtime[file_key] = None
            return _macro_file_cache[file_key]

        if file_key in _macro_file_cache and _macro_file_mtime.get(file_key) == mtime:
            return _macro_file_cache[file_key]

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                macros = data.get("macros", {})
                if not isinstance(macros, dict):
                    macros = {}
                _macro_file_cache[file_key] = macros
                _macro_file_mtime[file_key] = mtime
                print(f"✓ {os.path.basename(path)} 로드 완료: {len(macros)}개 매크로")
                return macros
        except Exception as e:
            print(f"✗ {path} 로드 실패: {e}")
            _macro_file_cache[file_key] = {}
            _macro_file_mtime[file_key] = None
            return _macro_file_cache[file_key]


def _run_macro_steps_with_error_handling(steps: List[Dict[str, Any]]) -> bool:
    """매크로 스텝을 실행합니다 (에러 핸들링 포함)"""
    global _global_port_error_shown
    if not isinstance(steps, list) or not steps:
        print("✗ 매크로 스텝이 비어있거나 유효하지 않습니다")
        return False
    if _send_command is None:
        print("✗ 시리얼 제어 모듈(_send_command) 미준비")
        return False
    
    # 포트 연결 상태 추적
    port_was_disconnected = False
    
    for idx, step in enumerate(steps):
        try:
            motor_id = resolve_motor_id(step.get("motor_id"))
            position = int(step.get("position"))
            speed_raw = step.get("speed", 0)
            speed = int(speed_raw) if str(speed_raw).lstrip("-").isdigit() else 0
            delay_raw = step.get("delay_ms", 200)
            delay_ms = int(delay_raw) if str(delay_raw).lstrip("-").isdigit() else 200
        except Exception as e:
            print(f"✗ 매크로 스텝 {idx+1}/{len(steps)} 파싱 실패: {e}")
            print(f"  스텝 데이터: {step}")
            continue
        
        # 명령 전송 시도 (매 스텝마다 포트 연결 재시도)
        try:
            _send_command(motor_id, position, speed)
            # 포트가 이전에 끊겼다가 다시 연결된 경우
            if port_was_disconnected:
                print(f"✓ 시리얼 포트 연결 성공 - 정상 동작 재개")
                port_was_disconnected = False
        except RuntimeError as e:
            # 시리얼 포트 연결 실패
            error_msg = str(e)
            if ("시리얼 포트" in error_msg or "serial" in error_msg.lower()):
                with _port_error_lock:
                    if not _global_port_error_shown:
                        print(f"⚠️ 시리얼 포트 연결 실패: {error_msg}")
                        print(f"  → 포트 연결 없이 시뮬레이션 모드로 진행합니다 (로봇은 움직이지 않습니다)")
                        print(f"  → 포트를 연결하면 자동으로 정상 동작을 재개합니다")
                        _global_port_error_shown = True
                port_was_disconnected = True
            else:
                # 기타 예외는 한 번만 출력
                with _port_error_lock:
                    if not _global_port_error_shown:
                        print(f"✗ 매크로 스텝 {idx+1}/{len(steps)} 전송 실패: {type(e).__name__}: {e}")
                        _global_port_error_shown = True
        
        # delay는 항상 실행 (시뮬레이션 모드에서도 시간 흐름 유지)
        time.sleep(max(0, delay_ms) / 1000.0)
    
    # 포트 연결 실패했어도 매크로는 "성공"으로 처리 (시뮬레이션 모드)
    return True


def trigger_macro(file_key: str, macro_name: str) -> bool:
    """특정 매크로 파일에서 매크로를 실행합니다"""
    macros = load_macro_file(file_key)
    if not macros:
        print(f"⚠️ 매크로 파일 '{file_key}'를 로드할 수 없거나 비어있습니다.")
        print(f"  → MACRO_FILES에 '{file_key}' 키가 있는지 확인하세요.")
        return False
    
    steps = macros.get(macro_name)
    if not steps:
        print(f"⚠️ {file_key}에 '{macro_name}' 매크로가 없습니다.")
        print(f"  → 사용 가능한 매크로: {list(macros.keys())}")
        return False

    def _runner():
        success = _run_macro_steps_with_error_handling(steps)
        if success:
            print(f"→ {file_key} 매크로('{macro_name}') 실행 완료")
        else:
            print(f"✗ {file_key} 매크로('{macro_name}') 실행 실패")

    threading.Thread(target=_runner, daemon=True).start()
    return True


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


