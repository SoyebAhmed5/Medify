"""Create an initial admin using environment-provided credentials.

Set ADMIN_NAME, ADMIN_EMAIL and ADMIN_PASSWORD before running this script.
Never commit real credentials to source control.
"""
import os
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

admin_name = os.getenv('ADMIN_NAME', 'System Admin').strip()
admin_email = os.getenv('ADMIN_EMAIL', '').strip().lower()
admin_password = os.getenv('ADMIN_PASSWORD', '')

if not admin_email or not admin_password:
    raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD environment variables first.')
if len(admin_password) < 12:
    raise SystemExit('ADMIN_PASSWORD must be at least 12 characters long.')

with app.app_context():
    if User.query.filter_by(email=admin_email).first():
        raise SystemExit('An account with ADMIN_EMAIL already exists; no changes made.')
    admin = User(name=admin_name, email=admin_email,
                 password_hash=generate_password_hash(admin_password), role='admin')
    db.session.add(admin)
    db.session.commit()
    print(f'Admin account created for {admin_email}.')
