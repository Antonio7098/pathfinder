# Demo Vulnerable Repo

This fixture is intentionally small and intentionally unsafe.

Purpose:
- produce a readable service graph
- produce a plausible attack path
- surface grounded recommendations in the dashboard

Intended services:
- `web`
- `auth`
- `billing`
- `admin`
- `shared`

Intentional weaknesses:
- hardcoded JWT secret and weak token handling
- IDOR on invoice access
- SQL built with string interpolation
- admin export endpoint gated only by a debug header

