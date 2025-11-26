from __future__ import annotations

import random
import threading
import time
from typing import Dict, Any, Optional

from flask import Blueprint, jsonify, render_template, request
from macros_executor import (
    run_macro_by_event_text_async,
    last_event_to_trigger_text,
    run_macro_by_name_async,
)
from voice import trigger_macro  # reuse macro loader
from config import BASEBALL_ID


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


DEMO_MACRO_MAP = {
    "차렷자세": ("차렷자세", "차렷자세"),  # hold.json
    "김지찬 응원가": ("김지찬 응원가", "김지찬 응원가"),  # kimjichan.json
    "아웃(삐끼삐끼)": ("아웃(삐끼삐끼)", "아웃(삐끼삐끼)"),  # out.json
    "최강기아 1125": ("김도영 응원가", "김도영 응원가"),  # kimdoyoung.json
    "홈런": ("홈런", "홈런"),  # homerun.json
    "최강기아 + 만세 1125": ("외쳐라 최강기아", "최강기아 + 만세 1125"),  # kia.json
}


DEMO_SCENARIO_STEPS = [
    {
        "delay": 0,
        "description": "데모 시나리오 시작 – 기본 자세",
        "event_type": "info",
        "macro": "차렷자세",
        "set_teams": {"home": "기아", "away": "삼성"},
        "set_scores": {"home": 0, "away": 0},
        "set_hits": {"home": 0, "away": 0},
        "set_errors": {"home": 0, "away": 0},
        "inning": 1,
        "half": "T",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
    },
    {
        "delay": 3,
        "description": "경기 시작",
        "event_type": "start",
    },
    {
        "delay": 3,
        "description": "상대팀 김지찬 타석 입장",
        "event_type": "live",
    },
    {
        "delay": 0,
        "description": "김지찬 응원가",
        "event_type": "chant",
        "macro": "김지찬 응원가",
        "popup_description": "김지찬 타석 입장",
    },
    {
        "delay": 10,
        "description": "응원 종료 후 잠시 휴식",
        "event_type": "info",
    },
    {
        "delay": 2,
        "description": "김지찬 삼진 아웃",
        "event_type": "strikeout",
        "count": {"balls": 0, "strikes": 0, "outs": 1},
    },
    {
        "delay": 0,
        "description": "삐끼삐끼 동작",
        "event_type": "info",
        "macro": "아웃(삐끼삐끼)",
    },
    {
        "delay": 10,
        "description": "아웃 연출 유지",
        "event_type": "info",
    },
    {
        "delay": 3,
        "description": "공수 교대 → KIA 공격",
        "event_type": "change",
        "half": "B",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
    },
    {
        "delay": 0,
        "description": "기본 자세 복귀",
        "event_type": "info",
        "macro": "차렷자세",
    },
    {
        "delay": 3,
        "description": "김도영 타석 입장",
        "event_type": "live",
    },
    {
        "delay": 0,
        "description": "김도영 응원가",
        "event_type": "chant",
        "macro": "최강기아 1125",
        "popup_description": "김도영 타석 입장",
    },
    {
        "delay": 10,
        "description": "응원 종료",
        "event_type": "info",
    },
    {
        "delay": 2,
        "description": "김도영 좌중월 솔로 홈런!",
        "event_type": "hr",
        "score_delta": {"home": 1},
        "hits_delta": {"home": 1},
        "bases": {"first": False, "second": False, "third": False},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
    },
    {
        "delay": 0,
        "description": "홈런 동작",
        "event_type": "info",
        "macro": "홈런",
    },
    {
        "delay": 5,
        "description": "홈런 연출 유지",
        "event_type": "info",
    },
    {
        "delay": 2,
        "description": "정적",
        "event_type": "info",
    },
    {
        "delay": 0,
        "description": "기아 우승! 열광하라",
        "event_type": "live",
        "macro": "최강기아 + 만세 1125",
        "popup_description": "기아 우승 세리머니",
    },
    {
        "delay": 10,
        "description": "열광 연출 유지",
        "event_type": "info",
    },
    {
        "delay": 0,
        "description": "경기 종료 – KIA 승리",
        "event_type": "end",
        "set_scores": {"home": 1, "away": 0},
        "half": "F",
    },
    {
        "delay": 0,
        "description": "기본 자세 복귀",
        "event_type": "info",
        "macro": "차렷자세",
    },
]


