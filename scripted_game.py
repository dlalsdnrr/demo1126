from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

try:
    from macros_executor import run_macro_by_name_async
except Exception:  # pragma: no cover - macro system optional during tests
    def run_macro_by_name_async(_name: str) -> bool:
        return False


State = Dict[str, Any]
ApplyFn = Callable[[State], None]


@dataclass(frozen=True)
class ScriptStep:
    at: float
    description: str
    type: str = "script"
    apply: Optional[ApplyFn] = None


class ScriptedGame:
    """Plays back a predefined sequence of baseball events over time."""

    def __init__(self, steps: List[ScriptStep], base_state_factory: Callable[[], State]):
        if not steps:
            raise ValueError("ScriptedGame requires at least one step")
        self._steps = sorted(steps, key=lambda step: step.at)
        self._base_state_factory = base_state_factory
        self._state: State = {}
        self._start_time: float = 0.0
        self._cursor: int = -1
        self.reset()

    def reset(self) -> None:
        """Restart the script from the beginning."""
        self._state = self._base_state_factory()
        self._start_time = time.monotonic()
        self._cursor = -1
        # Apply any steps scheduled for t=0 immediately.
        self._apply_until_elapsed(0.0)

    def _apply_step(self, step: ScriptStep) -> None:
        if step.apply:
            step.apply(self._state)
        if step.description:
            self._state["last_event"] = {
                "type": step.type,
                "description": step.description,
            }

    def _apply_until_elapsed(self, elapsed: float) -> None:
        while self._cursor + 1 < len(self._steps) and self._steps[self._cursor + 1].at <= elapsed:
            self._cursor += 1
            self._apply_step(self._steps[self._cursor])

    def current_state(self) -> State:
        """Return the latest state snapshot for the current playback time."""
        elapsed = time.monotonic() - self._start_time
        self._apply_until_elapsed(elapsed)
        return deepcopy(self._state)


def _blank_state() -> State:
    return {
        "teams": {
            "away": {"name": "삼성 라이온즈", "runs": 0, "hits": 0, "errors": 0},
            "home": {"name": "KIA 타이거즈", "runs": 0, "hits": 0, "errors": 0},
        },
        "inning": 1,
        "half": "T",
        "count": {"balls": 0, "strikes": 0, "outs": 0},
        "bases": {"first": False, "second": False, "third": False},
        "fielders": _kia_fielders(),
        "last_event": {"type": "start", "description": "광주, KIA vs 삼성 시연 시작"},
    }


def _kia_fielders() -> Dict[str, Dict[str, Any]]:
    return {
        "p": {"active": True, "name": "양현종"},
        "c": {"active": True, "name": "김태군"},
        "1b": {"active": True, "name": "김석환"},
        "2b": {"active": True, "name": "김선빈"},
        "3b": {"active": True, "name": "김도영"},
        "ss": {"active": True, "name": "박찬호"},
        "lf": {"active": True, "name": "김호령"},
        "cf": {"active": True, "name": "최형우"},
        "rf": {"active": True, "name": "소크라테스"},
    }


def _samsung_fielders() -> Dict[str, Dict[str, Any]]:
    return {
        "p": {"active": True, "name": "원태인"},
        "c": {"active": True, "name": "강민호"},
        "1b": {"active": True, "name": "오재일"},
        "2b": {"active": True, "name": "김지찬"},
        "3b": {"active": True, "name": "이원석"},
        "ss": {"active": True, "name": "이재현"},
        "lf": {"active": True, "name": "김헌곤"},
        "cf": {"active": True, "name": "구자욱"},
        "rf": {"active": True, "name": "박해민"},
    }


def _set_bases(state: State, first: Optional[bool] = None, second: Optional[bool] = None, third: Optional[bool] = None) -> None:
    bases = state["bases"]
    if first is not None:
        bases["first"] = bool(first)
    if second is not None:
        bases["second"] = bool(second)
    if third is not None:
        bases["third"] = bool(third)


def _reset_count(state: State) -> None:
    count = state["count"]
    count["balls"] = 0
    count["strikes"] = 0


def _set_outs(state: State, outs: int) -> None:
    state["count"]["outs"] = max(0, min(3, outs))


def _add_hit(state: State, team: str) -> None:
    state["teams"][team]["hits"] += 1


def _add_run(state: State, team: str, runs: int = 1) -> None:
    state["teams"][team]["runs"] += max(0, runs)


