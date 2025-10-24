# -*- coding: utf-8 -*-
# BLE → Raspberry Pi → I2C → Arduino Mega2560
# 한글(EUC-KR) 지원 완전판

from bluezero import peripheral
from smbus2 import SMBus, i2c_msg
import os
import time

# ✅ BLE 설정
SERVICE_UUID = '12345678-1234-5678-1234-56789abcdef0'
CHAR_UUID    = 'abcdef01-1234-5678-1234-56789abcdef0'
ADAPTER_ADDR = '2C:CF:67:E9:50:B5'   # hciconfig로 확인한 블루투스 MAC 주소

# ✅ I2C 설정
ARDUINO_ADDR = 0x08
bus = SMBus(1)

# BLE 데이터 캐시
last_received = "Hello from Pi"

# ✅ BLE Write 콜백 (Android → Pi)
def write_callback(value, options):
    global last_received
    try:
        # BLE에서 UTF-8로 수신
        msg = value.decode('utf-8', errors='ignore')
    except Exception:
        msg = str(value)

    print(f"[Android → Pi] {msg}")
    last_received = f"Pi received: {msg}"

    # EUC-KR로 인코딩 후 I2C로 전송
    try:
        data = list(msg.encode('euc-kr', errors='ignore'))
        if len(data) > 32:   # I2C 전송 최대 32바이트
            data = data[:32]

        write = i2c_msg.write(ARDUINO_ADDR, data)
        bus.i2c_rdwr(write)
        print(f"[Pi → Arduino] ✅ Sent (EUC-KR): {msg}")
    except Exception as e:
        print(f"[Pi → Arduino] ❌ I2C Error: {e}")

# ✅ BLE Read 콜백 (Android ← Pi)
def read_callback(options):
    print("[Android ← Pi] Android requested read")
    return last_received.encode('utf-8')

# ✅ Peripheral 생성
ble_periph = peripheral.Peripheral(ADAPTER_ADDR, local_name='kimjunha-desktop')

# ✅ 서비스 등록
ble_periph.add_service(
    srv_id=1,
    uuid=SERVICE_UUID,
    primary=True
)

# ✅ 특성 등록 (읽기/쓰기 허용)
ble_periph.add_characteristic(
    srv_id=1,
    chr_id=1,
    uuid=CHAR_UUID,
    value=bytearray(b'Hello from Pi'),
    notifying=False,
    flags=['read', 'write', 'write-without-response'],
    read_callback=read_callback,
    write_callback=write_callback
)

# ✅ 실행 준비
print("🚀 BLE ↔ I2C Bridge 실행 중...")
print(f"Adapter Address : {ADAPTER_ADDR}")
print(f"Service UUID    : {SERVICE_UUID}")
print(f"Characteristic  : {CHAR_UUID}")
print("-------------------------------------------")

# ✅ 블루투스 이름 설정
os.system("sudo bluetoothctl system-alias kimjunha-desktop > /dev/null 2>&1")

# ✅ 서비스 등록 및 광고 시작
ble_periph.publish()
time.sleep(1)
ble_periph.advertise(name='kimjunha-desktop')
print("📡 Advertising started... (Waiting for Android connection)")
print("-------------------------------------------")

# ✅ 메인 루프
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 BLE Bridge 종료 중...")
