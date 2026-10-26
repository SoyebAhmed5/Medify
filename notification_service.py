"""Small transactional helpers for in-app notifications."""
from models import Notification, db


def add_notification(user_id, event_type, message, url_path='/notifications', actor_id=None):
    """Stage a notification in the current transaction; caller commits with its event."""
    if not user_id or not message:
        return None
    notification = Notification(
        user_id=user_id, actor_id=actor_id, event_type=event_type,
        message=message[:500], url_path=url_path if url_path.startswith('/') and not url_path.startswith('//') else '/notifications',
    )
    db.session.add(notification)
    return notification
