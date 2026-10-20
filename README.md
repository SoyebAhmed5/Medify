# Medify — Medicine & Goods Donation System

A Flask web application intended to connect donors with NGOs and hospitals, with administrative review of donations.

## Current project status

This repository is a development baseline. Authentication and donor-side donation management are present. Admin verification, recipient browsing, and claim-request workflows still require implementation and testing.

## Requirements

- Python 3.10 or newer (verify against the deployment environment)
- pip and `venv`

## Local setup

### 1. Create and activate a virtual environment

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Configure secrets

Copy `.env.example` to `.env` and replace every example value with a unique value. The application does not automatically load `.env`; export environment variables in your shell or use a local environment loader. Never commit `.env` or share its contents. Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`.

### 4. Run the application

```bash
python app.py
```

Open the local URL printed by Flask. The current application creates its database tables at startup; database migrations and safe production configuration are not yet configured.

## Project layout

- `app.py` — Flask application setup and blueprint registration
- `models.py` — SQLAlchemy models
- `auth.py` — authentication routes
- `donor.py` — donor donation routes
- `recipient.py` — NGO/hospital routes
- `admin.py` — admin routes
- `templates/` — Jinja templates
- `static/` — CSS and uploaded assets
- `instance/` — local instance data, including the supplied development database

## Development notes

- Keep real secrets in environment variables; never commit `.env` files.
- Do not use the included SQLite database as a production database.
- Back up the database and uploaded files before schema or workflow changes.
- Automated tests and database migrations are not yet established.

## Security configuration (Phase 3)

Medify now requires `SECRET_KEY` to be set before startup. Copy `.env.example` to `.env` as a reference, then export the values in your shell (the app does not automatically load `.env`). Use a unique random secret and never commit it.

Example for local development:

```bash
# macOS/Linux
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export APP_ENV=development
python -m pip install -r requirements.txt
python app.py
```

On Windows PowerShell:

```powershell
$env:SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:APP_ENV = "development"
python -m pip install -r requirements.txt
python app.py
```

Public registration only permits `donor`, `ngo`, and `hospital` roles. Passwords must be 12–128 characters. All state-changing forms use CSRF tokens, including logout (now POST-only). Production deployments should set `APP_ENV=production`, use HTTPS, configure a production database, and keep secrets out of source control. Admin creation requires `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables; the password must be at least 12 characters.

Uploads are limited to 5 MB and PNG/JPEG file signatures are checked before saving. Medicine donations require a future expiry date. The donor dashboard supports search, category/status filters, and pagination. These checks reduce common input mistakes but do not replace a comprehensive medicine-safety verification process.
