import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from models import db, User

auth = Blueprint('auth', __name__)
PUBLIC_ROLES = {'donor', 'ngo', 'hospital'}


def valid_email(email):
    return bool(email and len(email) <= 120 and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        role = (request.form.get('role') or '').strip().lower()

        if not name or len(name) > 100:
            flash('Enter a name between 1 and 100 characters.', 'danger')
            return render_template('register.html'), 400
        if not valid_email(email):
            flash('Enter a valid email address.', 'danger')
            return render_template('register.html'), 400
        if len(password) < 12 or len(password) > 128:
            flash('Password must be at least 12 characters and no more than 128 characters.', 'danger')
            return render_template('register.html'), 400
        if role not in PUBLIC_ROLES:
            flash('Choose a valid account type.', 'danger')
            return render_template('register.html'), 400
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('auth.register'))

        user = User(name=name, email=email, password_hash=generate_password_hash(password), role=role)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('auth.register'))
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        user = User.query.filter_by(email=email).first() if email else None
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=False, fresh=True)
            flash('Login successful!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            if user.role == 'donor':
                return redirect(url_for('donor.dashboard'))
            if user.role in {'ngo', 'hospital'}:
                return redirect(url_for('recipient.dashboard'))
            logout_user()
        flash('Invalid email or password.', 'danger')
        return redirect(url_for('auth.login'))
    return render_template('login.html')


@auth.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
