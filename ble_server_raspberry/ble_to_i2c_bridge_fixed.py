#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BLE to I2C Bridge for Baseball Robot
BLE 신호를 받아 SPI, OpenCM, MP3를 제어하는 서버
"""

import dbus
import dbus.exceptions
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
import subprocess
import time
import os
import spidev
import json
import glob
import threading
from typing import Optional, Dict, Tuple

# 시리얼 포트 자동 검색을 위한 import
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


# ============================================================================
# 상수 정의
# ============================================================================

# BLE UUID 설정
SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID = 'abcdef01-1234-5678-1234-56789abcdef0'
LOCAL_NAME = 'kimjunha-desktop'

# BlueZ 인터페이스
BLUEZ_SERVICE = 'org.bluez'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
ADV_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
OBJ_MANAGER_IFACE = 'org.freedesktop.DBus.ObjectManager'

# 하드웨어 설정
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 500000
OPENCM_BAUDRATE = 115200
OPENCM_INIT_DELAY = 2.0

# OpenCM 모터 ID 매핑
MOTOR_ID_MAP = {
    "R1": 25,
    "R2": 50,
    "RE": 75,
    "L1": 100,
    "L2": 125,
    "LE": 150
}

# 매크로 실행 설정 (명령어 -> (매크로파일명, MP3파일명, MP3재생전딜레이, MP3재생후딜레이, 스레드실행여부))
MACRO_CONFIG = {
    "HOMERUN": {
        "macro_file": "homerun",
        "mp3_file": "homerun.mp3",
        "mp3_pre_delay": 0.0,
        "mp3_post_delay": 1.8,
        "threaded": False
    },
    "KIM_DOYOUNG": {
        "macro_file": "kimdoyoung",
        "mp3_file": "kimdoyoung.mp3",
        "mp3_pre_delay": 0.0,
        "mp3_post_delay": 1.0,
        "threaded": False
    },
    "KIM_JICHAN": {
        "macro_file": "kimjichan",
        "mp3_file": "kimjichan.mp3",
        "mp3_pre_delay": 0.5,  # 동작 먼저 시작 후 MP3 재생
        "mp3_post_delay": 0.0,
        "threaded": True  # 팔 동작을 스레드로 실행
    },
    "OUT": {
        "macro_file": "biggibiggi",
        "mp3_file": "biggibiggi.mp3",
        "mp3_pre_delay": 0.0,
        "mp3_post_delay": 1.0,
        "threaded": False
    },
    "STOP": {
        "macro_file": "stop",
        "mp3_file": None,
        "mp3_pre_delay": 0.0,
        "mp3_post_delay": 0.0,
        "threaded": False
    }
}

# 경로 설정
MACRO_DIR = "/home/raspberry/baseball_robot/macros/"
MP3_BASE_DIR = "/home/raspberry/"


# ============================================================================
# SPI 통신 (Arduino Mega)
# ============================================================================

class SPIController:
    """SPI 통신을 담당하는 클래스"""
    
    def __init__(self, bus: int = SPI_BUS, device: int = SPI_DEVICE, speed_hz: int = SPI_SPEED_HZ):
        self.spi: Optional[spidev.SpiDev] = None
        try:
            self.spi = spidev.SpiDev()
            self.spi.open(bus, device)
            self.spi.max_speed_hz = speed_hz
            print("✓ SPI 통신 초기화 완료")
        except Exception as e:
            print(f"⚠️ SPI 통신 초기화 실패: {e}")
            self.spi = None
    
    def send(self, message: str) -> None:
        """Arduino로 SPI 명령을 전송합니다."""
        if self.spi is None:
            return
        
        try:
            packet = message.strip() + "\n"
            self.spi.xfer2([ord(c) for c in packet])
            print(f"[SPI] → Arduino: {packet.strip()}")
        except Exception as e:
            print(f"⚠️ SPI 전송 실패: {e}")


# ============================================================================
# OpenCM Serial (Dynamixel)
# ============================================================================

class OpenCMController:
    """OpenCM 시리얼 통신을 담당하는 클래스"""
    
    def __init__(self, motor_id_map: Dict[str, int] = None):
        self.motor_id_map = motor_id_map or MOTOR_ID_MAP if motor_id_map is None else motor_id_map
        self.serial: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        self._connect()
    
    def _find_port(self) -> Optional[str]:
        """OpenCM 시리얼 포트를 자동으로 찾습니다 (라즈베리파이 전용)."""
        if serial is None or list_ports is None:
            print("❌ pyserial이 설치되지 않음")
            return None
        
        ports = list_ports.comports()
        
        # 라즈베리파이: ttyACM 또는 ttyUSB 포트 검색
        for port in ports:
            port_name = port.device
            if 'ttyACM' in port_name or 'ttyUSB' in port_name:
                if self._test_port(port_name):
                    return port_name
        
        print("❌ OpenCM 포트를 찾을 수 없음")
        return None
    
    def _test_port(self, port_name: str) -> bool:
        """포트가 실제로 열릴 수 있는지 테스트합니다."""
        try:
            test_ser = serial.Serial(port_name, OPENCM_BAUDRATE, timeout=1)
            test_ser.close()
            print(f"✓ OpenCM 포트 발견: {port_name}")
            return True
        except (serial.SerialException, OSError):
            return False
    
    def _connect(self) -> None:
        """OpenCM에 연결합니다."""
        self.port = self._find_port()
        if not self.port:
            return
        
        try:
            self.serial = serial.Serial(self.port, OPENCM_BAUDRATE, timeout=1)
            print(f"✓ OpenCM 연결 성공 ({self.port})")
            time.sleep(OPENCM_INIT_DELAY)
        except Exception as e:
            self.serial = None
            print(f"❌ OpenCM 연결 실패 ({self.port}): {e}")
    
    def send_command(self, motor_id: str, position: int, speed: int) -> None:
        """OpenCM으로 모터 명령을 전송합니다."""
        if self.serial is None:
            print("[OpenCM ERROR] 연결되지 않음")
            return
        
        if motor_id not in self.motor_id_map:
            print(f"[OpenCM ERROR] Unknown motor_id: {motor_id}")
            return
        
        real_id = self.motor_id_map[motor_id]
        cmd = f"{real_id},{position},{speed}\n"
        
        try:
            self.serial.write(cmd.encode('ascii'))
            self.serial.flush()
            print(f"[OpenCM →] {cmd.strip()}")
            time.sleep(0.004)  # 명령 간 최소 간격
        except Exception as e:
            print(f"⚠️ OpenCM Write Error: {e}")


# ============================================================================
# 매크로 관리
# ============================================================================

class MacroManager:
    """매크로 파일을 로드하고 실행하는 클래스"""
    
    def __init__(self, macro_dir: str, opencm_controller: OpenCMController):
        self.macro_dir = macro_dir
        self.opencm = opencm_controller
        self.macros: Dict[str, Dict] = {}
        self.load_all()
    
    def load_all(self) -> None:
        """모든 매크로 파일을 로드합니다."""
        self.macros = {}
        
        if not os.path.exists(self.macro_dir):
            print(f"⚠️ 매크로 디렉토리가 없습니다: {self.macro_dir}")
            return
        
        macro_files = glob.glob(os.path.join(self.macro_dir, "*.json"))
        
        for file_path in macro_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    name = os.path.basename(file_path).replace(".json", "")
                    self.macros[name] = data.get("macros", {})
                    print(f"[MACRO] 로드됨 → {name}")
            except Exception as e:
                print(f"⚠️ [MACRO ERROR] {file_path}: {e}")
        
        print(f"✓ 총 {len(self.macros)}개의 매크로 로드 완료\n")
    
    def execute(self, macro_name: str) -> None:
        """매크로를 실행합니다."""
        if macro_name not in self.macros:
            print(f"⚠️ [ERROR] 매크로 '{macro_name}' 없음")
            return
        
        macros_dict = self.macros[macro_name]
        if not macros_dict:
            print(f"⚠️ [ERROR] '{macro_name}' 파일에 매크로가 없음")
            return
        
        # JSON 내부의 첫 번째 매크로를 사용
        macro_key = list(macros_dict.keys())[0]
        steps = macros_dict[macro_key]
        
        if not steps:
            print(f"⚠️ [ERROR] '{macro_name}'의 '{macro_key}' 매크로가 비어있음")
            return
        
        print(f"🔥 매크로 시작: {macro_name} -> {macro_key}")
        
        for step in steps:
            motor_id = step["motor_id"]
            pos = step["position"]
            speed = step["speed"]
            delay_ms = step["delay_ms"]
            
            self.opencm.send_command(motor_id, pos, speed)
            
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        
        print(f"🏁 매크로 종료: {macro_name} -> {macro_key}\n")


# ============================================================================
# MP3 재생
# ============================================================================

class MP3Player:
    """MP3 파일 재생을 담당하는 클래스"""
    
    def __init__(self, base_dir: str = MP3_BASE_DIR):
        self.base_dir = base_dir
    
    def play(self, filename: str) -> None:
        """MP3 파일을 재생합니다."""
        path = os.path.join(self.base_dir, filename)
        
        print(f"🎵 요청된 파일: {path}")
        
        if not os.path.exists(path):
            print(f"❌ MP3 파일 없음: {path}")
            return
        
        # 기존 재생 중인 mpg123 프로세스 종료
        subprocess.call(["pkill", "-f", "mpg123"], stderr=subprocess.DEVNULL)
        
        print(f"🎧 MP3 재생 시작 → {filename}")
        try:
            subprocess.Popen(
                ["mpg123", "-a", "hw:0,0", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print("⚠️ mpg123 명령을 찾을 수 없습니다. 설치가 필요합니다: sudo apt-get install mpg123")


# ============================================================================
# 매크로 실행 핸들러
# ============================================================================

class MacroHandler:
    """BLE 명령을 받아 매크로를 실행하는 핸들러"""
    
    def __init__(self, spi_controller: SPIController, macro_manager: MacroManager, mp3_player: MP3Player):
        self.spi = spi_controller
        self.macros = macro_manager
        self.mp3 = mp3_player
        self.config = MACRO_CONFIG
    
    def handle_command(self, command: str) -> None:
        """BLE 명령을 처리합니다."""
        # SPI 명령 전송
        self.spi.send(command)
        
        # 명령어 매칭
        config = None
        for key, cfg in self.config.items():
            if command.startswith(key):
                config = cfg
                break
        
        if not config:
            return
        
        # 매크로 실행
        macro_file = config["macro_file"]
        mp3_file = config.get("mp3_file")
        mp3_pre_delay = config.get("mp3_pre_delay", 0.0)
        mp3_post_delay = config.get("mp3_post_delay", 0.0)
        threaded = config.get("threaded", False)
        
        # MP3 재생 전 딜레이
        if mp3_pre_delay > 0:
            time.sleep(mp3_pre_delay)
        
        # MP3 재생 (있는 경우)
        if mp3_file:
            self.mp3.play(mp3_file)
        
        # 매크로 실행
        if threaded:
            # 스레드로 실행 (예: KIM_JICHAN)
            threading.Thread(
                target=self.macros.execute,
                args=(macro_file,),
                daemon=True
            ).start()
        else:
            # 동기 실행
            if mp3_post_delay > 0:
                time.sleep(mp3_post_delay)
            self.macros.execute(macro_file)


# ============================================================================
# GATT Application (BLE)
# ============================================================================

class Application(dbus.service.Object):
    """BLE GATT 애플리케이션"""
    
    def __init__(self, bus, macro_handler: MacroHandler):
        self.path = "/org/bluez/example"
        self.services = []
        self.macro_handler = macro_handler
        super().__init__(bus, self.path)
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    def add_service(self, service):
        self.services.append(service)
    
    @dbus.service.method(OBJ_MANAGER_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for ch in service.characteristics:
                response[ch.get_path()] = ch.get_properties()
        return response


class Service(dbus.service.Object):
    """GATT 서비스"""
    
    def __init__(self, bus, index, uuid, primary):
        self.path = f"/org/bluez/example/service{index}"
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        super().__init__(bus, self.path)
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    def add_characteristic(self, ch):
        self.characteristics.append(ch)
    
    def get_properties(self):
        return {
            GATT_SERVICE_IFACE: {
                'UUID': self.uuid,
                'Primary': self.primary
            }
        }


class Characteristic(dbus.service.Object):
    """GATT 특성 (BLE 명령 수신)"""
    
    def __init__(self, bus, index, uuid, service, macro_handler: MacroHandler):
        self.path = f"{service.path}/char{index}"
        self.uuid = uuid
        self.service = service
        self.macro_handler = macro_handler
        super().__init__(bus, self.path)
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    def get_properties(self):
        return {
            GATT_CHRC_IFACE: {
                'UUID': self.uuid,
                'Service': self.service.get_path(),
                'Flags': ['read', 'write', 'write-without-response']
            }
        }
    
    @dbus.service.method(GATT_CHRC_IFACE, in_signature='aya{sv}')
    def WriteValue(self, value, options):
        """BLE로부터 명령을 받습니다."""
        msg = bytes(value).decode(errors='ignore')
        cleaned = msg.replace('\x00', '').replace('\r', '').replace('\n', '').strip()
        key = cleaned.upper()
        
        print("===== BLE PACKET RECEIVED =====")
        print(f"RAW   → {repr(msg)}")
        print(f"CLEAN → {repr(key)}")
        print("================================\n")
        
        # 매크로 핸들러로 전달
        self.macro_handler.handle_command(key)
    
    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        """BLE 읽기 요청에 응답합니다."""
        return dbus.Array(b"SPI Ready", signature='y')


class Advertisement(dbus.service.Object):
    """BLE 광고"""
    
    PATH = "/org/bluez/example/advertisement0"
    
    def __init__(self, bus):
        super().__init__(bus, self.PATH)
    
    @dbus.service.method('org.bluez.LEAdvertisement1')
    def Release(self):
        print("Advertisement Released")
    
    def get_properties(self):
        return {
            'org.bluez.LEAdvertisement1': {
                'Type': 'peripheral',
                'LocalName': LOCAL_NAME,
                'ServiceUUIDs': [SERVICE_UUID],
                'Includes': ['tx-power', 'local-name']
            }
        }
    
    def get_path(self):
        return dbus.ObjectPath(self.PATH)


# ============================================================================
# 메인 함수
# ============================================================================

def main():
    """메인 함수"""
    print("📂 매크로 파일 로드 중…")
    
    # 하드웨어 컨트롤러 초기화
    spi_controller = SPIController()
    opencm_controller = OpenCMController()
    macro_manager = MacroManager(MACRO_DIR, opencm_controller)
    mp3_player = MP3Player()
    macro_handler = MacroHandler(spi_controller, macro_manager, mp3_player)
    
    # BLE 초기화
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    
    adapter_path = "/org/bluez/hci0"
    adapter = bus.get_object(BLUEZ_SERVICE, adapter_path)
    props = dbus.Interface(adapter, "org.freedesktop.DBus.Properties")
    
    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(1))
    props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(1))
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(1))
    
    app = Application(bus, macro_handler)
    service = Service(bus, 0, SERVICE_UUID, True)
    ch = Characteristic(bus, 0, CHAR_UUID, service, macro_handler)
    service.add_characteristic(ch)
    app.add_service(service)
    
    gatt_manager = dbus.Interface(adapter, GATT_MANAGER_IFACE)
    adv_manager = dbus.Interface(adapter, ADV_MANAGER_IFACE)
    advertisement = Advertisement(bus)
    
    loop = GLib.MainLoop()
    
    def gatt_ok():
        print("✓ GATT 등록 완료")
        time.sleep(1)
        
        adv_manager.RegisterAdvertisement(
            advertisement.get_path(), {},
            reply_handler=lambda: print("📡 BLE Advertising 시작됨"),
            error_handler=lambda e: print(f"❌ Advertisement 실패: {e}")
        )
    
    def gatt_fail(e):
        print(f"❌ GATT 등록 실패: {e}")
    
    gatt_manager.RegisterApplication(
        app.get_path(), {},
        reply_handler=gatt_ok,
        error_handler=gatt_fail
    )
    
    print("🔥 BLE → SPI + MP3 + OpenCM 매크로 Server Running...")
    loop.run()


if __name__ == "__main__":
    main()
