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