class DemoScenarioRunner:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        self.current_step: Optional[str] = None

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        if self._running:
            return False
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        global game_state
        try:
            with lock:
                game_state = _initial_game_state()
                game_state["teams"]["home"]["name"] = "기아"
                game_state["teams"]["away"]["name"] = "삼성"
            for step in DEMO_SCENARIO_STEPS:
                if self._stop_event.is_set():
                    break
                self.current_step = step.get("description")
                delay = float(step.get("delay", 0))
                if delay > 0:
                    waited = 0.0
                    while waited < delay and not self._stop_event.is_set():
                        chunk = min(0.5, delay - waited)
                        time.sleep(chunk)
                        waited += chunk
                if self._stop_event.is_set():
                    break
                self._apply_step(step)
            self.current_step = None
        finally:
            self._running = False
            self._stop_event.clear()

    def _apply_step(self, step: Dict[str, Any]) -> None:
        global game_state
        with lock:
            state = game_state
            teams = state["teams"]

            team_names = step.get("set_teams")
            if team_names:
                if "home" in team_names:
                    teams["home"]["name"] = team_names["home"]
                if "away" in team_names:
                    teams["away"]["name"] = team_names["away"]

            if "set_scores" in step:
                for side, value in step["set_scores"].items():
                    if side in teams:
                        teams[side]["runs"] = max(0, int(value))

            if "set_hits" in step:
                for side, value in step["set_hits"].items():
                    if side in teams:
                        teams[side]["hits"] = max(0, int(value))

            if "set_errors" in step:
                for side, value in step["set_errors"].items():
                    if side in teams:
                        teams[side]["errors"] = max(0, int(value))

            if "score_delta" in step:
                for side, delta in step["score_delta"].items():
                    if side in teams:
                        teams[side]["runs"] = max(0, teams[side]["runs"] + int(delta))

            if "hits_delta" in step:
                for side, delta in step["hits_delta"].items():
                    if side in teams:
                        teams[side]["hits"] = max(0, teams[side]["hits"] + int(delta))

            if "errors_delta" in step:
                for side, delta in step["errors_delta"].items():
                    if side in teams:
                        teams[side]["errors"] = max(0, teams[side]["errors"] + int(delta))

            if "inning" in step:
                state["inning"] = int(step["inning"])

            if "half" in step:
                state["half"] = step["half"]

            if "count" in step:
                state["count"].update(step["count"])

            if "bases" in step:
                state["bases"].update(step["bases"])

            state["last_event"] = {
                "type": step.get("event_type", "live"),
                "description": step.get("popup_description", step.get("description", "")),
            }

        macro_name = step.get("macro")
        if macro_name:
            file_key, macro_key = DEMO_MACRO_MAP.get(macro_name, (None, None))
            if file_key and macro_key:
                success = trigger_macro(file_key, macro_key)
                if not success:
                    print(f"⚠️ 데모 매크로 '{file_key}:{macro_key}' 실행 실패")
            else:
                print(f"⚠️ 데모 매크로 매핑 없음: {macro_name}")


demo_runner = DemoScenarioRunner()


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


@game_bp.route("/")
def index():
    return render_template("game.html")


@game_bp.route("/api/game-state")
def api_game_state():
    global game_state
    should_advance = request.args.get("advance", "0") == "1"
    demo_active = demo_runner.is_running
    with lock:
        if should_advance and not demo_active:
            _advance_random_event(game_state)
        # 응답 복제
        response = dict(game_state)
        response["teams"] = {k: dict(v) for k, v in game_state["teams"].items()}
        response["count"] = dict(game_state["count"])
        response["bases"] = dict(game_state["bases"])
        response["last_event"] = dict(game_state["last_event"]) if game_state.get("last_event") else None
    response["demo_active"] = demo_active
    response["demo_step"] = demo_runner.current_step

    # 락 밖에서 비동기 매크로 트리거 (락 홀드 시간 최소화)
    trigger_text = last_event_to_trigger_text(response.get("last_event"))
    if trigger_text and not demo_active:
        run_macro_by_event_text_async(trigger_text)

    return jsonify(response)


@game_bp.route("/api/reset", methods=["POST"])
def api_reset():
    global game_state
    with lock:
        game_state = _initial_game_state()
    return jsonify({"ok": True})


@game_bp.route("/api/demo/start", methods=["POST"])
def api_demo_start():
    if demo_runner.start():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_running"}), 409


@game_bp.route("/api/demo/status")
def api_demo_status():
    return jsonify({"ok": True, "running": demo_runner.is_running, "step": demo_runner.current_step})


@game_bp.route("/api/config")
def api_config():
    """클라이언트에서 사용할 설정값을 반환합니다."""
    return jsonify({"ok": True, "gameId": BASEBALL_ID or ""})


