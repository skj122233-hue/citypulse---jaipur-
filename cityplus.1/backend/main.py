from pathlib import Path
import json
import sqlite3
import urllib.parse
import urllib.request
import os
import html
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "citypulse.db"

JAIPUR_LAT = 26.9124
JAIPUR_LON = 75.7873

app = FastAPI(
    title="CityPulse Jaipur API",
    description="Civic intelligence backend with live weather/AQI enrichment, civic reports, data fusion and analytics.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_type TEXT NOT NULL,
            area TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'medium',
            latitude REAL,
            longitude REAL,
            status TEXT NOT NULL DEFAULT 'received',
            created_at TEXT NOT NULL
        )
    """)
    # Upgrade databases created by v1/v2.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
    for name, sql in [
        ("severity", "ALTER TABLE reports ADD COLUMN severity TEXT NOT NULL DEFAULT 'medium'"),
        ("latitude", "ALTER TABLE reports ADD COLUMN latitude REAL"),
        ("longitude", "ALTER TABLE reports ADD COLUMN longitude REAL"),
    ]:
        if name not in cols:
            conn.execute(sql)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS civic_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            area TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            display_value TEXT,
            severity TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            is_live INTEGER NOT NULL DEFAULT 0
        )
    """)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(civic_data)").fetchall()}
    if "display_value" not in cols:
        conn.execute("ALTER TABLE civic_data ADD COLUMN display_value TEXT")
    if "is_live" not in cols:
        conn.execute("ALTER TABLE civic_data ADD COLUMN is_live INTEGER NOT NULL DEFAULT 0")

    count = conn.execute("SELECT COUNT(*) FROM civic_data").fetchone()[0]
    if count == 0:
        seed = [
            ("Weather", "Jaipur", "temperature", 31, "31°C", "normal", now_iso(), 0),
            ("Traffic", "Tonk Road", "congestion", 78, "78%", "medium", now_iso(), 0),
            ("Incidents", "Tonk Road", "complaints_30m", 8, "8 reports", "medium", now_iso(), 0),
            ("AQI", "Jaipur", "aqi", 118, "118", "medium", now_iso(), 0),
        ]
        conn.executemany(
            "INSERT INTO civic_data(source,area,metric,value,display_value,severity,timestamp,is_live) VALUES(?,?,?,?,?,?,?,?)",
            seed,
        )
    conn.commit()
    conn.close()


