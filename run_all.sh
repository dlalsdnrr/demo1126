#!/bin/bash

echo "=== Starting BLE + Flask + Web UI Launcher ==="

echo "[ RESET ] Restarting bluetooth service..."
sudo systemctl restart bluetooth
sleep 1
sudo hciconfig hci0 up
sleep 1

echo "Starting BLE SPI Bridge..."
python3 /home/raspberry/baseball_robot/ble_to_spi_bridge_bluez.py &
BLE_PID=$!
sleep 2

echo "Starting Flask Server..."
cd /home/raspberry/demo/demotest1127/demo1126
/home/raspberry/baseball_robot/venv/bin/python3 app.py &
FLASK_PID=$!
sleep 2

echo "Opening Chromium..."
/usr/bin/chromium --start-fullscreen --password-store=basic http://127.0.0.1:8484 &

echo "=== All Services Started ==="
echo "BLE PID   : $BLE_PID"
echo "FLASK PID : $FLASK_PID"

