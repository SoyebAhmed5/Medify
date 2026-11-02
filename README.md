# Medify — Medicine & Goods Donation System

A Flask application connecting donors with NGOs and hospitals, with administrative review, claim approval, fulfillment tracking, and in-app notifications.

## Features

- Role-based authentication: donor, NGO, hospital, and admin
- Donation creation, editing, validation, and secure image uploads
- Admin donation verification and audit logging
- Recipient marketplace and claim requests
- Admin claim approval/rejection and fulfillment tracking
- User-owned in-app notifications
- CSRF protection, secure cookies, security headers, and `/health` endpoint

## Local development (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
$env:SECRET_KEY = py -c "import secrets; print(secrets.token_hex(32))"
$env:APP_ENV = "development"
py app.py
```

Open the local URL printed by Flask. The local default database is SQLite. Do not use the supplied development database as a production database.

## Tests

```powershell
py -m unittest discover -s tests -v
```

## Deploy to Render

The repository includes `render.yaml`. It configures a Python web service, Gunicorn, and `/health` as the health-check path. The Blueprint intentionally does not create a paid database or persistent disk automatically.

### 1. Prepare PostgreSQL

1. In the Render Dashboard, create a Render PostgreSQL database.
2. Choose a plan appropriate for your project. Check current pricing, expiry, backup, and storage limits before choosing a free or paid plan.
3. Keep the database and web service in the same Render region.
4. Copy the database **Internal Database URL** from the database's Connect/Info area.

### 2. Connect the Git repository

1. Push the reviewed project to your Git provider (only when you are ready).
2. In Render, choose **New → Blueprint** and connect the repository containing `render.yaml`, or create a Web Service manually.
3. For a manual Web Service, use:
   - Runtime: `Python 3`
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
   - Health check path: `/health`

### 3. Set environment variables

In the Render service's Environment page, configure:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `FLASK_DEBUG` | `false` |
| `SECRET_KEY` | A unique random secret of at least 32 characters |
| `DATABASE_URL` | Render PostgreSQL **Internal Database URL** |
| `UPLOAD_FOLDER` | `/var/data/uploads` |

Generate a secret locally with `python -c "import secrets; print(secrets.token_hex(32))"`. Never paste secrets into Git, README files, screenshots, or chat.

### 4. Make uploads persistent

Render web-service filesystems are ephemeral by default. Medify stores uploaded donation images on disk, so uploads can disappear on redeploy/restart unless persistent storage is configured.

The Blueprint sets `UPLOAD_FOLDER=/var/data/uploads`. Attach a Render persistent disk with mount path `/var/data` to the web service. Persistent disks are available on compatible paid services and constrain scaling/zero-downtime behavior; check Render's current plan limitations and pricing first. Do not deploy a live donation workflow with user uploads on an ephemeral filesystem. For a free-tier demo, use a durable external object-storage service instead, or clearly treat uploads as disposable test data.

### 5. Deploy and verify

After setting the environment variables and storage, trigger the deploy. Check Render deploy logs for startup errors, then open:

`https://<your-service>.onrender.com/health`

Expected response:

```json
{"status":"ok","database":"available"}
```

Also test registration, login, donation upload, admin review, claim approval, fulfillment, and notifications using test accounts before sharing the URL.

### 6. Create the first admin account

Do not expose admin registration publicly. In the Render Dashboard, open the service Shell (or a secure one-off shell) and set `ADMIN_NAME`, `ADMIN_EMAIL`, and `ADMIN_PASSWORD` as temporary environment values, then run:

```bash
python create_admin.py
```

Use a unique password of at least 12 characters. Remove temporary admin-creation secrets from the environment after the account is created. If an account already exists for that email, the script makes no changes.

## Database and migration warning

The current application calls `db.create_all()` during startup and contains a small additive compatibility upgrade for existing claim-tracking columns. This is sufficient for a first deployment to a new empty database, but it is **not a complete database migration system**. Before future model/schema changes, introduce and review formal Alembic/Flask-Migrate migrations, back up the database, and run migrations as a controlled pre-deploy step. Do not assume `create_all()` alters existing tables.

## Data and privacy safeguards

- The included `instance/donation.db` is development data, not a production database.
- Keep production database backups and uploaded files backed up independently.
- Do not commit `.env`, database files, uploaded images, passwords, or production secrets.
- The cleaned deployment ZIP excludes the supplied development database, uploaded user images, and Python cache files. Preserve the original archive separately if you need those local assets.
- Review privacy, consent, retention, and medicine-handling requirements before accepting real donations.

## Project layout

- `app.py` — Flask application setup and health endpoint
- `models.py` — SQLAlchemy models
- `auth.py` — authentication routes
- `donor.py` — donor donation routes and uploads
- `recipient.py` — NGO/hospital marketplace and claims
- `admin.py` — admin review and fulfillment
- `notifications.py`, `notification_service.py` — notifications
- `templates/` — Jinja templates
- `static/` — CSS and upload directory
- `tests/` — automated regression tests
- `render.yaml`, `Procfile` — Render/Gunicorn deployment configuration
