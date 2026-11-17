# Deploy PlaySphere on Vercel

PlaySphere is a **single-origin FastAPI + HTML/CSS/JavaScript** application. Vercel detects root `app.py` and deploys it as one Python Function; static assets mounted at `/assets` can be served via the Vercel CDN. **Do not select a Next.js preset or add an output directory.**

## 1. Prepare the two external services

### PostgreSQL — required

Create a new project at [Neon](https://neon.tech/) or another managed PostgreSQL host. Copy the **pooled** connection URI; it commonly resembles:

```text
postgresql://USERNAME:PASSWORD@HOST-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
```

Keep the username/password private. You do not have to install a local database. The backend automatically adapts `postgres://` / `postgresql://` to SQLAlchemy's `psycopg` driver.

### Cloudinary — recommended for native video uploads

Create a Cloudinary account, find **cloud name**, **API key** and **API secret**. Direct browser uploads send videos straight to Cloudinary; the API signs a per-player upload ticket, validates Cloudinary's response signature, and stores only metadata in PostgreSQL. Public videos stream from Cloudinary; private videos upload using the authenticated delivery type and are not listed on public profiles. A private video owner can request a time-limited access URL.

Cloudinary's single-request upload API supports video files up to **100 MB** in this implementation. Longer videos should be uploaded to YouTube, Vimeo or another secure host and attached as an HTTPS link. The app never sends video bytes through Vercel Functions.

## 2. Import the GitHub repository

Visit [Vercel New Project](https://vercel.com/new), import `Shivam-Singh-Rajawat/PlaySphere`, select the `main` branch, and set **Root Directory** to the repository root (`./`). **Framework:** FastAPI / auto-detected. **Build Command** and **Output Directory:** leave blank/auto.

In Project → Settings → Environment Variables add the following values, scoped to *Production* and *Preview* as appropriate:

| Key | Value |
| --- | --- |
| `PLAYSPHERE_DATABASE_URL` | Managed PostgreSQL **pooled** URI (including TLS/SSL settings) |
| `PLAYSPHERE_SECRET_KEY` | Fresh, random secret of at least 32 characters, kept stable across deployments |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret (sensitive; server-side only) |

For distinct preview environments, use a **separate preview database and Cloudinary folder/account** if you plan to test changes involving data. Do not share real production credentials with unreviewed pull-request builds.

Generate a new secret locally with `python -c "import secrets;print(secrets.token_urlsafe(48))"` and copy it directly into Vercel Settings; never commit or paste it into a chat.

Click **Deploy**. Once running, check:

- `/` — responsive animated landing page
- `/api/health` — returns `status: ok`
- `/api/ready` — confirms database access
- `/api/config` — reports `upload_mode: cloud`
- `/api/docs` — interactive FastAPI API documentation

## 3. Smoke test using new accounts

1. Register a **player** (not a demo account), create a profile, add achievement and video link.
2. Upload a small MP4 clip; confirm it appears on the public player card. Upload a private clip and confirm it does **not** appear to another visitor.
3. Register a **club**, post a future tournament and verify it is listed.
4. Log in as player, register for the tournament, log in as club and check attendees.
5. Register a **scout**, shortlist and evaluate the player.
6. Redeploy and confirm the player and tournament records **persist** (validates managed PostgreSQL).

## 4. Local development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/
uvicorn app:app --reload
```

With no database config, local mode uses SQLite; with no Cloudinary config, it stores MP4/WebM/MOV uploads on local disk (up to 25 MB). **Neither local SQLite nor local uploads is used in Vercel production.**

## Operations & honest limitations

- Models are created when a new database starts. **This is a small-app bootstrap, not a replacement for versioned schema migrations**; add Alembic before modifying a production database schema.
- Clubs, scouts and coaches can currently self-register; the app does **not** verify their identity or organization. Never label their accounts verified without a trust-review process.
- Avoid inviting minors or hosting sensitive personal videos publicly until you implement parental consent, moderation/reporting, retention, account deletion, abuse prevention, and privacy policies.
- Add password reset, email verification, rate limiting, observability, and database backups before high-traffic public launch.
- Cloudinary storage quotas, upload/streaming quotas, and PostgreSQL plan limits depend on your providers. No third-party account is created automatically.
- A client failure after uploading a Cloudinary video but before confirming the receipt may leave an orphaned asset; schedule cleanup and reconciliation before large-scale use.
