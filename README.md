# Medify --- Medicine & Goods Donation System

Medify is a Flask-based web application that connects medicine and
general-goods donors with NGOs and hospitals. It provides an
administrator-reviewed donation marketplace, claim management,
fulfillment tracking, and in-app notifications.

> **Project purpose:** Make donation listings easier to discover and
> manage while adding an administrative review process and a traceable
> claim workflow.

## Table of Contents

-   [Key Features](#key-features)
-   [User Roles](#user-roles)
-   [Donation and Claim Workflow](#donation-and-claim-workflow)
-   [Technology Stack](#technology-stack)
-   [Project Structure](#project-structure)
-   [Getting Started](#getting-started)
-   [Environment Configuration](#environment-configuration)
-   [Creating the First Admin](#creating-the-first-admin)
-   [Running Tests](#running-tests)
-   [Database and Supabase Migration](#database-and-supabase-migration)
-   [Deployment on Render](#deployment-on-render)
-   [Health Check](#health-check)
-   [Security Notes](#security-notes)
-   [Current Scope and Limitations](#current-scope-and-limitations)

## Key Features

### Authentication and access control

-   User registration, login, and logout.
-   Supported roles: donor, NGO, hospital, and administrator.
-   Passwords are stored as hashes, not plaintext.
-   Role-based route protection.
-   CSRF protection for state-changing forms.
-   Public registration is limited to donor, NGO, and hospital roles.
    Admin accounts are created separately.

### Donor module

-   Create donation listings for medicines and general goods.
-   Edit or delete eligible pending listings.
-   View donation dashboard information and listing statuses.
-   Search listings and filter by category or status.
-   Paginate donation results.
-   Upload PNG/JPEG images, with a maximum upload size of 5 MB.
-   Validate image content/extension and use randomized upload
    filenames.
-   Require medicine expiry dates to be in the future.

### NGO and hospital module

-   Browse verified donations available in the recipient marketplace.
-   Search listings and filter by category.
-   Paginate marketplace results.
-   Exclude expired or undated medicines from the eligible marketplace.
-   Submit claim requests for available donations.
-   View claim history and statuses: pending, approved, rejected, and
    fulfilled.
-   Prevent duplicate or competing claims from reserving the same
    donation.

### Administrator module

-   View dashboard statistics for users, donations, and claims.
-   Search and filter donation listings.
-   Verify or reject pending donations, with optional remarks.
-   View donation verification history.
-   Search and filter claim requests.
-   Approve or reject pending claims.
-   Record fulfillment after handover, with optional notes.
-   Keep reviewer and review/fulfillment timestamps for claim tracking.

### In-app notifications

-   Notify donors when a donation receives a claim request.
-   Notify the donor and recipient when a claim is approved, rejected,
    or fulfilled.
-   View all, read, or unread notifications.
-   Mark one notification or all notifications as read.
-   Display an unread notification count.
-   Restrict notification access to the owning user.

### Application hardening

-   Production secret-key validation.
-   Secure session-cookie settings in production.
-   Security response headers.
-   Generic handling for unexpected server errors.
-   Database connection health check.
-   Timezone-aware UTC timestamps.
-   SQLAlchemy connection-pool pre-ping.

## User Roles

  -----------------------------------------------------------------------
  Role                                Main permissions
  ----------------------------------- -----------------------------------
  Donor                               Create and manage their eligible
                                      donation listings; view listing
                                      status and claim-related
                                      notifications.

  NGO                                 Browse verified available
                                      donations, submit claims, and track
                                      claim status.

  Hospital                            Browse verified available
                                      donations, submit claims, and track
                                      claim status.

  Admin                               Review donations, manage claim
                                      decisions, record fulfillment, and
                                      inspect review history.
  -----------------------------------------------------------------------

## Donation and Claim Workflow

``` text
Donor creates a donation listing
              |
              v
       Admin reviews it
          /       \
      Reject      Verify
                    |
                    v
        Listing appears in marketplace
                    |
                    v
          NGO / hospital claims it
                    |
                    v
           Admin reviews claim
              /          \
          Reject        Approve
            |              |
            v              v
    Donation released   Handover takes place
    for availability          |
                              v
                       Mark fulfilled
```

A verified donation is reserved when a claim is successfully submitted.
A rejected claim releases the donation back to the verified/available
state. An approved or fulfilled claim remains associated with the
claimed donation and is not returned to the marketplace.

## Technology Stack

  Layer                            Technology
  -------------------------------- ------------------------------
  Language                         Python
  Web framework                    Flask
  Authentication                   Flask-Login
  ORM / database layer             Flask-SQLAlchemy, SQLAlchemy
  Forms and CSRF                   Flask-WTF
  Database for local development   SQLite
  Hosted database                  Supabase PostgreSQL
  Templates                        Jinja2, HTML
  Styling                          CSS
  Production WSGI server           Gunicorn
  PostgreSQL driver                Psycopg 3
  Hosting                          Render
  Automated tests                  Python `unittest`

## Project Structure

``` text
Medify/
├── app.py                       # Flask app factory, configuration, health endpoint
├── models.py                    # SQLAlchemy database models
├── auth.py                      # Registration, login, logout
├── donor.py                     # Donor donation routes and image uploads
├── recipient.py                 # Recipient marketplace and claim requests
├── admin.py                     # Donation verification and claim administration
├── notifications.py             # Notification inbox and read/unread actions
├── notification_service.py      # Notification creation helpers
├── security.py                  # Shared security/validation helpers
├── time_utils.py                # UTC date/time helpers
├── create_admin.py               # Secure initial-admin creation script
├── migrate_sqlite_to_supabase.py # SQLite-to-Supabase data migration (if included)
├── requirements.txt             # Python dependencies
├── render.yaml                  # Render Blueprint configuration
├── Procfile                     # Gunicorn process declaration
├── templates/                   # Jinja2 pages
├── static/
│   ├── css/                     # Application styles
│   └── uploads/                 # Local donation images
└── tests/                       # Automated regression tests
```

Some deployment or migration files may be supplied in a separate project
package. Check the files present in your checkout before running those
optional scripts.

## Getting Started

### Prerequisites

-   Python 3.10 or later is recommended.
-   Git (if cloning the repository).
-   PowerShell on Windows, or a terminal on macOS/Linux.

### 1. Get the project

``` bash
git clone https://github.com/SoyebAhmed5/Medify.git
cd Medify
```

Alternatively, download the repository ZIP and extract it.

### 2. Create and activate a virtual environment

**Windows PowerShell**

``` powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script activation, you can use the virtual
environment's Python directly:

``` powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS / Linux**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, use `py -m pip` if `python` is not mapped to your Python
installation.

### 4. Configure environment variables

Set a development secret key before starting the application.

**Windows PowerShell**

``` powershell
$env:SECRET_KEY = (py -c "import secrets; print(secrets.token_hex(32))")
$env:APP_ENV = "development"
$env:FLASK_DEBUG = "false"
```

**macOS / Linux**

``` bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export APP_ENV=development
export FLASK_DEBUG=false
```

For local development, the application defaults to SQLite and the local
uploads directory when `DATABASE_URL` and `UPLOAD_FOLDER` are not set.

### 5. Start the application

``` bash
python app.py
```

On Windows, you can also run:

``` powershell
py app.py
```

Open the local address shown in the terminal. The usual development
address is:

**http://127.0.0.1:5000**

The home page redirects to the login page. Use the registration page to
create a donor, NGO, or hospital account.

## Environment Configuration

  -------------------------------------------------------------------------
  Variable                  Required?               Purpose
  ------------------------- ----------------------- -----------------------
  `SECRET_KEY`              Yes                     Flask session signing
                                                    and related security
                                                    features. Use a unique
                                                    random value;
                                                    production requires at
                                                    least 32 characters.

  `APP_ENV`                 For production          Set to `production` to
                                                    enable production
                                                    checks and
                                                    secure-cookie behavior.

  `FLASK_DEBUG`             No                      Set to `true` only for
                                                    local debugging. Keep
                                                    it `false` in
                                                    production.

  `DATABASE_URL`            No for local SQLite;    SQLAlchemy database
                            yes for production      connection URL.
                                                    Production must use
                                                    PostgreSQL.

  `UPLOAD_FOLDER`           No                      Directory used to store
                                                    uploaded donation
                                                    images.

  `ADMIN_NAME`              Admin creation only     Name for the initial
                                                    admin account.

  `ADMIN_EMAIL`             Admin creation only     Email for the initial
                                                    admin account.

  `ADMIN_PASSWORD`          Admin creation only     Initial admin password;
                                                    the script requires at
                                                    least 12 characters.

  `SUPABASE_DATABASE_URL`   Migration only          Supabase PostgreSQL
                                                    connection string used
                                                    by the migration
                                                    script, if included.
  -------------------------------------------------------------------------

A sample environment file may be available as `.env.example`. The
application does not rely on a committed `.env` file. Set variables in
your shell or hosting provider's environment settings.

## Creating the First Admin

Admin accounts cannot be created through public registration. To create
the first administrator, set the following environment variables in a
secure terminal:

**Windows PowerShell**

``` powershell
$env:ADMIN_NAME = "System Admin"
$env:ADMIN_EMAIL = "admin@example.com"
$env:ADMIN_PASSWORD = "Use-A-Unique-Password-At-Least-12-Chars"
py create_admin.py
```

**macOS / Linux**

``` bash
export ADMIN_NAME="System Admin"
export ADMIN_EMAIL="admin@example.com"
export ADMIN_PASSWORD="Use-A-Unique-Password-At-Least-12-Chars"
python create_admin.py
```

The script: - Requires an email and password. - Requires a password of
at least 12 characters. - Hashes the password before saving it. - Does
not overwrite an existing account with the same email.

Remove the temporary admin password from your shell/environment after
the account has been created. Never put real admin credentials in this
README or source control.

## Running Tests

Run the automated test suite from the project root:

``` bash
python -m unittest discover -s tests -v
```

On Windows:

``` powershell
py -m unittest discover -s tests -v
```

The project test suite has previously been reported as **38 passing
tests** across donor workflows, administrator verification, recipient
marketplace, claim handling, and notifications. Run the tests against
your current checkout to confirm its present status.

## Database and Supabase Migration

For local development, Medify uses SQLite. The hosted configuration is
designed to connect to PostgreSQL, including a Supabase PostgreSQL
database.

If the project package includes `migrate_sqlite_to_supabase.py`, it can
copy local SQLite records to a **new, empty** Supabase database.

High-level migration process:

1.  Back up the local SQLite database.
2.  Create a Supabase project and obtain its PostgreSQL connection
    string.
3.  Install the project requirements.
4.  Set `SUPABASE_DATABASE_URL` in your local terminal.
5.  Run the migration script.
6.  Compare row counts in Supabase with the migration output.
7.  Configure Render's `DATABASE_URL` to point to the Supabase
    PostgreSQL database.

Example backup command on Windows PowerShell:

``` powershell
Copy-Item .\instance\donation.db .\instance\donation.backup.db
```

Example migration command, only if the script is present:

``` powershell
$env:SUPABASE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/postgres?sslmode=require"
py .\migrate_sqlite_to_supabase.py
```

**Important migration precautions** - Run the provided migration script
only against a new/empty target database. It refuses to import into
populated tables. - Keep the connection string private. URL-encode
reserved characters in the password when required. - The script
preserves record IDs and foreign-key relationships and leaves the SQLite
source unchanged. - The migration script copies database records only.
It does **not** transfer uploaded image files; move those separately and
preserve the paths referenced by donation records. - Do not rerun the
import against a populated database. Plan and test a separate
merge/migration process instead. - Back up production data before schema
changes.

The app currently creates missing tables at startup and contains an
additive compatibility update for certain claim-tracking columns. This
is not a full schema migration framework. For future schema evolution,
introduce reviewed Alembic/Flask-Migrate migrations and apply them as a
controlled deployment step.

## Deployment on Render

The repository includes a `render.yaml` Blueprint configuration and a
Gunicorn start command. The application requires PostgreSQL and a strong
secret key when running in production.

### 1. Connect the repository

1.  Push the reviewed project to GitHub.
2.  In Render, create a new Web Service or Blueprint deployment.
3.  Connect the Medify repository.
4.  Use the following settings if creating the service manually:

  -------------------------------------------------------------------------------------------------------------------
  Setting                             Value
  ----------------------------------- -------------------------------------------------------------------------------
  Runtime                             Python

  Build command                       `pip install -r requirements.txt`

  Start command                       `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`

  Health check path                   `/health`
  -------------------------------------------------------------------------------------------------------------------

### 2. Configure environment variables

In Render → Medify Web Service → Environment, configure:

  -----------------------------------------------------------------------
  Variable                            Value
  ----------------------------------- -----------------------------------
  `APP_ENV`                           `production`

  `FLASK_DEBUG`                       `false`

  `SECRET_KEY`                        A newly generated random secret of
                                      at least 32 characters

  `DATABASE_URL`                      Supabase PostgreSQL connection
                                      string (Session Pooler, port 5432,
                                      with SSL required)

  `UPLOAD_FOLDER`                     The upload directory on your
                                      configured persistent storage, for
                                      example `/var/data/uploads`
  -----------------------------------------------------------------------

Do not use a Supabase `service_role` API key as `DATABASE_URL`.
`DATABASE_URL` must be a PostgreSQL connection URL. Do not commit it or
paste it into public issues, screenshots, or chat.

### 3. Configure persistent image storage

Medify stores uploaded donation images on the filesystem. Render's
default filesystem is ephemeral, so uploaded images may be lost on
redeploy/restart unless persistent storage is configured.

-   Attach a Render persistent disk with mount path `/var/data` if your
    Render plan supports it, and keep `UPLOAD_FOLDER=/var/data/uploads`.
-   Alternatively, use an external object-storage service and update the
    application to store/retrieve images there.
-   If using ephemeral storage for a temporary demo, treat uploaded
    images as disposable.

Check Render's current plan and pricing limitations before selecting
persistent storage.

### 4. Deploy and verify

After saving the environment variables, deploy the service and inspect
the build/runtime logs.

Open:

``` text
https://YOUR-SERVICE-NAME.onrender.com/health
```

Expected healthy response:

``` json
{"status":"ok","database":"available"}
```

Then test the core user journeys: - Register and log in as a donor. -
Create a donation and upload an image. - Log in as admin and
verify/reject the donation. - Log in as an NGO or hospital and submit a
claim. - Review the claim as admin, then approve/reject it. - Record
fulfillment for an approved claim. - Confirm notifications and
read/unread actions work.

A successful build alone does not prove that database access, uploads,
or all user workflows are working in production.

## Health Check

The application exposes:

``` text
GET /health
```

It executes a simple database query. A healthy response is:

``` json
{"status":"ok","database":"available"}
```

If the database probe fails, the endpoint returns HTTP `503` with an
unavailable status. It does not expose database credentials or internal
exception details.

## Security Notes

-   Never commit `.env`, database backups, uploaded user images,
    passwords, or production secrets.
-   Use a unique production `SECRET_KEY` with at least 32 characters.
-   Use strong, unique account passwords.
-   Do not share demo credentials in a public README or public
    repository.
-   Restrict admin account creation and access.
-   Back up the PostgreSQL database and uploaded files independently.
-   Treat uploaded donation images and user information as private data.
-   Review applicable local laws, consent, privacy, retention, and
    medicine-handling requirements before using the system with real
    donations.

## Current Scope and Limitations

The implemented application provides listing validation, administrative
review, claim processing, fulfillment tracking, and in-app
notifications. It does not independently certify the authenticity,
medical safety, storage history, or legal eligibility of medicines.

The following features are **not confirmed as implemented** and should
be treated as future enhancements unless separately developed: - Email
or SMS notifications. - Payment processing. - Live chat. - GPS/maps and
live delivery tracking. - AI-based recommendations. - Automated medicine
authenticity checks. - QR/barcode scanning. - Advanced analytics
exports. - Pickup/delivery logistics management.

------------------------------------------------------------------------

**Repository:**
[github.com/SoyebAhmed5/Medify](https://github.com/SoyebAhmed5/Medify)

**Project:** Medify --- Medicine & Goods Donation System
