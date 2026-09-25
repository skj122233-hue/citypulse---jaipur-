# CityPulse Architecture

## Components

### Frontend

- HTML/CSS/JavaScript
- Leaflet for maps
- Fetch API for backend communication
- Responsive dashboard layout

### Backend

- Python
- FastAPI
- Pydantic request validation
- SQLite

### Intelligence layer

- Feed normalization
- Weighted operational score
- Rule-based correlation/anomaly checks
- Grounded natural-language response engine

## Why this architecture fits a hackathon

It is small enough for a student team to understand and debug while still demonstrating a real data flow from ingestion to decision support.

## Trust boundaries

The application distinguishes external/live enrichment from synthetic demo feeds. Correlation messages are explicitly phrased as possible relationships rather than causal claims.