class ReportIn(BaseModel):
    issue_type: str = Field(min_length=1, max_length=60)
    area: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    severity: str = Field(default="medium", max_length=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AIRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    dashboard: Optional[dict] = None


@app.on_event("startup")
def startup():
    init_db()


def fetch_json(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, headers={"User-Agent": "CityPulse/3.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def live_weather_aqi():
    params = urllib.parse.urlencode({
        "latitude": JAIPUR_LAT,
        "longitude": JAIPUR_LON,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone": "Asia/Kolkata",
    })
    aq_params = urllib.parse.urlencode({
        "latitude": JAIPUR_LAT,
        "longitude": JAIPUR_LON,
        "current": "pm10,pm2_5,us_aqi",
        "timezone": "Asia/Kolkata",
    })
    weather_url = f"https://api.open-meteo.com/v1/forecast?{params}"
    aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?{aq_params}"
    try:
        w = fetch_json(weather_url)
        a = fetch_json(aq_url)
        wc = w.get("current", {})
        ac = a.get("current", {})
        temp = wc.get("temperature_2m")
        humidity = wc.get("relative_humidity_2m")
        wind = wc.get("wind_speed_10m")
        aqi = ac.get("us_aqi")
        return {
            "ok": True,
            "source": "Open-Meteo",
            "weather": {
                "temperature": temp,
                "humidity": humidity,
                "wind": wind,
                "condition": weather_code_label(wc.get("weather_code")),
            },
            "air_quality": {
                "aqi": aqi,
                "pm10": ac.get("pm10"),
                "pm2_5": ac.get("pm2_5"),
                "status": aqi_label(aqi),
            },
            "observed_at": wc.get("time") or ac.get("time"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "source": "demo fallback",
            "error": str(exc),
            "weather": {"temperature": 31, "humidity": 48, "wind": 14, "condition": "Clear"},
            "air_quality": {"aqi": 118, "pm10": None, "pm2_5": None, "status": "Moderate"},
            "observed_at": now_iso(),
        }


def weather_code_label(code):
    mapping = {
        0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
        81: "Rain showers", 82: "Heavy rain showers", 95: "Thunderstorm",
        96: "Thunderstorm + hail", 99: "Thunderstorm + hail",
    }
    return mapping.get(code, "Unknown")


def aqi_label(aqi):
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for sensitive groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very unhealthy"
    return "Hazardous"


def severity_from_aqi(aqi):
    if aqi is None:
        return "medium"
    if aqi <= 100:
        return "normal"
    if aqi <= 150:
        return "medium"
    return "high"


def current_reports():
    conn = db()
    rows = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_signals():
    live = live_weather_aqi()
    conn = db()
    traffic_row = conn.execute("SELECT * FROM civic_data WHERE metric='congestion' ORDER BY id DESC LIMIT 1").fetchone()
    incident_row = conn.execute("SELECT * FROM civic_data WHERE metric='complaints_30m' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()

    traffic = float(traffic_row["value"] if traffic_row else 64)
    incidents = float(incident_row["value"] if incident_row else 8)
    aqi = live["air_quality"]["aqi"] or 118
    # Transparent demo indicator: operational dashboard score, not an official city metric.
    safety = max(0, 100 - min(40, incidents * 2))
    traffic_score = max(0, 100 - traffic * 0.45)
    air_score = max(0, 100 - min(60, max(0, aqi - 50) * 0.4))
    weather_score = 90 if live["ok"] else 82
    health = round((safety * 0.30) + (traffic_score * 0.25) + (air_score * 0.25) + (weather_score * 0.20))
    return live, traffic, incidents, health


@app.get("/api/health")
def health():
    return {"status": "online", "service": "CityPulse Backend", "city": "Jaipur", "version": "3.0.0"}


@app.get("/api/dashboard")
def dashboard():
    live, traffic, incidents, health_score = build_signals()
    reports = current_reports()
    return {
        "city": "Jaipur",
        "health_score": health_score,
        "score_note": "Operational demo indicator calculated from available signals; not an official government metric.",
        "weather": live["weather"],
        "air_quality": live["air_quality"],
        "traffic": {"status": "Heavy" if traffic >= 75 else "Moderate", "congestion": round(traffic)},
        "emergency": {
            "active_alerts": 3,
            "incidents_today": int(12 + len(reports)),
            "vehicles_on_route": 8,
        },
        "reports_today": len(reports),
        "data_mode": "live-weather-aqi + synthetic-traffic-incidents",
        "last_sync": live.get("observed_at"),
    }


@app.get("/api/alerts")
def alerts():
    reports = current_reports()
    base = [
        {"id": 1, "type": "Emergency", "title": "Emergency response unit dispatched", "area": "MI Road", "severity": "high", "time": "2 min ago"},
        {"id": 2, "type": "Traffic", "title": "Road incident reported", "area": "Ajmer Road", "severity": "medium", "time": "8 min ago"},
        {"id": 3, "type": "Health", "title": "Health request received", "area": "Mansarovar", "severity": "medium", "time": "14 min ago"},
    ]
    for r in reports[:5]:
        base.insert(0, {
            "id": f"report-{r['id']}",
            "type": r["issue_type"],
            "title": f"Citizen report: {r['issue_type']}",
            "area": r["area"],
            "severity": r.get("severity", "medium"),
            "time": r["created_at"],
        })
    return {"alerts": base[:8]}


@app.get("/api/fusion")
def fusion():
    live, traffic, incidents, _ = build_signals()
    aqi = live["air_quality"]["aqi"] or 118
    feeds = [
        {"source": "Weather", "area": "Jaipur", "metric": "temperature", "value": live["weather"]["temperature"], "display_value": f"{live['weather']['temperature']}°C", "severity": "normal", "is_live": live["ok"]},
        {"source": "Traffic", "area": "Tonk Road", "metric": "congestion", "value": traffic, "display_value": f"{round(traffic)}%", "severity": "high" if traffic >= 75 else "medium", "is_live": False},
        {"source": "Incidents", "area": "Tonk Road", "metric": "complaints_30m", "value": incidents, "display_value": f"{int(incidents)} reports", "severity": "medium", "is_live": False},
        {"source": "AQI", "area": "Jaipur", "metric": "aqi", "value": aqi, "display_value": str(round(aqi)), "severity": severity_from_aqi(aqi), "is_live": live["ok"]},
    ]
    if traffic >= 70 and incidents >= 7:
        correlation = {
            "title": "Possible traffic-incident clustering",
            "area": "Tonk Road",
            "confidence": "Medium",
            "severity": "Monitor",
            "message": "Traffic congestion and incident reports are elevated in the same area. This is a possible relationship, not a confirmed cause.",
        }
    else:
        correlation = {
            "title": "No strong cross-feed anomaly detected",
            "area": "Jaipur",
            "confidence": "Within thresholds",
            "severity": "Normal",
            "message": "Current normalized signals do not cross the demo thresholds for a notable correlation.",
        }
    return {"feeds": feeds, "correlation": correlation, "window": "30 min", "pipeline": ["ingest", "normalize", "timestamp", "compare", "explain"]}


@app.get("/api/analytics")
def analytics():
    live, traffic, incidents, health_score = build_signals()
    reports = current_reports()
    by_type = {}
    by_area = {}
    for r in reports:
        by_type[r["issue_type"]] = by_type.get(r["issue_type"], 0) + 1
        by_area[r["area"]] = by_area.get(r["area"], 0) + 1
    top_area = max(by_area.items(), key=lambda x: x[1], default=("None", 0))
    return {
        "health_score": health_score,
        "traffic": round(traffic),
        "aqi": live["air_quality"]["aqi"],
        "reports_total": len(reports),
        "reports_by_type": by_type,
        "reports_by_area": by_area,
        "top_report_area": {"area": top_area[0], "count": top_area[1]},
        "method": "Rules + weighted indicators; demo civic sources are clearly labeled.",
    }


@app.get("/api/reports")
def get_reports(limit: int = Query(default=50, ge=1, le=100)):
    conn = db()
    rows = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return {"reports": [dict(r) for r in rows]}


@app.post("/api/reports")
def create_report(report: ReportIn):
    severity = report.severity.lower()
    if severity not in {"low", "medium", "high"}:
        severity = "medium"
    now = now_iso()
    conn = db()
    cur = conn.execute(
        "INSERT INTO reports(issue_type,area,description,severity,latitude,longitude,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (report.issue_type, report.area, report.description, severity, report.latitude, report.longitude, "received", now),
    )
    conn.commit()
    report_id = cur.lastrowid
    conn.close()
    return {"id": report_id, "status": "received", "message": "Civic issue recorded successfully.", "created_at": now}


@app.get("/api/report-stats")
def report_stats():
    reports = current_reports()
    by_area = {}
    for r in reports:
        by_area[r["area"]] = by_area.get(r["area"], 0) + 1
    return {"total": len(reports), "by_area": by_area}


def _reports_context():
    reports = current_reports()
    recent = reports[:8]
    return [
        {
            "id": r["id"],
            "type": r["issue_type"],
            "area": r["area"],
            "description": r["description"],
            "severity": r["severity"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in recent
    ]


def _local_ai_answer(q: str, live, traffic, incidents, health_score, fusion_data):
    """Deterministic fallback. It is deliberately transparent and grounded in current app data."""
    s = q.lower().strip()
    reports = current_reports()
    areas = sorted({r["area"] for r in reports})

    def has(*words):
        return any(w in s for w in words)

    if has("hello", "hi", "hey", "namaste", "नमस्ते"):
        return "Hi! I’m CityPulse AI. Ask me about Jaipur traffic, weather, AQI, emergencies, civic reports, power, water, parking, the city health indicator, or why an area is being monitored."

    if has("help", "what can you do", "what do you do"):
        return "I can explain the current CityPulse dashboard, find monitored areas, summarize alerts and citizen reports, explain correlations, and answer questions about weather, AQI, traffic, parking, fuel, power and water."

    if has("health score", "city health", "city score", "overall health"):
        return f"The CityPulse operational health indicator is {health_score}/100. It is a demo decision-support metric calculated from current safety, traffic, AQI and weather signals; it is not an official government score."

    if has("traffic", "jam", "congestion", "transport", "bus"):
        level = "heavy" if traffic >= 75 else "moderate" if traffic >= 45 else "light"
        return f"Traffic is {level} in the monitored mobility layer. Tonk Road is at about {round(traffic)}% congestion, with {int(incidents)} incident reports in the monitored 30-minute window. This traffic feed is currently synthetic/demo data."

    if has("weather", "temperature", "hot", "rain", "humidity", "wind"):
        w = live["weather"]
        return f"Jaipur's weather feed reports {w['temperature']}°C, {w['humidity']}% humidity, wind around {w['wind']} km/h and {str(w['condition']).lower()} conditions. Source status: {live.get('source')}."

    if has("aqi", "air quality", "pollution", "pm2", "pm10"):
        aq = live["air_quality"]
        extras = []
        if aq.get("pm2_5") is not None: extras.append(f"PM2.5 {aq['pm2_5']}")
        if aq.get("pm10") is not None: extras.append(f"PM10 {aq['pm10']}")
        extra = ("; " + ", ".join(extras)) if extras else ""
        return f"The air-quality feed reports US AQI {round(aq['aqi'] or 118)} ({aq['status']}){extra}. Source status: {live.get('source')}."

    if has("emergency", "alert", "ambulance", "fire", "police", "accident", "rescue"):
        return f"CityPulse has 3 base emergency alerts and {12 + len(reports)} incident records in the dashboard snapshot. {len(reports)} of those are citizen-submitted reports stored in SQLite."

    if has("report", "complaint", "issue", "citizen"):
        if reports:
            newest = reports[0]
            return f"There are {len(reports)} citizen reports stored. The latest is a {newest['issue_type']} report from {newest['area']}: {newest['description']}. Status: {newest['status']}."
        return "There are currently no citizen reports stored. Use Report Issue to submit one; it will be saved to SQLite and appear in the operations dashboard."

    if has("parking", "park"):
        return "The current demo mobility data shows about 64% parking availability, with C-Scheme represented on the map. Parking availability is currently synthetic/demo data."

    if has("fuel", "petrol", "diesel", "station"):
        return "The current demo mobility layer shows 18 fuel stations as open. Fuel availability is synthetic/demo data in this MVP."

    if has("power", "electricity", "outage"):
        return "The resources layer currently lists 2 power-outage areas, including a monitoring signal around Vaishali Nagar. These outage values are synthetic/demo data."

    if has("water", "supply"):
        return "The resources layer currently lists 3 water-supply notices, including a monitoring signal around Mansarovar. These notices are synthetic/demo data."

    if has("network", "internet", "connectivity"):
        return "The resources layer currently lists 1 network-connectivity issue around Kukas. This is synthetic/demo data."

    if has("why", "correlation", "related", "connection", "cause"):
        c = fusion_data["correlation"]
        return f"{c['title']} around {c['area']}. {c['message']}"

    if has("data source", "source", "where does data", "real data", "live data"):
        return "CityPulse currently combines live environmental enrichment from Open-Meteo with clearly labeled synthetic/demo traffic and incident feeds, plus citizen reports stored locally. The same normalized schema is designed for verified municipal/open-data adapters."

    # Area-aware answer for known report areas.
    area = next((a for a in areas if a.lower() in s), None)
    if area:
        count = sum(1 for r in reports if r["area"].lower() == area.lower())
        return f"For {area}, CityPulse has {count} stored citizen report(s). The map and dashboard can combine those reports with the broader civic signals."

    return "I can answer questions about traffic, weather, AQI, emergencies, citizen reports, parking, fuel, power, water, network issues, city health, data sources and civic correlations. Try: ‘Why is Tonk Road being monitored?’"


def _openai_answer(question: str, context: dict):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None, "no-key"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        instructions = (
            "You are CityPulse AI, a civic information assistant for a hackathon MVP. "
            "Answer only from the supplied CityPulse context. Never invent live facts. "
            "Clearly label synthetic/demo signals. Do not claim correlation proves causation. "
            "Be concise, practical and plain-language. If the context does not contain an answer, say so."
        )
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=f"USER QUESTION:\n{question}\n\nCITYPULSE CONTEXT:\n{json.dumps(context, ensure_ascii=False)}",
            max_output_tokens=300,
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip(), "openai"
        return None, "empty"
    except Exception as exc:
        return None, f"error:{type(exc).__name__}"


@app.post("/api/ai")
def ai(req: AIRequest):
    q = req.message.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    live, traffic, incidents, health_score = build_signals()
    fusion_data = fusion()
    context = {
        "city": "Jaipur",
        "weather": live["weather"],
        "air_quality": live["air_quality"],
        "traffic_percent": round(traffic),
        "incident_count_30m": int(incidents),
        "health_score": health_score,
        "fusion": fusion_data,
        "citizen_reports": _reports_context(),
        "dashboard_snapshot": req.dashboard or {},
    }

    answer, mode = _openai_answer(q, context)
    if answer:
        return {"answer": answer, "grounded": True, "mode": mode, "sources": ["dashboard", "civic-data", "live-weather-aqi", "citizen-reports"]}

    answer = _local_ai_answer(q, live, traffic, incidents, health_score, fusion_data)
    return {
        "answer": answer,
        "grounded": True,
        "mode": "local-civic-engine",
        "sources": ["dashboard", "civic-data", "live-weather-aqi", "citizen-reports"],
        "llm_status": mode,
    }


    q = req.message.lower().strip()
    live, traffic, incidents, health_score = build_signals()
    aqi = live["air_quality"]["aqi"] or 118
    weather = live["weather"]
    fusion_data = fusion()

    if any(x in q for x in ["traffic", "jam", "congestion", "transport"]):
        answer = f"Traffic is currently {'heavy' if traffic >= 75 else 'moderate'} in the demo mobility layer. Tonk Road is at about {round(traffic)}% congestion with {int(incidents)} incident reports in the monitored window."
    elif any(x in q for x in ["weather", "temperature", "hot", "rain"]):
        answer = f"Jaipur's weather feed reports {weather['temperature']}°C, {weather['humidity']}% humidity, wind around {weather['wind']} km/h and {weather['condition'].lower()} conditions."
    elif any(x in q for x in ["aqi", "air", "pollution"]):
        answer = f"The live air-quality feed reports a US AQI of {round(aqi)} ({live['air_quality']['status']})."
    elif any(x in q for x in ["emergency", "alert", "ambulance", "incident"]):
        answer = f"CityPulse currently shows 3 base emergency alerts and {int(12 + len(current_reports()))} incidents in the dashboard snapshot. Citizen reports are stored separately and appear in the live alert stream."
    elif any(x in q for x in ["health score", "city health", "city score"]):
        answer = f"The CityPulse operational health indicator is {health_score}/100. It is calculated from available safety, traffic, air-quality and weather signals and is not an official government score."
    elif any(x in q for x in ["why", "correlation", "related", "connection"]):
        c = fusion_data["correlation"]
        answer = f"{c['title']} around {c['area']}. {c['message']}"
    elif any(x in q for x in ["report", "issue", "complaint"]):
        answer = "Use the Report Issue button to submit a civic issue. The report is stored in SQLite and immediately becomes available to the alert and analytics endpoints."
    else:
        answer = "CityPulse combines weather/AQI enrichment, traffic and incident signals, citizen reports, anomaly rules and a map. Ask me about traffic, weather, AQI, emergencies, the city health indicator or civic correlations."
    return {"answer": answer, "grounded": True, "mode": "citypulse-civic-engine", "sources": ["dashboard", "civic-data", "live-weather-aqi"]}


# Serve the frontend from the same FastAPI process.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
