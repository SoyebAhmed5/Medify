"""Shared authorization helpers for Medify routes."""
from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def role_required(*roles):
    """Require authentication and one of the supplied application roles."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
