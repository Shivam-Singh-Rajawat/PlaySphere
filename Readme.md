# ✳ PlaySphere 2.0

**Every player deserves a shot.** PlaySphere is a full-stack sports talent-discovery web application connecting players, coaches, scouts, and clubs. It replaces the original terminal-only prototype with a real web experience, relational persistence, media portfolios, tournament registration, and structured scouting workflows.

**Stack:** FastAPI · Python 3.12+ · SQLAlchemy · SQLite locally / managed PostgreSQL on Vercel · Cloudinary for direct cloud video uploads · native HTML/CSS/JavaScript. **Frontend has no build step** and is served from the same origin as the API. The UI includes an animated landing page, searchable talent directory, responsive tournament listings, modals, scouting board, and signed-in workspace.

## Deploy to Vercel

**[Follow the step-by-step Vercel deployment instructions](VERCEL_DEPLOY.md)** (Neon PostgreSQL, persistent signing key and optional Cloudinary video upload settings). `app.py` is auto-detected by Vercel. Filesystem databases and uploads are deliberately rejected in serverless mode to avoid silently losing data.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
# Important in production: set PLAYSPHERE_SECRET_KEY to a strong persistent value.
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000**. Interactive API docs: **http://127.0.0.1:8000/api/docs**.

### Explore with example content (local only)

Run `python seed_demo.py` before starting the server. This creates **fictitious**, clearly DEMO-labelled player profiles and tournaments. Demo credentials (all use `DemoPass!123`):

| Demo role | Email |
|---|---|
| Player | `demo.player1@playsphere.local` |
| Scout | `demo.scout@playsphere.local` |
| Club | `demo.club@playsphere.local` |

These accounts are intentionally for local evaluation; **never run demo seeding on a public deployment**.

## Features

| Role | Capabilities |
|---|---|
| Players | Secure registration/login; update sport, city, position, bio, and statistical profile; manage achievements and evidence links directly from the signed-in dashboard; upload MP4/WebM/MOV directly to Cloudinary on Vercel (up to 100 MB) or share HTTPS video links; control public/private video visibility; discover and register/withdraw from tournaments |
| Scouts & coaches | Browse public player portfolios and footage; save private shortlists; record and edit private four-dimension assessments (technique, teamwork, consistency, potential, each 1–5) with notes |
| Clubs & coaches | Create tournaments with sport, location, date range, capacity and registration deadline; view registrants for their events in a private organizer dashboard; use scouting tools |
| Everyone | Search public talent directory; filter events by sport and **upcoming / live / recent**; view self-reported achievements with clear verification status |

**Fairness approach:** no opaque algorithmic player ranking and no automatic selection/rejection. Every recruiter uses the same *explicit* four-dimension scoring rubric with equal weighting. Scores and subjective notes stay private to the recruiter. This improves consistency, **not a guarantee of fairness**. Achievements are **unverified** without an independent review; recruiter's real-world identity and affiliation are **not verified** in this demonstration.

## Testing

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/
python -m compileall -q app.py seed_demo.py
node --check web/app.js
```

CI runs API tests and JavaScript syntax checks on pushes and PRs. An optional Chromium browser test (`tests/browser_smoke.py`) exercises the actual FastAPI test client through a browser bridge without requiring network access. Run it after installing `playwright` and a Chromium browser. Tests use isolated, temporary SQLite databases; they check authentication and authorization, no email leakage in public portfolios, achievements, public/private videos, tournament registration, duplicate prevention, date gating, owner-only attendance, scout evaluation privacy, and shortlisting.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/players`, `GET /api/players/{id}`, `PATCH /api/players/me`
- `POST /api/videos/link`, `POST /api/videos/upload`, `GET /api/videos/{id}/file`, `DELETE /api/videos/{id}`
- `POST /api/achievements`, `DELETE /api/achievements/{id}`
- `GET /api/tournaments?status=upcoming|live|recent&limit=150`, `POST /api/tournaments`, `POST /api/tournaments/{id}/register`, `DELETE /api/tournaments/{id}/register`
- `GET /api/tournaments/me/registrations`, `GET /api/tournaments/{id}/registrations`
- `POST /api/scouting/{player_id}/evaluate`, `GET /api/scouting/my-evaluations`, `POST/DELETE /api/scouting/{player_id}/shortlist`, `GET /api/scouting/shortlist`
- `GET /api/health`, `GET /api/stats`

Auth uses a short-lived 12-hour bearer token, password PBKDF2-HMAC-SHA256 with individual salts, and role-based route checks. Uploaded videos are stored outside the public static directory under randomized server filenames. The local demo upload limit is **25 MB**; the cloud upload limit is **100 MB**; media types are checked against file headers and requests are bounded while streaming to disk. Private video files require the owner's bearer token. Only public assets appear on public player portfolios. The default database is `playsphere.db` (ignored by Git).

## Production-readiness work still needed

This is a working **web application prototype**, not a hosted, production-hardened sports recruiting service. Before opening to real users:

1. Require verified coach/scout/club affiliations, parental/guardian consent workflows for minors, and verified achievement issuance.
2. Add email verification, password reset, session revocation, rate limits, bot protection, audit logs, CSRF/XSS/security review, and a robust account deletion / data-export pathway.
3. Put uploads in object storage with signed URLs, malware/media transcoding & moderation, quota limits, and CDN; add takedown/reporting and privacy retention policies.
4. Managed PostgreSQL is required on Vercel. Add versioned migrations (Alembic), dedicated background jobs and integration monitoring before large-scale use. Set a persistent `PLAYSPHERE_SECRET_KEY` in a secrets manager and use HTTPS behind a trusted reverse proxy.
5. Verify tournament organizers and listings, moderation and reporting flows, accessibility/browser audits, and comprehensive real-user testing.

**Legacy:** `legacy/sports.py` preserves the original terminal-only coursework prototype as reference. The new entrypoint is `app.py` / `uvicorn app:app`.

## License / visuals

No license is applied by default. The CSS uses generic sport emojis and an external Unsplash photo URL as a decorative asset; its gradient background remains available if the photo fails to load. Google Fonts is optional; system font fallback is provided. No paid UI kit or copyrighted sports logo is included.
