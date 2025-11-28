from __future__ import annotations

import random
import threading
import time
import os
import subprocess
import platform
from typing import Dict, Any, Optional

from flask import Blueprint, jsonify, render_template, request
from macros_executor import (
    run_macro_by_event_text_async,
    last_event_to_trigger_text,
    run_macro_by_name_async,
)
from macros_executor import trigger_macro, calculate_macro_duration
from config import BASEBALL_ID, RASPBERRY_PI_IP, RASPBERRY_PI_MP3_PORT, I2C_MODE

# SPI 통신 (라즈베리파이에서만 사용)
SPI_AVAILABLE = False
spi = None
try:
    if platform.system() == "Linux":
        try:
            import spidev  # type: ignore
            spi = spidev.SpiDev()
            spi.open(0, 0)
            spi.max_speed_hz = 500000
            SPI_AVAILABLE = True
            print("✓ SPI 통신 초기화 완료")
        except ImportError:
            print("⚠️ spidev 모듈이 설치되지 않았습니다 (라즈베리파이에서만 필요)")
            SPI_AVAILABLE = False
except Exception as e:
    print(f"⚠️ SPI 통신 초기화 실패: {e}")
    SPI_AVAILABLE = False


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
        "macro": "김도영 응원가가",
        "batter": {"name": "김도영", "active": True},
    },
    {
        "delay": 2,
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


class DemoScenarioRunner:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False  # 사용자가 일시정지한 경우만 True
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 초기에는 일시정지 해제 상태
        self.current_step: Optional[str] = None
        self._step_index = 0  # 현재 진행 중인 스텝 인덱스
        self._macro_running = False  # 매크로 실행 중 플래그
        self._macro_lock = threading.Lock()  # 매크로 실행 상태 보호

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def start(self) -> bool:
        if self._running:
            return False
        self._stop_event.clear()
        self._pause_event.set()  # 시작 시 일시정지 해제
        self._paused = False
        self._step_index = 0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        return True

    def pause(self) -> bool:
        if not self._running or self._paused:
            return False
        self._paused = True
        self._pause_event.clear()  # 일시정지
        
        # 매크로 실행 중이면 차렷자세로 복귀
        with self._macro_lock:
            if self._macro_running:
                print("⏸️ 데모 일시정지: 매크로 실행 중이므로 차렷자세로 복귀")
                # 아두이노에 STOP 명령 전송 (바퀴 멈춤)
                _send_spi_command("STOP")
                # 차렷자세 매크로 실행
                file_key, macro_key = DEMO_MACRO_MAP.get("차렷자세", (None, None))
                if file_key and macro_key:
                    trigger_macro(file_key, macro_key)
                    print("✓ 차렷자세로 복귀")
        
        return True

    def resume(self) -> bool:
        if not self._running or not self._paused:
            return False
        self._paused = False
        self._pause_event.set()  # 재개
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        self._pause_event.set()  # 정지 시 일시정지 해제
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
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
                
                delay = float(step.get("delay", 0))
                if delay > 0:
                    waited = 0.0
                    while waited < delay and not self._stop_event.is_set():
                        # 일시정지 중이면 대기
                        if self._paused:
                            self._pause_event.wait()  # 일시정지 해제까지 대기
                            if self._stop_event.is_set():
                                break
                            continue  # 일시정지 해제 후 다시 체크
                        if self._stop_event.is_set():
                            break
                        chunk = min(0.1, delay - waited)
                        time.sleep(chunk)
                        waited += chunk
                
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
            # MP3 파일 매핑
            MP3_MAP = {
                "홈런": "homerun.mp3",
                "김도영 응원가": "kimdoyoung.mp3",
                "김도영 응원가가": "kimdoyoung.mp3",  # DEMO_MACRO_MAP의 키와 일치
                "김지찬 응원가": "kimjichan.mp3",
                "아웃(삐끼삐끼)": "biggibiggi.mp3",
                "외쳐라 최강기아": "best_kia.mp3",
                "최강기아": "best_kia.mp3",  # DEMO_MACRO_MAP의 키와 일치
            }
            
            file_key, macro_key = DEMO_MACRO_MAP.get(macro_name, (None, None))
            if file_key and macro_key:
                try:
                    # 매크로 실행 시간 계산
                    macro_duration = calculate_macro_duration(file_key, macro_key)
                    
                    # MP3 재생 (매크로 시작 전에 재생 시작)
                    mp3_file = MP3_MAP.get(macro_name)
                    if mp3_file:
                        # 김지찬 응원가만 2초 딜레이 추가
                        if macro_name == "김지찬 응원가":
                            print("⏳ 김지찬 응원가 MP3 재생 2초 딜레이...")
                            time.sleep(2.0)
                        _play_mp3_on_raspberry(mp3_file)
                        # MP3 재생 시작 후 약간의 딜레이 (MP3와 동작 싱크 맞추기)
                        time.sleep(0.3)
                    
                    # 아두이노로 SPI 명령 전송 (바퀴 움직임)
                    arduino_cmd = ARDUINO_COMMAND_MAP.get(macro_name)
                    if arduino_cmd:
                        _send_spi_command(arduino_cmd)
                        print(f"🎮 아두이노 명령 전송: {arduino_cmd}")
                    
                    # 매크로 실행 (비동기)
                    success = trigger_macro(file_key, macro_key)
                    if not success:
                        print(f"⚠️ 데모 매크로 '{file_key}:{macro_key}' 실행 실패")
                        print(f"  → 매크로 파일 '{file_key}' 또는 매크로 이름 '{macro_key}' 확인 필요")
                    else:
                        # 매크로 실행 중 시나리오 일시정지 (내부적으로만 처리, 사용자 일시정지와 구분)
                        if macro_duration > 0:
                            # 매크로 실행 중 플래그 설정
                            with self._macro_lock:
                                self._macro_running = True
                            
                            # 매크로 실행 중에는 _pause_event를 clear하지 않음 (사용자 일시정지와 구분)
                            print(f"⏸️ 매크로 실행 중: {step.get('description', '')} ({macro_duration:.1f}초)")
                            
                            # 매크로 실행 시간 동안 대기 (일시정지 감지)
                            waited = 0.0
                            chunk = 0.1  # 0.1초씩 체크
                            while waited < macro_duration and not self._stop_event.is_set():
                                # 사용자가 일시정지했는지 확인
                                if self._paused:
                                    print("⏸️ 사용자 일시정지 감지, 매크로 대기 중단")
                                    # 일시정지 해제까지 대기
                                    self._pause_event.wait()
                                    if self._stop_event.is_set():
                                        break
                                    # 일시정지 해제 후에도 매크로 대기 중단 (차렷자세로 복귀했으므로)
                                    break
                                time.sleep(chunk)
                                waited += chunk
                            
                            # 매크로 실행 완료
                            with self._macro_lock:
                                self._macro_running = False
                            
                            # 동작 간 텀 추가 (1.5초) - 일시정지 상태 체크
                            if not self._paused and not self._stop_event.is_set():
                                print(f"⏳ 동작 간 텀: 1.5초")
                                waited = 0.0
                                while waited < 1.5 and not self._stop_event.is_set():
                                    if self._paused:
                                        self._pause_event.wait()
                                        if self._stop_event.is_set():
                                            break
                                        continue
                                    chunk = min(0.1, 1.5 - waited)
                                    time.sleep(chunk)
                                    waited += chunk
                            
                            print(f"▶️ 매크로 완료")
                except Exception as e:
                    print(f"✗ 데모 매크로 '{file_key}:{macro_key}' 실행 중 예외 발생: {type(e).__name__}: {e}")
            else:
                print(f"⚠️ 데모 매크로 매핑 없음: '{macro_name}'")
                print(f"  → DEMO_MACRO_MAP에 '{macro_name}' 키가 없습니다")


demo_runner = DemoScenarioRunner()


def _is_raspberry_pi() -> bool:
    """라즈베리파이에서 실행 중인지 확인"""
    # I2C_MODE가 auto이고 Linux 환경이면 라즈베리파이로 간주
    if I2C_MODE == "auto" and platform.system() == "Linux":
        # 추가 확인: /proc/cpuinfo에 Raspberry Pi 정보가 있는지 확인
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                if "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo:
                    return True
        except:
            pass
    return False


def _send_spi_command(command: str) -> None:
    """아두이노로 SPI 명령 전송"""
    if not SPI_AVAILABLE or spi is None:
        return
    
    try:
        packet = command.strip() + "\n"
        spi.xfer2([ord(c) for c in packet])
        print(f"[SPI] → Arduino: {command}")
    except Exception as e:
        print(f"⚠️ SPI 전송 실패: {e}")


# 매크로 이름을 아두이노 SPI 명령어로 매핑
ARDUINO_COMMAND_MAP = {
    "김지찬 응원가": "KIM_JICHAN",
    "홈런": "HOMERUN",
    "김도영 응원가가": "KIM_DOYOUNG",
    "김도영 응원가": "KIM_DOYOUNG",  # 별칭
    "아웃(삐끼삐끼)": "KIAOUT",
}


def _play_mp3_on_raspberry(mp3_filename: str) -> None:
    """라즈베리파이에서 MP3 파일을 재생합니다"""
    is_rpi = _is_raspberry_pi()
    
    if is_rpi:
        # 라즈베리파이에서 직접 재생
        mp3_path = f"/home/raspberry/{mp3_filename}"
        
        if not os.path.exists(mp3_path):
            print(f"⚠️ MP3 파일 없음: {mp3_path}")
            return
        
        try:
            # 기존 재생 중인 mpg123 프로세스 종료
            subprocess.call(["pkill", "-f", "mpg123"], stderr=subprocess.DEVNULL)
            
            # MP3 재생 (비동기)
            print(f"🎧 MP3 재생 시작: {mp3_filename}")
            subprocess.Popen(
                ["mpg123", "-a", "hw:0,0", mp3_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            print(f"⚠️ MP3 재생 실패: {e} (파일: {mp3_filename})")
    elif RASPBERRY_PI_IP:
        # PC에서 라즈베리파이로 HTTP 요청
        try:
            import requests
            url = f"http://{RASPBERRY_PI_IP}:{RASPBERRY_PI_MP3_PORT}/play"
            response = requests.post(url, json={"filename": mp3_filename}, timeout=2)
            if response.status_code == 200:
                print(f"🎵 MP3 재생 요청 전송: {mp3_filename}")
            else:
                print(f"⚠️ MP3 재생 요청 실패 ({response.status_code}): {mp3_filename}")
        except ImportError:
            print(f"⚠️ requests 모듈이 없어 MP3 재생을 건너뜁니다: {mp3_filename}")
        except Exception as e:
            print(f"⚠️ MP3 재생 요청 중 오류: {e} (파일: {mp3_filename})")
    else:
        print(f"⚠️ 라즈베리파이 환경이 아니고 IP도 설정되지 않아 MP3 재생을 건너뜁니다: {mp3_filename}")


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
    # 데모가 실행 중이거나 일시정지 중이면 자동 진행 비활성화
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
    response["demo_paused"] = demo_runner.is_paused
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
    return jsonify({
        "ok": True,
        "running": demo_runner.is_running,
        "paused": demo_runner.is_paused,
        "step": demo_runner.current_step
    })


@game_bp.route("/api/demo/pause", methods=["POST"])
def api_demo_pause():
    if demo_runner.pause():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_not_running_or_already_paused"}), 400


@game_bp.route("/api/demo/resume", methods=["POST"])
def api_demo_resume():
    if demo_runner.resume():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_not_running_or_not_paused"}), 400


@game_bp.route("/api/demo/restart", methods=["POST"])
def api_demo_restart():
    """데모를 처음부터 다시 시작합니다"""
    demo_runner.stop()
    time.sleep(0.5)  # 정지 완료 대기
    if demo_runner.start():
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "demo_start_failed"}), 500


@game_bp.route("/api/config")
def api_config():
    """클라이언트에서 사용할 설정값을 반환합니다."""
    return jsonify({"ok": True, "gameId": BASEBALL_ID or ""})


