# Judge Q&A Cheat Sheet

## Is the data really live?

Weather and AQI are enriched from an external provider when reachable. Traffic and incident values in this hackathon build are synthetic demo feeds. The dashboard labels the distinction rather than presenting demo values as official measurements.

## Is the correlation AI-generated?

The core correlation is rule-based and deterministic. This makes the reasoning inspectable. The assistant turns the resulting dashboard state into plain language.

## How do you prevent false causality?

The correlation UI explicitly says a detected relationship is a possible link, not a confirmed cause. The system uses the phrase "monitor" rather than treating a correlation as proof.

## Where is the database?

SQLite stores citizen reports locally. The API exposes report retrieval and analytics.

## How would this scale?

SQLite can be replaced with PostgreSQL, the feed adapters can become scheduled workers, and the normalized schema can remain the contract between ingestion and analytics.

## What would you add next?

Verified city/open-data feeds, authentication and authority roles, a proper job queue, PostgreSQL/PostGIS, stronger anomaly detection, audit trails, source freshness scoring and deployment monitoring.
