#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import dbus, dbus.exceptions, dbus.mainloop.glib, dbus.service
from gi.repository import GLib
import subprocess, time, os, spidev, json, glob
import threading

# 시리얼 포트 자동 검색을 위한 import
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


# --------------------------------------------------
# UUID
# --------------------------------------------------
SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID    = 'abcdef01-1234-5678-1234-56789abcdef0'
LOCAL_NAME   = 'kimjunha-desktop'

BLUEZ_SERVICE = 'org.bluez'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
ADV_MANAGER_IFACE  = 'org.bluez.LEAdvertisingManager1'
ADAPTER_IFACE      = 'org.bluez.Adapter1'
GATT_SERVICE_IFACE = 'org.bluez.GattService1'
GATT_CHRC_IFACE    = 'org.bluez.GattCharacteristic1'
OBJ_MANAGER_IFACE  = 'org.freedesktop.DBus.ObjectManager'


# =====================================================
# SPI → Arduino Mega
# =====================================================
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 500000

def spi_send(msg):
    try:
        packet = msg.strip() + "\n"
        spi.xfer2([ord(c) for c in packet])
        print(f"[SPI] → Arduino : {packet}")
    except Exception as e:
        print("SPI Error:", e)


# =====================================================
# OpenCM Serial (Dynamixel) - 자동 포트 검색
# =====================================================
ID_MAP = {
    "L1": 25,
    "L2": 50,
    "LE": 75,
    "R1": 100,
    "R2": 125,
    "RE": 150
}

def find_opencm_port():
    """OpenCM 시리얼 포트를 자동으로 찾습니다."""
    if serial is None or list_ports is None:
        print("❌ pyserial이 설치되지 않음")
        return None
    
    # 사용 가능한 모든 시리얼 포트 검색
    ports = list_ports.comports()
    
    # OpenCM은 보통 ttyACM 또는 ttyUSB로 연결됨
    # Linux에서는 /dev/ttyACM*, /dev/ttyUSB* 형태
    # 우선순위: ttyACM > ttyUSB
    for port in ports:
        port_name = port.device
        # Linux에서 ttyACM 또는 ttyUSB 포트 찾기
        if 'ttyACM' in port_name or 'ttyUSB' in port_name:
            try:
                # 포트가 실제로 열릴 수 있는지 테스트
                test_ser = serial.Serial(port_name, 115200, timeout=1)
                test_ser.close()
                print(f"✓ OpenCM 포트 발견: {port_name}")
                return port_name
            except (serial.SerialException, OSError):
                continue
    
    # Windows 환경 (COM 포트)
    for port in ports:
        port_name = port.device
        if port_name.startswith('COM'):
            try:
                test_ser = serial.Serial(port_name, 115200, timeout=1)
                test_ser.close()
                print(f"✓ OpenCM 포트 발견: {port_name}")
                return port_name
            except (serial.SerialException, OSError):
                continue
    
    print("❌ OpenCM 포트를 찾을 수 없음")
    return None

# 시리얼 포트 자동 검색 및 연결
opencm_port = find_opencm_port()
opencm = None

if opencm_port:
    try:
        opencm = serial.Serial(opencm_port, 115200, timeout=1)
        print(f"✓ OpenCM 연결 성공 ({opencm_port})")
        time.sleep(2)
    except Exception as e:
        opencm = None
        print(f"❌ OpenCM 연결 실패 ({opencm_port}): {e}")
else:
    print("❌ OpenCM 연결 실패 (포트를 찾을 수 없음)")


def send_opencm_command(motor_id, pos, speed):
    if opencm is None:
        print("[OpenCM ERROR] 연결되지 않음")
        return

    if motor_id not in ID_MAP:
        print(f"[OpenCM ERROR] Unknown motor_id: {motor_id}")
        return

    real_id = ID_MAP[motor_id]
    cmd = f"{real_id},{pos},{speed}\n"

    try:
        opencm.write(cmd.encode('ascii'))
        opencm.flush()
        print(f"[OpenCM →] {cmd.strip()}")
        time.sleep(0.004)
    except Exception as e:
        print("OpenCM Write Error:", e)


# =====================================================
# 매크로 로딩
# =====================================================
MACROS = {}

