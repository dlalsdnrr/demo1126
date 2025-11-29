from __future__ import annotations

import random
import threading
import time
import os
import subprocess
from typing import Dict, Any, Optional

from flask import Blueprint, jsonify, render_template, request
from macros_executor import (
    last_event_to_trigger_text,
    trigger_macro,
    calculate_macro_duration,
)
from config import BASEBALL_ID, RASPBERRY_PI_IP, RASPBERRY_PI_MP3_PORT, I2C_MODE

# ============================================================================
# 상수 정의
# ============================================================================

# 매크로 파일 매핑 (매크로 이름 -> (파일키, 매크로키))
DEMO_MACRO_MAP = {
    "차렷자세": ("차렷자세", "차렷자세"),
    "김지찬 응원가": ("김지찬 응원가", "김지찬 응원가"),
    "아웃(삐끼삐끼)": ("아웃(삐끼삐끼)", "아웃(삐끼삐끼)"),
    "김도영 응원가": ("김도영 응원가", "김도영 응원가"),
    "홈런": ("홈런", "홈런"),
    "최강기아": ("외쳐라 최강기아", "최강기아"),
}

# 이벤트 텍스트를 매크로 이름으로 매핑 (각 JSON 파일만 사용)
EVENT_TO_MACRO_MAP = {
    "홈런": "홈런",
    "아웃": "아웃(삐끼삐끼)",
    "삼진아웃": "아웃(삐끼삐끼)",
}

# MP3 파일 매핑
MP3_MAP = {
    "홈런": "homerun.mp3",
    "김도영 응원가": "kimdoyoung.mp3",
    "김지찬 응원가": "kimjichan.mp3",
    "아웃(삐끼삐끼)": "biggibiggi.mp3",
    "외쳐라 최강기아": "best_kia.mp3",
    "최강기아": "best_kia.mp3",
}

# 아두이노 SPI 명령 매핑
ARDUINO_COMMAND_MAP = {
    "김지찬 응원가": "KIM_JICHAN",
    "홈런": "HOMERUN",
    "김도영 응원가": "KIM_DOYOUNG",
    "아웃(삐끼삐끼)": "OUT",
}

# MP3 재생 전 딜레이 설정 (초 단위) - 동작과 소리 싱크 맞추기
MP3_PRE_DELAY_MAP = {
    # 최강기아는 딜레이 없이 잘 맞으므로 김지찬도 동일하게 설정
    "김지찬 응원가": 2.0,  # 동작을 2초 먼저 시작하여 MP3와 싱크 맞춤
}

# MP3 재생 후 딜레이 설정 (초 단위)
MP3_DELAY_MAP = {
    "김지찬 응원가": 0.3,  # 최강기아와 동일한 기본 딜레이로 설정
    "김도영 응원가": 1.0,
    "홈런": 1.8,
    "아웃(삐끼삐끼)": 1.3,
}

# 기본 MP3 딜레이
DEFAULT_MP3_DELAY = 0.3

# 경기 관련 이벤트 타입 (UI에 표시되는 이벤트)
GAME_RELATED_EVENTS = {
    "start", "live", "strikeout", "hr", "single", "double", "triple",
    "out", "sac_fly", "walk", "error", "change", "end", "ball", "strike"
}

# 차렷자세 정렬 대기 시간 (초)
ATTENTION_POSE_ALIGNMENT_TIME = 3.0

# ============================================================================
# SPI 통신 초기화
# ============================================================================

SPI_AVAILABLE = False
spi = None
try:
    import spidev  # type: ignore
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 500000
    SPI_AVAILABLE = True
    print("✓ SPI 통신 초기화 완료")
except ImportError:
    print("⚠️ spidev 모듈이 설치되지 않았습니다")
    SPI_AVAILABLE = False
except Exception as e:
    print(f"⚠️ SPI 통신 초기화 실패: {e}")
    SPI_AVAILABLE = False

# ============================================================================
# Flask Blueprint 및 전역 변수
# ============================================================================

game_bp = Blueprint("game", __name__)
lock = threading.Lock()
game_state: Dict[str, Any] = {}

# ============================================================================
# 게임 상태 관리
# ============================================================================

def _initial_game_state() -> Dict[str, Any]:
    """초기 게임 상태를 반환합니다."""
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

