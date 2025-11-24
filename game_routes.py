from __future__ import annotations

import random
import threading
from typing import Dict, Any

from flask import Blueprint, jsonify, render_template, request
from macros_executor import run_macro_by_event_text_async, last_event_to_trigger_text
from config import BASEBALL_ID, GAME_MODE, SCRIPT_ID
from scripted_game import get_scripted_game, ScriptedGame


game_bp = Blueprint("game", __name__)

lock = threading.Lock()


def _initial_game_state() -> Dict[str, Any]:
    return {
        "teams": {
            "away": {"name": "AWAY", "runs": 0, "hits": 0, "errors": 0},
            "home": {"name": "HOME", "runs": 0, "hits": 0, "errors": 0},
        },
        "inning": 1,
        "half": "T",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
        "last_event": {"type": "start", "description": "경기 시작"},
    }


game_state: Dict[str, Any] = _initial_game_state()

def _resolve_game_mode() -> str:
    mode = (GAME_MODE or "auto").strip().lower()
    if mode in ("auto", "", None):
        if SCRIPT_ID:
            return "script"
        if BASEBALL_ID:
            return "daum"
        return "random"
    return mode


ACTIVE_GAME_MODE = _resolve_game_mode()

scripted_game: ScriptedGame | None = None
scripted_game_error: str | None = None
if ACTIVE_GAME_MODE == "script":
    try:
        scripted_game = get_scripted_game(SCRIPT_ID)
    except Exception as exc:  # pragma: no cover - config error visibility
        scripted_game_error = str(exc)


def _advance_random_event(state: Dict[str, Any]) -> None:
    if state["count"]["outs"] >= 3:
        state["count"] = {"balls": 0, "strikes": 0, "outs": 0}
        state["bases"] = {"first": False, "second": False, "third": False}
        if state["half"] == "T":
            state["half"] = "B"
        else:
            state["half"] = "T"
            state["inning"] += 1
        state["last_event"] = {"type": "change", "description": "이닝 전환"}
        return

    event = random.choices(
        population=["pitch", "ball", "strike", "out", "single", "double", "triple", "hr", "walk", "error"],
        weights=[20, 10, 10, 8, 12, 7, 3, 4, 10, 6],
        k=1,
    )[0]

    batting = "away" if state["half"] == "T" else "home"

    def clear_count():
        state["count"]["balls"] = 0
        state["count"]["strikes"] = 0

    if event == "pitch":
        state["last_event"] = {"type": "pitch", "description": "투구"}
        return

    if event == "ball":
        state["count"]["balls"] = min(3, state["count"]["balls"] + 1)
        state["last_event"] = {"type": "ball", "description": "볼"}
        if state["count"]["balls"] >= 4:
            clear_count()
            state["last_event"] = {"type": "walk", "description": "볼넷"}
            _advance_runners(state, bases_to_advance=1, batting=batting)
        return

    if event == "strike":
        state["count"]["strikes"] = min(2, state["count"]["strikes"] + 1)
        state["last_event"] = {"type": "strike", "description": "스트라이크"}
        if state["count"]["strikes"] >= 3:
            clear_count()
            state["count"]["outs"] += 1
            state["last_event"] = {"type": "strikeout", "description": "삼진 아웃"}
        return

    if event == "out":
        clear_count()
        state["count"]["outs"] += 1
        state["last_event"] = {"type": "out", "description": "타구 아웃"}
        return

    if event == "single":
        clear_count()
        state["teams"][batting]["hits"] += 1
        _advance_runners(state, 1, batting)
        state["last_event"] = {"type": "single", "description": "안타(1루타)"}
        return

    if event == "double":
        clear_count()
        state["teams"][batting]["hits"] += 1
        _advance_runners(state, 2, batting)
        state["last_event"] = {"type": "double", "description": "2루타"}
        return

    if event == "triple":
        clear_count()
        state["teams"][batting]["hits"] += 1
        _advance_runners(state, 3, batting)
        state["last_event"] = {"type": "triple", "description": "3루타"}
        return

    if event == "hr":
        clear_count()
        state["teams"][batting]["hits"] += 1
        _advance_runners(state, 4, batting)
        state["last_event"] = {"type": "hr", "description": "홈런"}
        return

    if event == "error":
        clear_count()
        state["teams"]["home" if batting == "away" else "away"]["errors"] += 1
        _advance_runners(state, random.choice([1, 2]), batting)
        state["last_event"] = {"type": "error", "description": "수비 실책으로 진루"}
        return