def load_all_macros():
    global MACROS
    MACROS = {}

    macro_dir = "/home/raspberry/baseball_robot/macros/"
    macro_files = glob.glob(macro_dir + "*.json")

    for f in macro_files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                name = os.path.basename(f).replace(".json", "")
                MACROS[name] = data["macros"]
                print(f"[MACRO] 로드됨 → {name}")
        except Exception as e:
            print("[MACRO ERROR]", f, e)

    print(f"총 {len(MACROS)}개의 매크로 로드 완료.\n")


def execute_macro(name):
    if name not in MACROS:
        print(f"[ERROR] 매크로 '{name}' 없음")
        return

    # JSON 구조에 맞는 접근 (핵심 수정)
    if name not in MACROS[name]:
        print(f"[ERROR] JSON 내부 key '{name}' 없음")
        return

    steps = MACROS[name][name]

    print(f"🔥 매크로 시작: {name}")

    for step in steps:
        motor_id = step["motor_id"]
        pos = step["position"]
        speed = step["speed"]
        delay_ms = step["delay_ms"]

        send_opencm_command(motor_id, pos, speed)

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    print(f"🏁 매크로 종료: {name}\n")


# =====================================================
# MP3 재생
# =====================================================
def play_specific_mp3(filename):
    path = f"/home/raspberry/{filename}"

    print(f"🎵 요청된 파일: {path}")

    if not os.path.exists(path):
        print("❌ MP3 파일 없음:", path)
        return

    subprocess.call(["pkill", "-f", "mpg123"])
    print(f"🎧 MP3 재생 시작 → {filename}")
    subprocess.Popen(["mpg123", "-a", "hw:0,0", path])


# =====================================================
# GATT Application
# =====================================================
class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = "/org/bluez/example"
        self.services = []
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
    def __init__(self, bus, index, uuid, service):
        self.path = f"{service.path}/char{index}"
        self.uuid = uuid
        self.service = service
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

        msg = bytes(value).decode(errors='ignore')
        cleaned = msg.replace('\x00', '').replace('\r', '').replace('\n', '').strip()
        key = cleaned.upper()

        print("===== BLE PACKET RECEIVED =====")
        print("RAW   →", repr(msg))
        print("CLEAN →", repr(key))
        print("================================\n")

        spi_send(key)

        # --- 매크로 실행 (파일명과 JSON 내부 이름을 동일하게) ---
        if key.startswith("HOMERUN"):
            play_specific_mp3("homerun.mp3")
            time.sleep(1.8)
            execute_macro("homerun")

        elif key.startswith("KIM_DOYOUNG"):
            play_specific_mp3("kimdoyoung.mp3")
            time.sleep(1.0)
            execute_macro("kimdoyoung")


        elif key.startswith("STOP"):
            execute_macro("stop")

        elif key.startswith("KIM_JICHAN"):

            # 팔 먼저 실행 (스레드)
            threading.Thread(target=execute_macro, args=("kimjichan",), daemon=True).start()

            # 0.2초 뒤 음악 시작
            time.sleep(2.0)
            play_specific_mp3("kimjichan.mp3")




        elif key.startswith("KIAOUT"):
            play_specific_mp3("biggibiggi.mp3")
            time.sleep(1.0)
            execute_macro("biggibiggi")

    @dbus.service.method(GATT_CHRC_IFACE, in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        return dbus.Array(b"SPI Ready", signature='y')


# =====================================================
# Advertisement
# =====================================================
class Advertisement(dbus.service.Object):
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


# =====================================================
# MAIN
# =====================================================
def main():
    print("📂 매크로 파일 로드 중…")
    load_all_macros()

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    adapter_path = "/org/bluez/hci0"
    adapter = bus.get_object(BLUEZ_SERVICE, adapter_path)
    props = dbus.Interface(adapter, "org.freedesktop.DBus.Properties")

    props.Set(ADAPTER_IFACE, "Powered", dbus.Boolean(1))
    props.Set(ADAPTER_IFACE, "Discoverable", dbus.Boolean(1))
    props.Set(ADAPTER_IFACE, "Pairable", dbus.Boolean(1))

    app = Application(bus)
    service = Service(bus, 0, SERVICE_UUID, True)
    ch = Characteristic(bus, 0, CHAR_UUID, service)
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
            error_handler=lambda e: print("❌ Advertisement 실패:", e)
        )

    def gatt_fail(e):
        print("❌ GATT 등록 실패:", e)

    gatt_manager.RegisterApplication(app.get_path(), {}, reply_handler=gatt_ok, error_handler=gatt_fail)

    print("🔥 BLE → SPI + MP3 + OpenCM 매크로 Server Running...")
    loop.run()


if __name__ == "__main__":
    main()

