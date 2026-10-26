"""Authenticated in-app notifications and read/unread controls."""
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import Notification, db

notifications = Blueprint('notifications', __name__, url_prefix='/notifications')
PAGE_SIZE = 20


@notifications.route('/')
@login_required
def inbox():
    from flask import request
    page = max(request.args.get('page', 1, type=int) or 1, 1)
    status = (request.args.get('status') or 'all').strip().lower()
    if status not in {'all', 'unread', 'read'}:
        status = 'all'
    query = Notification.query.filter_by(user_id=current_user.user_id)
    if status == 'unread':
        query = query.filter(Notification.read_at.is_(None))
    elif status == 'read':
        query = query.filter(Notification.read_at.is_not(None))
    pagination = query.order_by(Notification.created_at.desc(), Notification.notification_id.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )
    unread_count = Notification.query.filter_by(user_id=current_user.user_id, read_at=None).count()
    return render_template('notifications/inbox.html', notifications=pagination.items,
                           pagination=pagination, selected_status=status, unread_count=unread_count)


@notifications.route('/<int:notification_id>/open', methods=['POST'])
@login_required
def open_notification(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.user_id:
        abort(404)
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Could not mark notification %s read', notification_id)
            flash('Could not update this notification. Please try again.', 'danger')
            return redirect(url_for('notifications.inbox'))
    # Only allow local absolute paths; never redirect to an external host.
    target = notification.url_path or url_for('notifications.inbox')
    if not target.startswith('/') or target.startswith('//'):
        target = url_for('notifications.inbox')
    return redirect(target)


@notifications.route('/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_read(notification_id):
    notification = db.session.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.user_id:
        abort(404)
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Could not mark notification %s read', notification_id)
            flash('Could not update this notification. Please try again.', 'danger')
    return redirect(url_for('notifications.inbox'))


@notifications.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    try:
        Notification.query.filter_by(user_id=current_user.user_id, read_at=None).update(
            {Notification.read_at: datetime.utcnow()}, synchronize_session=False
        )
        db.session.commit()
        flash('All notifications marked as read.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Could not mark all notifications read')
        flash('Could not update notifications. Please try again.', 'danger')
    return redirect(url_for('notifications.inbox'))
