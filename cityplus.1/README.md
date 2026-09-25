# CityPulse Jaipur — Level 3 Hackathon Build

CityPulse is a civic-intelligence dashboard concept for Jaipur. This Level 3 build turns the original frontend prototype into a locally runnable full-stack MVP with:

- FastAPI backend
- SQLite persistence for citizen reports
- Interactive Leaflet map
- Live weather/AQI enrichment through Open-Meteo when the internet is available
- Clearly labeled synthetic traffic/incident feeds for the hackathon demo
- Normalized civic-data fusion pipeline
- Rule-based anomaly/correlation engine
- Backend-grounded civic assistant
- Citizen reporting with optional browser geolocation
- Analytics/operations view
- CSV export of citizen reports
- Responsive dashboard UI
- Docker and Render deployment files
- Submission/pitch documentation

## Important data note

The weather and air-quality enrichment is external data when reachable. Traffic, incident, emergency, parking, power, water and other civic values in this repository are **synthetic/demo signals** unless replaced with verified sources. Do not describe synthetic values as official live Jaipur government measurements.

The City Health score is an **operational demo indicator**, not an official government metric.

## Run locally in VS Code

### Option A — terminal

Open this folder in VS Code, then run:

```powershell
python -m pip install -r requirements.txt
python backend\main.py
```

Open:

```text
http://127.0.0.1:8000
```

### Option B — Windows one-click

Double-click:

```text
start.bat
```

### If `cd` causes errors

The terminal must be in the folder containing `requirements.txt` and the `backend` folder:

```text
CityPulse>
```

Do **not** run `cd CityPulse` if the prompt already ends in `CityPulse>`.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend health/version |
| GET | `/api/dashboard` | Unified dashboard snapshot |
| GET | `/api/alerts` | Active alerts + citizen reports |
| GET | `/api/fusion` | Normalized feeds + correlation |
| GET | `/api/analytics` | Health/traffic/AQI/report analytics |
| GET | `/api/reports` | Recent citizen reports |
| POST | `/api/reports` | Create a citizen report |
| POST | `/api/ai` | Grounded civic Q&A |

FastAPI also exposes interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Architecture

```text
                    CITYPULSE
                        |
             +----------+----------+
             |                     |
         FRONTEND               FASTAPI
       HTML/CSS/JS                  |
             |          +----------+-----------+
             |          |          |            |
          Leaflet    SQLite    Feed Enrichment  AI Engine
             |          |          |            |
             +----------+----------+------------+
                        |
                 Data Fusion Engine
                        |
             Normalize -> Timestamp
                        |
                 Compare Signals
                        |
              Anomaly/Correlation
                        |
                 Plain-language
                    explanation
```

## Data pipeline

```text
Weather/AQI -----------+
                       |
Traffic demo ----------+--> Normalize --> Timestamp --> Analyze
                       |                              |
Incident demo ---------+                              v
                                                    Insight
Citizen reports -------+                              |
                                                      +--> Dashboard
                                                      +--> Map
                                                      +--> AI assistant
```

## Level 3 features

### 1. Data fusion

Every feed is represented using a common structure such as:

```text
source
area
metric
value
severity
timestamp
is_live
```

This makes heterogeneous signals comparable.

### 2. Correlation engine

The current rule engine checks whether monitored traffic congestion and incident reports are elevated in the same zone. It deliberately reports a **possible relationship**, not causation.

### 3. Live weather/AQI enrichment

The backend requests current weather and air-quality values for Jaipur. If the external service is unavailable, the application falls back to clearly labeled demo values so the hackathon demo still works offline.

### 4. Citizen reporting

A user can submit:

- issue type
- area
- description
- severity
- optional browser coordinates

Reports are persisted in SQLite and surfaced in alerts/analytics.

### 5. Operations view

Click the **📊** button in the header to open the operations/analytics panel. It includes report counts, health/traffic/AQI indicators, recent reports, pipeline stages and CSV export.

## Deployment

### Docker

```bash
docker build -t citypulse .
docker run -p 8000:8000 citypulse
```

### Render

The repository includes `render.yaml`. Create a new Web Service from the repository and use the generated configuration.

## GitHub submission checklist

Before pushing:

- [ ] Remove any real secrets from files
- [ ] Confirm `.env` is ignored
- [ ] Run the project from a fresh terminal
- [ ] Test `/docs`
- [ ] Submit a test civic report
- [ ] Open the analytics view
- [ ] Test AI questions
- [ ] Test the map
- [ ] Take 4–6 clean screenshots
- [ ] Add the official problem statement wording to the final submission form
- [ ] Verify all team member names/IDs
- [ ] Verify the repository is accessible to judges

## Suggested 3-minute demo

1. Start on the CityPulse dashboard.
2. Point out the city health indicator and live weather/AQI provenance.
3. Switch to Transport & Traffic and show the map.
4. Open Civic Data Fusion and explain normalization.
5. Show the Tonk Road correlation and emphasize that it is a possible link, not confirmed causation.
6. Ask the assistant: `Where is traffic heavy?`
7. Submit a citizen report.
8. Open 📊 Operations and show that the report is persisted.
9. Export the report CSV.
10. Finish with the architecture: ingest → normalize → analyze → explain → act.

## Open-Meteo attribution

If live Open-Meteo data is used in the demo, retain clear attribution to Open-Meteo and the underlying CAMS data providers as required by their documentation. See `docs/SOURCES.md` for the source notes.


## AI Assistant
The AI endpoint has two modes:

1. **Local Civic Engine (default):** no API key required. It answers grounded questions from the current CityPulse data and citizen reports.
2. **OpenAI mode (optional):** set `OPENAI_API_KEY` and optionally `OPENAI_MODEL`. The backend sends a compact civic-data context to the model and explicitly instructs it not to invent facts or treat correlations as causation.

PowerShell example:
```powershell
$env:OPENAI_API_KEY="YOUR_KEY_HERE"
$env:OPENAI_MODEL="gpt-5.6-luna"
python backend\main.py
```
Never commit your API key to GitHub. Use `.env.example` as a template and keep real secrets out of source control.
