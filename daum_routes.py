from __future__ import annotations

from typing import Dict, Any

from flask import Blueprint, jsonify, request
import requests
from macros_executor import run_macro_by_event_text_async, last_event_to_trigger_text


daum_bp = Blueprint("daum", __name__)


def _map_daum_to_ui(doc: Dict[str, Any]) -> Dict[str, Any]:
    away_team_name = doc.get("away", {}).get("team", {}).get("shortNameKo") or doc.get("away", {}).get("team", {}).get("shortName") or "AWAY"
    home_team_name = doc.get("home", {}).get("team", {}).get("shortNameKo") or doc.get("home", {}).get("team", {}).get("shortName") or "HOME"

    away_score = doc.get("awayScore", {})
    home_score = doc.get("homeScore", {})

    last_period = (doc.get("liveData", {}) or {}).get("ground", {}) or {}
    period_code = last_period.get("lastPeriod") or "T01"
    half = "T" if str(period_code).upper().startswith("T") else "B"
    try:
        inning_num = int(str(period_code)[1:3])
    except Exception:
        inning_num = 1

    balls = int(last_period.get("ball", 0) or 0)
    strikes = int(last_period.get("strike", 0) or 0)
    outs = int(last_period.get("out", 0) or 0)

    bases = {
        "first": bool(last_period.get("base1") or last_period.get("base1b") or last_period.get("base1B")),
        "second": bool(last_period.get("base2") or last_period.get("base2b") or last_period.get("base2B")),
        "third": bool(last_period.get("base3") or last_period.get("base3b") or last_period.get("base3B")),
    }

    fielder_keys = {
        "p": "currentPitcher", "c": "fielderC", "1b": "fielder1B", "2b": "fielder2B",
        "3b": "fielder3B", "ss": "fielderSS", "lf": "fielderLF", "cf": "fielderCF", "rf": "fielderRF"
    }

    all_players = doc.get("homePerson", []) + doc.get("awayPerson", [])
    player_map = {p["cpPersonId"]: p["nameKo"] for p in all_players if p.get("cpPersonId")}

    fielders = {}
    for pos, key in fielder_keys.items():
        player_id = last_period.get(key)
        if player_id:
            fielders[pos] = {
                "active": True,
                "name": player_map.get(player_id, "")
            }
        else:
            fielders[pos] = {"active": False, "name": ""}

    live_text = (doc.get("liveData", {}) or {}).get("liveText", [])
    last_text = live_text[-1]["text"] if isinstance(live_text, list) and live_text else ""

    return {
        "teams": {
            "away": {"name": away_team_name, "runs": int(away_score.get("run", 0) or 0), "hits": int(away_score.get("hit", 0) or 0), "errors": int(away_score.get("error", 0) or 0)},
            "home": {"name": home_team_name, "runs": int(home_score.get("run", 0) or 0), "hits": int(home_score.get("hit", 0) or 0), "errors": int(home_score.get("error", 0) or 0)},
        },
        "inning": inning_num,
        "half": half,
        "count": {"balls": min(3, balls), "strikes": min(2, strikes), "outs": min(3, outs)},
        "bases": bases,
        "fielders": fielders,
        "last_event": {"type": "live", "description": last_text},
    }


@daum_bp.route("/api/daum-state")
def api_daum_state():
    game_id = request.args.get("gameId")
    if not game_id:
        return jsonify({"error": "missing gameId"}), 400

    url = (
        "https://issue.daum.net/api/arms/SPORTS_GAME"
        f"?gameId={game_id}&detail=liveData,lineup"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        r = requests.get(url, timeout=5, headers=headers)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return jsonify({"error": "fetch_failed", "detail": str(e)}), 502

    if not isinstance(data, dict) or data.get("code") != 200:
        return jsonify({"error": "bad_response", "raw": data}), 502

    doc = data.get("document") or {}
    mapped = _map_daum_to_ui(doc)

    # 라이브 텍스트/상태로부터 이벤트 추출하여 매크로 트리거
    # 데모가 실행 중이거나 일시정지 중이면 매크로 트리거하지 않음 (순환 import 방지를 위해 함수 내부에서 import)
    try:
        from game_routes import demo_runner
        if not demo_runner.is_running:
            trigger_text = last_event_to_trigger_text(mapped.get("last_event"))
            if trigger_text:
                run_macro_by_event_text_async(trigger_text)
    except ImportError:
        # game_routes가 아직 로드되지 않은 경우 (초기화 순서 문제)
        trigger_text = last_event_to_trigger_text(mapped.get("last_event"))
        if trigger_text:
            run_macro_by_event_text_async(trigger_text)

    return jsonify(mapped)


