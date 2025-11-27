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
from macros_executor import trigger_macro
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
        "runners": {"first": "", "second": "", "third": ""},
        "batter": {"name": "", "active": False},
        "fielders": {
            "p": {"active": True, "name": ""},
            "c": {"active": True, "name": ""},
            "1b": {"active": True, "name": ""},
            "2b": {"active": True, "name": ""},
            "3b": {"active": True, "name": ""},
            "ss": {"active": True, "name": ""},
            "lf": {"active": True, "name": ""},
            "cf": {"active": True, "name": ""},
            "rf": {"active": True, "name": ""},
        },
        "last_event": {"type": "start", "description": "경기 시작"},
    }


game_state: Dict[str, Any] = _initial_game_state()


DEMO_MACRO_MAP = {
    "차렷자세": ("차렷자세", "차렷자세"),  # hold.json
    "김지찬 응원가": ("김지찬 응원가", "김지찬 응원가"),  # kimjichan.json
    "아웃(삐끼삐끼)": ("아웃(삐끼삐끼)", "아웃(삐끼삐끼)"),  # out.json
    "김도영 응원가가": ("김도영 응원가", "김도영 응원가"),  # kimdoyoung.json
    "홈런": ("홈런", "홈런"),  # homerun.json
    "최강기아": ("외쳐라 최강기아", "최강기아"),  # kia.json
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
        "fielders": {
            "p": {"active": True, "name": "양현종"},
            "c": {"active": True, "name": "김태군"},
            "1b": {"active": True, "name": "김석환"},
            "2b": {"active": True, "name": "김선빈"},
            "3b": {"active": True, "name": "김도영"},
            "ss": {"active": True, "name": "박찬호"},
            "lf": {"active": True, "name": "김호령"},
            "cf": {"active": True, "name": "최형우"},
            "rf": {"active": True, "name": "소크라테스"},
        },
    },
    {
        "delay": 3,
        "description": "경기 시작 삼성 공격 기아 수비",
        "event_type": "start",
    },
    {
        "delay": 3,
        "description": "김지찬 타석 입장",
        "event_type": "live",
        "batter": {"name": "김지찬", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
    },
    {
        "delay": 0,
        "description": "김지찬 응원가",
        "event_type": "chant",
        "macro": "김지찬 응원가",
        "batter": {"name": "김지찬", "active": True},
    },
    {
        "delay": 10,
        "description": "응원 종료 후 잠시 휴식",
        "event_type": "info",
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 0, "outs": 0},
        "batter": {"name": "김지찬", "active": True},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 1, "strikes": 1, "outs": 0},
        "batter": {"name": "김지찬", "active": True},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 2, "strikes": 1, "outs": 0},
        "batter": {"name": "김지찬", "active": True},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 2, "strikes": 2, "outs": 0},
        "batter": {"name": "김지찬", "active": True},
    },
    {
        "delay": 2,
        "description": "김지찬, 삼진 아웃",
        "event_type": "strikeout",
        "count": {"balls": 2, "strikes": 2, "outs": 1},
        "batter": {"name": "", "active": False},
        "runners": {"first": "", "second": "", "third": ""},
    },
    {
        "delay": 0,
        "description": "삐끼삐끼 동작",
        "event_type": "info",
        "macro": "아웃(삐끼삐끼)",
    },
    {
        "delay": 3,
        "description": "구자욱 타석 입장",
        "event_type": "live",
        "batter": {"name": "구자욱", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 1},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 0, "strikes": 1, "outs": 1},
        "batter": {"name": "구자욱", "active": True},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 1, "outs": 1},
        "batter": {"name": "구자욱", "active": True},
    },
    {
        "delay": 2,
        "description": "구자욱, 우중간 안타로 1루에 출루",
        "event_type": "single",
        "count": {"balls": 1, "strikes": 1, "outs": 1},
        "bases": {"first": True, "second": False, "third": False},
        "batter": {"name": "", "active": False},
        "runners": {"first": "구자욱", "second": "", "third": ""},
        "hits_delta": {"away": 1},
    },
    {
        "delay": 3,
        "description": "오재일 타석 입장",
        "event_type": "live",
        "batter": {"name": "오재일", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 1},
        "bases": {"first": True, "second": False, "third": False},
        "runners": {"first": "구자욱", "second": "", "third": ""},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 0, "outs": 1},
        "batter": {"name": "오재일", "active": True},
        "bases": {"first": True, "second": False, "third": False},
        "runners": {"first": "구자욱", "second": "", "third": ""},
    },
    {
        "delay": 2,
        "description": "오재일, 플라이 아웃",
        "event_type": "out",
        "count": {"balls": 1, "strikes": 0, "outs": 2},
        "bases": {"first": True, "second": False, "third": False},
        "batter": {"name": "", "active": False},
        "runners": {"first": "구자욱", "second": "", "third": ""},
    },
    {
        "delay": 3,
        "description": "이닝 종료",
        "event_type": "change",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
    },
    {
        "delay": 3,
        "description": "공수 교대 기아 공격 삼성 수비",
        "event_type": "change",
        "half": "B",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
        "fielders": {
            "p": {"active": True, "name": "원태인"},
            "c": {"active": True, "name": "강민호"},
            "1b": {"active": True, "name": "오재일"},
            "2b": {"active": True, "name": "김지찬"},
            "3b": {"active": True, "name": "이원석"},
            "ss": {"active": True, "name": "이재현"},
            "lf": {"active": True, "name": "김헌곤"},
            "cf": {"active": True, "name": "구자욱"},
            "rf": {"active": True, "name": "박해민"},
        },
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
        "batter": {"name": "김도영", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
    },
    {
        "delay": 0,
        "description": "김도영 응원가",
        "event_type": "chant",
        "macro": "김도영 응원가가",
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 10,
        "description": "응원 종료",
        "event_type": "info",
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 0, "strikes": 1, "outs": 0},
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 1, "outs": 0},
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 2, "strikes": 1, "outs": 0},
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 2, "strikes": 2, "outs": 0},
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 2,
        "description": "김도영 좌중월 솔로 홈런!",
        "event_type": "hr",
        "score_delta": {"home": 1},
        "hits_delta": {"home": 1},
        "bases": {"first": False, "second": False, "third": False},
        "count": {"balls": 2, "strikes": 2, "outs": 0},
        "batter": {"name": "", "active": False},
        "runners": {"first": "", "second": "", "third": ""},
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
        "description": "최형우 타석 입장",
        "event_type": "live",
        "batter": {"name": "최형우", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 0, "outs": 0},
        "batter": {"name": "최형우", "active": True},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 1, "strikes": 1, "outs": 0},
        "batter": {"name": "최형우", "active": True},
    },
    {
        "delay": 2,
        "description": "스트라이크",
        "event_type": "strike",
        "count": {"balls": 1, "strikes": 2, "outs": 0},
        "batter": {"name": "최형우", "active": True},
    },
    {
        "delay": 2,
        "description": "최형우, 중전 안타로 1루에 출루",
        "event_type": "single",
        "count": {"balls": 1, "strikes": 2, "outs": 0},
        "bases": {"first": True, "second": False, "third": False},
        "batter": {"name": "", "active": False},
        "runners": {"first": "최형우", "second": "", "third": ""},
        "hits_delta": {"home": 1},
    },
    {
        "delay": 3,
        "description": "박찬호 타석 입장",
        "event_type": "live",
        "batter": {"name": "박찬호", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": True, "second": False, "third": False},
        "runners": {"first": "최형우", "second": "", "third": ""},
    },
    {
        "delay": 2,
        "description": "볼",
        "event_type": "ball",
        "count": {"balls": 1, "strikes": 0, "outs": 0},
        "batter": {"name": "박찬호", "active": True},
        "bases": {"first": True, "second": False, "third": False},
        "runners": {"first": "최형우", "second": "", "third": ""},
    },
    {
        "delay": 2,
        "description": "박찬호, 번트로 아웃, 주자는 2루로 진루",
        "event_type": "out",
        "count": {"balls": 1, "strikes": 0, "outs": 1},
        "bases": {"first": False, "second": True, "third": False},
        "batter": {"name": "", "active": False},
        "runners": {"first": "", "second": "최형우", "third": ""},
    },
    {
        "delay": 3,
        "description": "이닝 종료",
        "event_type": "change",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
    },
    {
        "delay": 0,
        "description": "기아 우승! 열광하라",
        "event_type": "info",
        "macro": "최강기아",
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
        "popup_description": "🏆 KIA 타이거즈 우승 🏆",
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
        self._paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self.current_step: Optional[str] = None
        self._current_step_index = 0  # 현재 실행 중인 스텝 인덱스

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self, resume: bool = False) -> bool:
        if self._running and not self._paused:
            return False
        if resume and self._paused:
            # 재시작: 멈춘 지점부터 계속
            self._pause_event.set()
            self._paused = False
            return True
        # 처음 시작: 처음부터
        if self._running:
            self.stop()
        self._stop_event.clear()
        self._pause_event.clear()
        self._current_step_index = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        self._paused = False
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        self._pause_event.set()  # 일시정지 상태도 해제
        if self._thread:
            self._thread.join(timeout=1)
        self._running = False
        self._paused = False

    def pause(self) -> None:
        """데모를 일시정지합니다 (멈춘 지점부터 재시작 가능)"""
        if not self._running or self._paused:
            return
        self._paused = True
        self._pause_event.clear()

    def resume(self) -> bool:
        """일시정지된 데모를 재시작합니다"""
        if not self._paused:
            return False
        self._pause_event.set()
        self._paused = False
        return True

    def _run(self) -> None:
        global game_state
        try:
            # 처음 시작할 때만 게임 상태 초기화
            if self._current_step_index == 0:
                with lock:
                    game_state = _initial_game_state()
                    game_state["teams"]["home"]["name"] = "기아"
                    game_state["teams"]["away"]["name"] = "삼성"
            
            # 현재 스텝 인덱스부터 실행
            for i in range(self._current_step_index, len(DEMO_SCENARIO_STEPS)):
                if self._stop_event.is_set():
                    break
                
                # 일시정지 대기
                if self._paused:
                    self._pause_event.wait()
                    if self._stop_event.is_set():
                        break
                
                step = DEMO_SCENARIO_STEPS[i]
                self._current_step_index = i
                self.current_step = step.get("description")
                
                delay = float(step.get("delay", 0))
                if delay > 0:
                    waited = 0.0
                    while waited < delay and not self._stop_event.is_set():
                        # 일시정지 체크
                        if self._paused:
                            self._pause_event.wait()
                            if self._stop_event.is_set():
                                break
                        chunk = min(0.5, delay - waited)
                        time.sleep(chunk)
                        waited += chunk
                
                if self._stop_event.is_set():
                    break
                
                # 일시정지 체크
                if self._paused:
                    self._pause_event.wait()
                    if self._stop_event.is_set():
                        break
                
                self._apply_step(step)
            
            # 데모 완료
            self.current_step = None
            self._current_step_index = 0
        finally:
            self._running = False
            self._paused = False
            self._stop_event.clear()
            self._pause_event.clear()

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
                # runners 정보도 함께 업데이트 (선택적)
                if "runners" in step:
                    if "runners" not in state:
                        state["runners"] = {"first": "", "second": "", "third": ""}
                    state["runners"].update(step["runners"])

            if "batter" in step:
                if "batter" not in state:
                    state["batter"] = {"name": "", "active": False}
                state["batter"].update(step["batter"])

            if "fielders" in step:
                state["fielders"].update(step["fielders"])

            # 경기 관련 이벤트만 last_event 업데이트 (UI에 표시)
            # 응원가(chant), 휴식(info), 삐끼삐끼(info), 기본 자세 복귀(info), 홈런 동작(info) 등은 내부 처리만 하고 UI에 표시 안 함
            event_type = step.get("event_type", "live")
            GAME_RELATED_EVENTS = {"start", "live", "strikeout", "hr", "single", "double", "triple", "out", "sac_fly", "walk", "error", "change", "end", "ball", "strike"}
            
            if event_type in GAME_RELATED_EVENTS:
                # popup_description이 명시적으로 있으면 사용, 없으면 None
                popup_desc = step.get("popup_description")
                state["last_event"] = {
                    "type": event_type,
                    "description": step.get("description", ""),
                    "popup_description": popup_desc if popup_desc is not None else None,
                }
            # 응원가, 휴식 등은 last_event를 업데이트하지 않음 (이전 경기 이벤트 유지)

        macro_name = step.get("macro")
        if macro_name:
            file_key, macro_key = DEMO_MACRO_MAP.get(macro_name, (None, None))
            if file_key and macro_key:
                try:
                    success = trigger_macro(file_key, macro_key)
                    if not success:
                        print(f"⚠️ 데모 매크로 '{file_key}:{macro_key}' 실행 실패")
                        print(f"  → 매크로 파일 '{file_key}' 또는 매크로 이름 '{macro_key}' 확인 필요")
                except Exception as e:
                    print(f"✗ 데모 매크로 '{file_key}:{macro_key}' 실행 중 예외 발생: {type(e).__name__}: {e}")
            else:
                print(f"⚠️ 데모 매크로 매핑 없음: '{macro_name}'")
                print(f"  → DEMO_MACRO_MAP에 '{macro_name}' 키가 없습니다")


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
        response["runners"] = dict(game_state.get("runners", {"first": "", "second": "", "third": ""}))
        response["batter"] = dict(game_state.get("batter", {"name": "", "active": False}))
        response["fielders"] = {k: dict(v) for k, v in game_state.get("fielders", {}).items()}
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
    data = request.get_json(silent=True) or {}
    resume = data.get("resume", False)
    if demo_runner.start(resume=resume):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_running"}), 409


@game_bp.route("/api/demo/stop", methods=["POST"])
def api_demo_stop():
    demo_runner.stop()
    return jsonify({"ok": True})


@game_bp.route("/api/demo/pause", methods=["POST"])
def api_demo_pause():
    demo_runner.pause()
    return jsonify({"ok": True})


@game_bp.route("/api/demo/resume", methods=["POST"])
def api_demo_resume():
    if demo_runner.resume():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "not_paused"}), 409


@game_bp.route("/api/demo/status")
def api_demo_status():
    return jsonify({
        "ok": True,
        "running": demo_runner.is_running,
        "paused": demo_runner.is_paused,
        "step": demo_runner.current_step
    })


@game_bp.route("/api/config")
def api_config():
    """클라이언트에서 사용할 설정값을 반환합니다."""
    return jsonify({"ok": True, "gameId": BASEBALL_ID or ""})


