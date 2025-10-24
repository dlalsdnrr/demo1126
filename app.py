from __future__ import annotations

from flask import Flask

from game_routes import game_bp
from serial_api import serial_bp
from voice import voice_bp
from daum_routes import daum_bp
from macros_routes import macros_bp
from bldc_routes import bldc_bp

from config import MOTOR_ID_MAP

app = Flask(__name__)

# 블루프린트 등록
app.register_blueprint(game_bp)
app.register_blueprint(serial_bp)
app.register_blueprint(voice_bp)
app.register_blueprint(daum_bp)
app.register_blueprint(macros_bp)
app.register_blueprint(bldc_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8484, debug=True)