def _change_half(state: State) -> None:
    _reset_count(state)
    state["count"]["outs"] = 0
    _set_bases(state, first=False, second=False, third=False)
    if state["half"] == "T":
        state["half"] = "B"
    else:
        state["half"] = "T"
        state["inning"] += 1


def _set_fielders(state: State, fielders: Dict[str, Dict[str, Any]]) -> None:
    state["fielders"] = deepcopy(fielders)


def _trigger_macro(name: str) -> None:
    if not name:
        return
    try:
        run_macro_by_name_async(name)
    except Exception:
        pass


def _kia_vs_samsung_steps() -> List[ScriptStep]:
    steps: List[ScriptStep] = []

    def stage_reset(state: State) -> None:
        _reset_count(state)
        _set_outs(state, 0)
        _set_bases(state, first=False, second=False, third=False)
        _trigger_macro("차렷자세")

    steps.append(
        ScriptStep(
            at=0.0,
            type="intro",
            description="데모 준비",
            apply=stage_reset,
        )
    )

    def kim_jichan_entrance(_state: State) -> None:
        _trigger_macro("김지찬 응원가")

    steps.append(
        ScriptStep(
            at=3.0,
            type="entrance",
            description="김지찬 타석 입장, 삼성 팬들의 함성이 커집니다",
            apply=kim_jichan_entrance,
        )
    )

    def kim_jichan_patience(state: State) -> None:
        _reset_count(state)
        state["count"]["balls"] = 1
        state["count"]["strikes"] = 0

    steps.append(
        ScriptStep(
            at=6.0,
            type="ball",
            description="김지찬, 초구를 침착하게 지켜보며 볼을 골라냅니다",
            apply=kim_jichan_patience,
        )
    )

    def kim_jichan_aggressive(state: State) -> None:
        state["count"]["strikes"] = 1

    steps.append(
        ScriptStep(
            at=8.0,
            type="strike",
            description="김지찬, 빠른 스윙으로 파울! 스트라이크가 하나 쌓입니다",
            apply=kim_jichan_aggressive,
        )
    )

    def kim_jichan_single(state: State) -> None:
        _add_hit(state, "away")
        _reset_count(state)
        _set_bases(state, first=True, second=False, third=False)

    steps.append(
        ScriptStep(
            at=11.0,
            type="single",
            description="김지찬, 좌전 안타로 1루까지 시원하게 질주합니다",
            apply=kim_jichan_single,
        )
    )

    def kim_jichan_steal(state: State) -> None:
        _set_bases(state, first=False, second=True, third=False)

    steps.append(
        ScriptStep(
            at=14.0,
            type="steal",
            description="김지찬, 폭발적인 스타트로 2루 도루에 성공합니다",
            apply=kim_jichan_steal,
        )
    )

    def guja_wook_rbi(state: State) -> None:
        _add_hit(state, "away")
        _add_run(state, "away")
        _reset_count(state)
        _set_bases(state, first=True, second=False, third=False)

    steps.append(
        ScriptStep(
            at=18.0,
            type="single",
            description="구자욱, 우중간 적시타! 김지찬 홈 인으로 삼성 선취점",
            apply=guja_wook_rbi,
        )
    )

    def oh_jaeil_strike(state: State) -> None:
        state["count"]["strikes"] = min(2, state["count"]["strikes"] + 1)

    steps.append(
        ScriptStep(
            at=23.0,
            type="strike",
            description="오재일, 패스트볼에 헛스윙하며 스트라이크를 허용합니다",
            apply=oh_jaeil_strike,
        )
    )

    def oh_jaeil_fly(state: State) -> None:
        _set_outs(state, 1)
        _reset_count(state)
        _set_bases(state, first=False, second=True, third=False)

    steps.append(
        ScriptStep(
            at=26.0,
            type="out",
            description="오재일, 깊숙한 플라이로 잡히지만 주자는 진루합니다",
            apply=oh_jaeil_fly,
        )
    )

    def inning_end(state: State) -> None:
        _set_outs(state, 3)
        _change_half(state)
        _set_fielders(state, _samsung_fielders())

    steps.append(
        ScriptStep(
            at=32.0,
            type="change",
            description="더블플레이로 공격 종료, 이제 KIA 공격 차례입니다",
            apply=inning_end,
        )
    )

    def kim_doyoung_entrance(_state: State) -> None:
        _trigger_macro("김도영 응원가")

    steps.append(
        ScriptStep(
            at=36.0,
            type="entrance",
            description="김도영 타석 입장, 기아 팬들의 기대가 커집니다",
            apply=kim_doyoung_entrance,
        )
    )

    def kim_doyoung_return_to_attention(_state: State) -> None:
        _trigger_macro("차렷자세")

    steps.append(
        ScriptStep(
            at=70.0,  # 김도영 응원가 완료 후 차렷 자세로 복귀 (약 34초 응원가 + 여유시간)
            type="info",
            description="차렷 자세로 복귀",
            apply=kim_doyoung_return_to_attention,
        )
    )

    def kim_doyoung_pitch_mix(state: State) -> None:
        _reset_count(state)
        state["count"]["balls"] = 1

    steps.append(
        ScriptStep(
            at=73.0,  # 차렷 자세 후 약간의 여유
            type="ball",
            description="김도영, 낮게 떨어지는 초구를 지켜보며 볼을 고릅니다",
            apply=kim_doyoung_pitch_mix,
        )
    )

    def kim_doyoung_equal(state: State) -> None:
        state["count"]["strikes"] = 1

    steps.append(
        ScriptStep(
            at=75.0,
            type="strike",
            description="김도영, 두 번째 공에는 방망이를 내며 스트라이크를 허용합니다",
            apply=kim_doyoung_equal,
        )
    )

    def kim_doyoung_hr(state: State) -> None:
        _add_hit(state, "home")
        _add_run(state, "home")
        _reset_count(state)
        _set_bases(state, first=False, second=False, third=False)
        _trigger_macro("홈런")

    steps.append(
        ScriptStep(
            at=79.0,  # 차렷 자세 후 홈런 이벤트
            type="hr",
            description="김도영, 좌월 솔로 홈런! 동점을 만들며 분위기를 바꿉니다",
            apply=kim_doyoung_hr,
        )
    )

    def choi_hyoungwoo_single(state: State) -> None:
        _add_hit(state, "home")
        _reset_count(state)
        _set_bases(state, first=True, second=False, third=False)

    steps.append(
        ScriptStep(
            at=83.0,  # 홈런 후 시간 조정
            type="single",
            description="최형우, 침착한 중전 안타로 다시 주자를 내보냅니다",
            apply=choi_hyoungwoo_single,
        )
    )

    def park_chanho_bunt(state: State) -> None:
        _set_outs(state, 1)
        _set_bases(state, first=False, second=False, third=True)

    steps.append(
        ScriptStep(
            at=90.0,  # 홈런 후 시간 조정
            type="bunt",
            description="박찬호, 정교한 스퀴즈 번트로 3루 주자를 압박합니다",
            apply=park_chanho_bunt,
        )
    )

    def socrates_sac_fly(state: State) -> None:
        _add_run(state, "home")
        _set_outs(state, 2)
        _set_bases(state, third=False)

    steps.append(
        ScriptStep(
            at=98.0,  # 홈런 후 시간 조정
            type="sac_fly",
            description="소크라테스, 우중간 희생플라이로 KIA가 앞서갑니다",
            apply=socrates_sac_fly,
        )
    )

    def inning_close(state: State) -> None:
        _set_outs(state, 3)
        _change_half(state)
        _set_fielders(state, _kia_fielders())

    steps.append(
        ScriptStep(
            at=106.0,  # 홈런 후 시간 조정
            type="strikeout",
            description="박동원, 루킹 삼진으로 이닝이 마무리됩니다",
            apply=inning_close,
        )
    )

    def kia_victory(state: State) -> None:
        state["half"] = "F"
        _set_bases(state, first=False, second=False, third=False)
        _set_fielders(state, _kia_fielders())
        _trigger_macro("KIA 승리")

    steps.append(
        ScriptStep(
            at=116.0,  # 홈런 후 시간 조정
            type="final",
            description="KIA 2:1 승리",
            apply=kia_victory,
        )
    )

    steps.append(
        ScriptStep(
            at=121.0,  # 홈런 후 시간 조정
            type="end",
            description="경기 종료",
            apply=stage_reset,
        )
    )

    return steps


def create_kia_vs_samsung_demo() -> ScriptedGame:
    return ScriptedGame(
        steps=_kia_vs_samsung_steps(),
        base_state_factory=_blank_state,
    )


def get_scripted_game(script_id: str) -> ScriptedGame:
    normalized = (script_id or "").strip().lower()
    if normalized in {"", "demo", "kia", "kia_vs_samsung", "kia_samsung_demo"}:
        return create_kia_vs_samsung_demo()
    raise ValueError(f"Unknown script id: {script_id}")


