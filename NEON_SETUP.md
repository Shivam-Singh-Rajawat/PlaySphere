# PlaySphere + Neon Lakebase Postgres

This project keeps its existing **FastAPI + SQLAlchemy + psycopg 3** backend. Neon provisions
Postgres; it does **not** replace PlaySphere's FastAPI API, existing app authentication, or
Cloudinary video storage. The Neon `production` branch is a **database branch**, not a Git branch.

## CLI initialization (already scaffolded)

```powershell
npm i -g neon@latest
neon init -y --org-id org-cool-rain-92079554 --project-id aged-base-59831625 --branch production --services postgres
```

The generated `neon.ts` declares standard Postgres with Neon Auth disabled; PlaySphere already
has its own login and permissions. The generated `.neon` and all `.env*` credential files are
excluded from Git.

## Required human sign-in, deploy and env pull

```powershell
neon login
# Finish the sign-in in your browser, then return to the terminal.
neon config plan
neon deploy
# If needed:
neon env pull --service postgres
```

The CLI should write the pooled `DATABASE_URL` and direct `DATABASE_URL_UNPOOLED` to
`.env.local` (or `.env` if it exists). **Never commit or paste either connection string.**
You can check that the variables exist without printing their values. For a live app, use
the pooled URL. For future schema migrations (Alembic), use a direct/unpooled connection.

PlaySphere loads `.env.local` and `.env` in local development. Actual shell/process env
variables take precedence, then `.env.local`, then `.env`. The app accepts the Neon-managed
`DATABASE_URL` automatically, but an explicit `PLAYSPHERE_DATABASE_URL` overrides it.
Remove any old SQLite override before testing Neon. Vercel never loads local env files.

## Build and verify

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm ci
npm run build
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe scripts/smoke_neon.py
```

`npm run build` checks the static assets, JavaScript syntax, Python syntax, and deployment
config: this is a **Python app with unbundled HTML/CSS/JS**, not a React/Next.js build.
The smoke script requires a live Postgres URL. It verifies actual database operations via
FastAPI (registration, profile, achievement, tournament, registration) and cleans its
temporary records. It does not print secrets.

To run the site with Neon:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Visit http://127.0.0.1:8000, http://127.0.0.1:8000/api/ready and
http://127.0.0.1:8000/api/docs.

## Deploy to Vercel

Use root `./`, FastAPI/Python, default build/output settings. Set in Vercel **Production**
(or separate Preview data for Preview):

- `PLAYSPHERE_DATABASE_URL` — Neon **pooled** URL copied directly into the Vercel dashboard
  (or set `DATABASE_URL`; do not set both to different databases).
- `PLAYSPHERE_SECRET_KEY` — one stable secret (32+ random characters).
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` —
  required only for actual cloud video uploads.

No SQLite database or user-uploaded file can persist inside a Vercel Function. Do not
deploy with the placeholder `.env.example` credentials. Verify the live /api/ready route
and run role-specific user flows before treating production as ready.

## Operational caveats

Existing models are bootstrapped with `create_all` at startup for an empty database; that
does not perform migrations on an existing schema. Add Alembic before evolving the
production schema. Cloudinary is a separate service and is not validated by Neon smoke
tests. Never expose database credentials in source, browser JavaScript or logs.