# ============================================================================
# 데모 시나리오 정의
# ============================================================================

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
        "delay": 2,
        "description": "경기 시작",
        "event_type": "start",
    },
    {
        "delay": 2,
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
        "delay": 2,
        "description": "김지찬, 삼진 아웃",
        "event_type": "strikeout",
        "count": {"balls": 0, "strikes": 0, "outs": 1},
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
        "delay": 2,
        "description": "공수 교대",
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
        "delay": 2,
        "description": "김도영 타석 입장",
        "event_type": "live",
        "batter": {"name": "김도영", "active": True},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
    },
    {
        "delay": 0,
        "description": "김도영 응원가",
        "event_type": "chant",
        "macro": "김도영 응원가",
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 0,
        "description": "기본 자세 복귀",
        "event_type": "info",
        "macro": "차렷자세",
    },
    {
        "delay": 0,
        "description": "김도영 좌중월 솔로 홈런!",
        "event_type": "hr",
        "score_delta": {"home": 1},
        "hits_delta": {"home": 1},
        "bases": {"first": False, "second": False, "third": False},
        "count": {"balls": 0, "strikes": 0, "outs": 0},
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
        "delay": 0,
        "description": "기본 자세 복귀",
        "event_type": "info",
        "macro": "차렷자세",
    },
    {
        "delay": 2,
        "description": "기아 우승! 열광하라",
        "event_type": "end",
        "macro": "최강기아",
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

# ============================================================================
# 유틸리티 함수
# ============================================================================

def _is_raspberry_pi() -> bool:
    """라즈베리파이에서 실행 중인지 확인합니다."""
    if I2C_MODE == "auto":
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                if "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo:
                    return True
        except Exception:
            pass
    return False


def _send_spi_command(command: str) -> None:
    """아두이노로 SPI 명령을 전송합니다."""
    if not SPI_AVAILABLE or spi is None:
        return
    
    try:
        packet = command.strip() + "\n"
        spi.xfer2([ord(c) for c in packet])
        print(f"[SPI] → Arduino: {command}")
    except Exception as e:
        print(f"⚠️ SPI 전송 실패: {e}")


def _play_mp3_on_raspberry(mp3_filename: str) -> None:
    """라즈베리파이에서 MP3 파일을 재생합니다."""
    mp3_path = f"/home/raspberry/{mp3_filename}"
    
    if not os.path.exists(mp3_path):
        print(f"⚠️ MP3 파일 없음: {mp3_path}")
        return
    
    try:
        # 기존 재생 중인 mpg123 프로세스 종료
        subprocess.call(["pkill", "-f", "mpg123"], stderr=subprocess.DEVNULL)
        
        # MP3 재생 시작 (비동기)
        print(f"🎧 MP3 재생 시작: {mp3_filename}")
        process = subprocess.Popen(
            ["mpg123", "-a", "hw:0,0", mp3_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # 프로세스가 정상적으로 시작되었는지 확인
        if process.poll() is None:
            # 프로세스가 실행 중이면 성공
            print(f"✓ MP3 재생 프로세스 시작됨: PID {process.pid}")
        else:
            print(f"⚠️ MP3 재생 프로세스가 즉시 종료됨: {mp3_filename}")
            
    except FileNotFoundError:
        print(f"⚠️ mpg123 명령을 찾을 수 없습니다. 설치가 필요합니다: sudo apt-get install mpg123")
    except Exception as e:
        print(f"⚠️ MP3 재생 실패: {e} (파일: {mp3_filename})")


def _get_mp3_delay(macro_name: str) -> float:
    """매크로 이름에 따른 MP3 재생 후 딜레이를 반환합니다."""
    return MP3_DELAY_MAP.get(macro_name, DEFAULT_MP3_DELAY)


def _get_mp3_pre_delay(macro_name: str) -> float:
    """매크로 이름에 따른 MP3 재생 전 딜레이를 반환합니다."""
    return MP3_PRE_DELAY_MAP.get(macro_name, 0.0)


def _wait_with_pause_check(duration: float, stop_event: threading.Event, pause_event: threading.Event, paused: bool) -> None:
    """일시정지 및 정지 이벤트를 체크하면서 대기합니다."""
    waited = 0.0
    chunk = 0.1
    while waited < duration and not stop_event.is_set():
        if paused:
            pause_event.wait()
            if stop_event.is_set():
                break
            continue
        time.sleep(chunk)
        waited += chunk

# ============================================================================
# 데모 시나리오 실행기
# ============================================================================

class DemoScenarioRunner:
    """데모 시나리오를 실행하는 클래스"""
    
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self.current_step: Optional[str] = None
        self._step_index = 0
        self._macro_running = False
        self._macro_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self) -> bool:
        """데모 시나리오를 시작합니다."""
        if self._running:
            return False
        self._stop_event.clear()
        self._pause_event.set()
        self._paused = False
        self._step_index = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        return True

    def pause(self) -> bool:
        """데모 시나리오를 일시정지합니다."""
        if not self._running or self._paused:
            return False
        self._paused = True
        self._pause_event.clear()
        
        with self._macro_lock:
            if self._macro_running:
                print("⏸️ 데모 일시정지: 매크로 실행 중이므로 차렷자세로 복귀")
                _send_spi_command("STOP")
                file_key, macro_key = DEMO_MACRO_MAP.get("차렷자세", (None, None))
                if file_key and macro_key:
                    trigger_macro(file_key, macro_key)
                    print("✓ 차렷자세로 복귀")
        
        return True

    def resume(self) -> bool:
        """데모 시나리오를 재개합니다."""
        if not self._running or not self._paused:
            return False
        self._paused = False
        self._pause_event.set()
        return True

    def stop(self) -> None:
        """데모 시나리오를 정지합니다."""
        if not self._running:
            return
        self._stop_event.set()
        self._pause_event.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        """데모 시나리오 실행 메인 루프"""
        global game_state
        try:
            with lock:
                game_state = _initial_game_state()
                game_state["teams"]["home"]["name"] = "기아"
                game_state["teams"]["away"]["name"] = "삼성"
            
            for idx, step in enumerate(DEMO_SCENARIO_STEPS):
                if self._stop_event.is_set():
                    break
                
                self._step_index = idx
                self.current_step = step.get("description")
                
                # 일시정지 대기
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                
                # 딜레이 처리
                delay = float(step.get("delay", 0))
                if delay > 0:
                    _wait_with_pause_check(delay, self._stop_event, self._pause_event, self._paused)
                
                if self._stop_event.is_set():
                    break
                
                # 일시정지 대기
                self._pause_event.wait()
                if self._stop_event.is_set():
                    break
                
                self._apply_step(step)
            
            self.current_step = None
            self._step_index = 0
        finally:
            self._running = False
            self._paused = False
            self._stop_event.clear()
            self._pause_event.set()

    def _apply_step(self, step: Dict[str, Any]) -> None:
        """시나리오 스텝을 적용합니다."""
        self._update_game_state(step)
        self._execute_macro(step)

    def _update_game_state(self, step: Dict[str, Any]) -> None:
        """게임 상태를 업데이트합니다."""
        global game_state
        with lock:
            state = game_state
            teams = state["teams"]

            # 팀 이름 설정
            if "set_teams" in step:
                for side, name in step["set_teams"].items():
                    if side in teams:
                        teams[side]["name"] = name

            # 점수 설정
            if "set_scores" in step:
                for side, value in step["set_scores"].items():
                    if side in teams:
                        teams[side]["runs"] = max(0, int(value))

            # 안타 설정
            if "set_hits" in step:
                for side, value in step["set_hits"].items():
                    if side in teams:
                        teams[side]["hits"] = max(0, int(value))

            # 에러 설정
            if "set_errors" in step:
                for side, value in step["set_errors"].items():
                    if side in teams:
                        teams[side]["errors"] = max(0, int(value))

            # 점수 변화
            if "score_delta" in step:
                for side, delta in step["score_delta"].items():
                    if side in teams:
                        teams[side]["runs"] = max(0, teams[side]["runs"] + int(delta))

            # 안타 변화
            if "hits_delta" in step:
                for side, delta in step["hits_delta"].items():
                    if side in teams:
                        teams[side]["hits"] = max(0, teams[side]["hits"] + int(delta))

            # 에러 변화
            if "errors_delta" in step:
                for side, delta in step["errors_delta"].items():
                    if side in teams:
                        teams[side]["errors"] = max(0, teams[side]["errors"] + int(delta))

            # 이닝, 하프 설정
            if "inning" in step:
                state["inning"] = int(step["inning"])
            if "half" in step:
                state["half"] = step["half"]

            # 카운트, 베이스, 주자 설정
            if "count" in step:
                state["count"].update(step["count"])
            if "bases" in step:
                state["bases"].update(step["bases"])
            if "runners" in step:
                if "runners" not in state:
                    state["runners"] = {"first": "", "second": "", "third": ""}
                state["runners"].update(step["runners"])

            # 타자, 수비수 설정
            if "batter" in step:
                if "batter" not in state:
                    state["batter"] = {"name": "", "active": False}
                state["batter"].update(step["batter"])
            if "fielders" in step:
                state["fielders"].update(step["fielders"])

            # 경기 이벤트 업데이트 (UI 표시용)
            event_type = step.get("event_type", "live")
            if event_type in GAME_RELATED_EVENTS:
                popup_desc = step.get("popup_description")
                state["last_event"] = {
                    "type": event_type,
                    "description": step.get("description", ""),
                    "popup_description": popup_desc if popup_desc is not None else None,
                }

    def _execute_macro(self, step: Dict[str, Any]) -> None:
        """매크로를 실행합니다."""
        macro_name = step.get("macro")
        if not macro_name:
            return

        file_key, macro_key = DEMO_MACRO_MAP.get(macro_name, (None, None))
        if not file_key or not macro_key:
            print(f"⚠️ 데모 매크로 매핑 없음: '{macro_name}'")
            print(f"  → DEMO_MACRO_MAP에 '{macro_name}' 키가 없습니다")
            return

        try:
            # 매크로 정보 확인
            macro_duration = calculate_macro_duration(file_key, macro_key)
            arduino_cmd = ARDUINO_COMMAND_MAP.get(macro_name)
            mp3_file = MP3_MAP.get(macro_name)
            is_attention_pose = (macro_name == "차렷자세")
            
            # 1. 아두이노 SPI 명령 전송 (바퀴 움직임)
            if arduino_cmd:
                _send_spi_command(arduino_cmd)
                print(f"🎮 아두이노 명령 전송: {arduino_cmd}")
            
            # 2. 매크로 실행 (팔 동작)
            success = trigger_macro(file_key, macro_key)
            if not success:
                print(f"⚠️ 데모 매크로 '{file_key}:{macro_key}' 실행 실패")
                print(f"  → 매크로 파일 '{file_key}' 또는 매크로 이름 '{macro_key}' 확인 필요")
                return
            
            # 3. MP3 재생 처리 (SPI 명령이 없는 경우에만)
            if not arduino_cmd and mp3_file:
                self._handle_mp3_playback(macro_name, mp3_file)
            elif arduino_cmd:
                print(f"ℹ️ {macro_name}: SPI 명령으로 MP3 재생 처리됨 (ble_to_i2c_bridge)")
            
            # 4. 매크로 실행 시간 대기
            self._wait_for_macro_completion(
                macro_name,
                macro_duration,
                is_attention_pose,
                step.get('description', '')
            )
            
            print(f"▶️ 매크로 완료: {macro_name}")
            
        except Exception as e:
            print(f"✗ 데모 매크로 '{file_key}:{macro_key}' 실행 중 예외 발생: {type(e).__name__}: {e}")
    
    def _handle_mp3_playback(self, macro_name: str, mp3_file: str) -> None:
        """MP3 재생을 처리합니다."""
        pre_delay = _get_mp3_pre_delay(macro_name)
        
        if pre_delay > 0:
            print(f"⏳ {macro_name} 동작 먼저 시작: {pre_delay}초 후 MP3 재생")
            time.sleep(pre_delay)
        
        _play_mp3_on_raspberry(mp3_file)
        
        post_delay = _get_mp3_delay(macro_name)
        if post_delay > 0:
            print(f"⏳ {macro_name} 싱크 조정: {post_delay}초 대기")
            time.sleep(post_delay)
    
    def _wait_for_macro_completion(
        self,
        macro_name: str,
        macro_duration: float,
        is_attention_pose: bool,
        description: str
    ) -> None:
        """매크로 실행 완료까지 대기합니다."""
        with self._macro_lock:
            self._macro_running = True
        
        # 차렷자세는 정렬 시간이 필요
        if is_attention_pose:
            wait_time = ATTENTION_POSE_ALIGNMENT_TIME
            print(f"⏸️ 차렷자세 매크로 실행 중 (정렬 대기: {wait_time}초)")
        elif macro_duration > 0:
            wait_time = macro_duration
            print(f"⏸️ 매크로 실행 중: {description} ({wait_time:.1f}초)")
        else:
            # duration이 0이면 대기하지 않음
            with self._macro_lock:
                self._macro_running = False
            return
        
        _wait_with_pause_check(
            wait_time,
            self._stop_event,
            self._pause_event,
            self._paused
        )
        
        with self._macro_lock:
            self._macro_running = False


demo_runner = DemoScenarioRunner()

# ============================================================================
# 게임 이벤트 처리
# ============================================================================

def _advance_random_event(state: Dict[str, Any]) -> None:
    """랜덤 이벤트를 생성하고 게임 상태를 업데이트합니다."""
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
    """주자를 진루시킵니다."""
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

# ============================================================================
# Flask 라우트
# ============================================================================

@game_bp.route("/")
def index():
    return render_template("game.html")


@game_bp.route("/api/game-state")
def api_game_state():
    """게임 상태를 반환합니다."""
    global game_state
    should_advance = request.args.get("advance", "0") == "1"
    demo_active = demo_runner.is_running
    
    with lock:
        if should_advance and not demo_active:
            _advance_random_event(game_state)
        
        response = dict(game_state)
        response["teams"] = {k: dict(v) for k, v in game_state["teams"].items()}
        response["count"] = dict(game_state["count"])
        response["bases"] = dict(game_state["bases"])
        response["runners"] = dict(game_state.get("runners", {"first": "", "second": "", "third": ""}))
        response["batter"] = dict(game_state.get("batter", {"name": "", "active": False}))
        response["fielders"] = {k: dict(v) for k, v in game_state.get("fielders", {}).items()}
        response["last_event"] = dict(game_state["last_event"]) if game_state.get("last_event") else None
    
    response["demo_active"] = demo_active
    response["demo_paused"] = demo_runner.is_paused
    response["demo_step"] = demo_runner.current_step

    trigger_text = last_event_to_trigger_text(response.get("last_event"))
    if trigger_text and not demo_active:
        # 이벤트 텍스트를 매크로 이름으로 변환 (각 JSON 파일만 사용)
        macro_name = EVENT_TO_MACRO_MAP.get(trigger_text)
        if macro_name:
            file_key, macro_key = DEMO_MACRO_MAP.get(macro_name, (None, None))
            if file_key and macro_key:
                trigger_macro(file_key, macro_key)

    return jsonify(response)


@game_bp.route("/api/reset", methods=["POST"])
def api_reset():
    """게임 상태를 초기화합니다."""
    global game_state
    with lock:
        game_state = _initial_game_state()
    return jsonify({"ok": True})


@game_bp.route("/api/demo/start", methods=["POST"])
def api_demo_start():
    """데모 시나리오를 시작합니다."""
    if demo_runner.start():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_running"}), 409


@game_bp.route("/api/demo/status")
def api_demo_status():
    """데모 시나리오 상태를 반환합니다."""
    return jsonify({
        "ok": True,
        "running": demo_runner.is_running,
        "paused": demo_runner.is_paused,
        "step": demo_runner.current_step
    })


@game_bp.route("/api/demo/pause", methods=["POST"])
def api_demo_pause():
    """데모 시나리오를 일시정지합니다."""
    if demo_runner.pause():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_not_running_or_already_paused"}), 400


@game_bp.route("/api/demo/resume", methods=["POST"])
def api_demo_resume():
    """데모 시나리오를 재개합니다."""
    if demo_runner.resume():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_not_running_or_not_paused"}), 400


@game_bp.route("/api/demo/restart", methods=["POST"])
def api_demo_restart():
    """데모 시나리오를 처음부터 다시 시작합니다."""
    demo_runner.stop()
    time.sleep(0.5)
    if demo_runner.start():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_start_failed"}), 500


@game_bp.route("/api/config")
def api_config():
    """클라이언트에서 사용할 설정값을 반환합니다."""
    return jsonify({"ok": True, "gameId": BASEBALL_ID or ""})
