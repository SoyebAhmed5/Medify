import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from models import db, User
from auth import auth
from donor import donor
from recipient import recipient
from admin import admin

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    is_production = os.getenv('FLASK_ENV', '').lower() == 'production' or os.getenv('APP_ENV', '').lower() == 'production'
    database_url = os.getenv('DATABASE_URL', 'sqlite:///donation.db')
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY'),
        SQLALCHEMY_DATABASE_URI=database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', str(Path(app.root_path) / 'static' / 'uploads')),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=is_production,
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=is_production,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        WTF_CSRF_TIME_LIMIT=3600,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get('SECRET_KEY'):
        if app.config.get('TESTING'):
            app.config['SECRET_KEY'] = 'test-only-secret-key'
        else:
            raise RuntimeError('SECRET_KEY must be set in the environment before starting Medify.')

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    db.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth)
    app.register_blueprint(donor)
    app.register_blueprint(recipient)
    app.register_blueprint(admin)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.route('/')
    def home():
        return redirect(url_for('auth.login'))

    @app.errorhandler(403)
    def forbidden(_error):
        return 'Access denied. You do not have permission to perform this action.', 403

    @app.errorhandler(413)
    def file_too_large(_error):
        return 'Uploaded file is too large. Maximum upload size is 5 MB.', 413

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    # Debug mode is opt-in and should remain disabled in production.
    app.run(debug=os.getenv('FLASK_DEBUG', '').lower() == 'true')