def _advance_runners(state: Dict[str, Any], bases_to_advance: int, batting: str) -> None:
    bases = state["bases"]

    def score_run():
        state["teams"][batting]["runs"] += 1

    for _ in range(bases_to_advance):
        if bases["third"]:
            score_run()
            bases["third"] = False
        if bases["second"]:
            bases["third"] = True
            bases["second"] = False
        if bases["first"]:
            bases["second"] = True
            bases["first"] = False

        if bases_to_advance >= 4:
            score_run()
        else:
            target = "first" if not bases["first"] else (
                "second" if not bases["second"] else (
                    "third" if not bases["third"] else None
                )
            )
            if target is None:
                score_run()
            else:
                bases[target] = True


def _snapshot_state(state: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(state)
    result["teams"] = {k: dict(v) for k, v in state.get("teams", {}).items()}
    result["count"] = dict(state.get("count", {}))
    result["bases"] = dict(state.get("bases", {}))
    last_event = state.get("last_event")
    result["last_event"] = dict(last_event) if isinstance(last_event, dict) else (last_event or None)
    fielders = state.get("fielders")
    if isinstance(fielders, dict):
        result["fielders"] = {k: dict(v) for k, v in fielders.items()}
    return result


@game_bp.route("/")
def index():
    return render_template("game.html")


@game_bp.route("/api/game-state")
def api_game_state():
    global game_state
    should_advance = request.args.get("advance", "0") == "1"
    with lock:
        if should_advance:
            _advance_random_event(game_state)
        response = _snapshot_state(game_state)

    # 락 밖에서 비동기 매크로 트리거 (락 홀드 시간 최소화)
    trigger_text = last_event_to_trigger_text(response.get("last_event"))
    if trigger_text:
        run_macro_by_event_text_async(trigger_text)

    return jsonify(response)


@game_bp.route("/api/reset", methods=["POST"])
def api_reset():
    global game_state
    with lock:
        game_state = _initial_game_state()
    return jsonify({"ok": True})


@game_bp.route("/api/scripted-state")
def api_scripted_state():
    if scripted_game is None:
        return jsonify({"error": "script_mode_disabled", "detail": scripted_game_error}), 400
    state = scripted_game.current_state()
    trigger_text = last_event_to_trigger_text(state.get("last_event"))
    if trigger_text:
        run_macro_by_event_text_async(trigger_text)
    return jsonify(state)


@game_bp.route("/api/scripted/reset", methods=["POST"])
def api_scripted_reset():
    if scripted_game is None:
        return jsonify({"error": "script_mode_disabled", "detail": scripted_game_error}), 400
    scripted_game.reset()
    return jsonify({"ok": True})


@game_bp.route("/api/config")
def api_config():
    """클라이언트에서 사용할 설정값을 반환합니다."""
    game_id = "" if ACTIVE_GAME_MODE == "script" else (BASEBALL_ID or "")
    config_payload = {
        "ok": True,
        "gameId": game_id,
        "mode": ACTIVE_GAME_MODE,
        "scriptId": SCRIPT_ID if ACTIVE_GAME_MODE == "script" else "",
        "scriptError": scripted_game_error if ACTIVE_GAME_MODE == "script" else "",
    }
    return jsonify(config_payload)


def get_current_state_snapshot() -> Dict[str, Any]:
    """Voice/other modules에서 현재 경기 상황을 참조할 수 있도록 상태를 제공합니다."""
    if ACTIVE_GAME_MODE == "script" and scripted_game is not None:
        try:
            return scripted_game.current_state()
        except Exception:
            return {}
    with lock:
        return _snapshot_state(game_state)


