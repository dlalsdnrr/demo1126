#!/usr/bin/env python3
"""
라즈베리파이에서 실행할 MP3 재생 서버
Flask 서버로 MP3 재생 요청을 받아서 mpg123로 재생합니다.
"""

from flask import Flask, request, jsonify
import subprocess
import os
import threading

app = Flask(__name__)

# MP3 파일이 저장된 디렉토리
MP3_DIR = "/home/raspberry"

def play_mp3(filename: str):
    """mpg123를 사용하여 MP3 파일을 재생합니다"""
    filepath = os.path.join(MP3_DIR, filename)
    
    if not os.path.exists(filepath):
        print(f"❌ MP3 파일 없음: {filepath}")
        return False
    
    # 기존 재생 중인 mpg123 프로세스 종료
    try:
        subprocess.call(["pkill", "-f", "mpg123"], stderr=subprocess.DEVNULL)
    except:
        pass
    
    # MP3 재생 (비동기)
    try:
        print(f"🎧 MP3 재생 시작: {filename}")
        subprocess.Popen(["mpg123", "-a", "hw:0,0", filepath], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"✗ MP3 재생 실패: {e}")
        return False

@app.route("/play", methods=["POST"])
def play():
    """MP3 재생 요청을 받습니다"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "JSON 데이터 없음"}), 400
        
        filename = data.get("filename")
        if not filename:
            return jsonify({"ok": False, "error": "filename 파라미터 없음"}), 400
        
        # MP3 재생
        success = play_mp3(filename)
        
        if success:
            return jsonify({"ok": True, "filename": filename})
        else:
            return jsonify({"ok": False, "error": "MP3 재생 실패"}), 500
            
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    """서버 상태 확인"""
    return jsonify({"ok": True, "status": "running"})

if __name__ == "__main__":
    print("🎵 라즈베리파이 MP3 재생 서버 시작")
    print(f"📁 MP3 디렉토리: {MP3_DIR}")
    print("🌐 서버 주소: http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, debug=False)

