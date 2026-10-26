"""Regression tests for in-app notifications."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'unit-test-secret-not-for-production')

from app import create_app
from models import ClaimRequest, DonationItem, Notification, User, db
from werkzeug.security import generate_password_hash


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            'TESTING': True, 'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'unit-test-secret-not-for-production',
            'SQLALCHEMY_DATABASE_URI': f"sqlite:///{(Path(self.temp_dir.name) / 'notifications.db').as_posix()}",
            'UPLOAD_FOLDER': str(Path(self.temp_dir.name) / 'uploads'),
        })
        self.ctx = self.app.app_context(); self.ctx.push()
        db.drop_all(); db.create_all()
        self.admin = self.make_user('Admin', 'admin@notify.test', 'admin')
        self.donor = self.make_user('Donor', 'donor@notify.test', 'donor')
        self.recipient = self.make_user('Recipient', 'ngo@notify.test', 'ngo')
        db.session.add_all([self.admin, self.donor, self.recipient]); db.session.commit()
        self.client = self.app.test_client()
        self.login_as(self.recipient)

    def make_user(self, name, email, role):
        return User(name=name, email=email, password_hash=generate_password_hash('long-test-password'), role=role)

    def login_as(self, user):
        with self.client.session_transaction() as session:
            session['_user_id'] = str(user.user_id); session['_fresh'] = True

    def tearDown(self):
        db.session.remove(); self.ctx.pop()
        with self.app.app_context():
            db.session.remove(); db.engine.dispose()
        self.temp_dir.cleanup()

    def test_claim_submission_notifies_donor(self):
        item = DonationItem(donor_id=self.donor.user_id, item_name='First aid kit', category='goods', status='verified')
        db.session.add(item); db.session.commit()
        response = self.client.post(f'/recipient/claim/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        notification = Notification.query.filter_by(user_id=self.donor.user_id, event_type='claim_requested').one()
        self.assertIn('First aid kit', notification.message)
        self.assertEqual(notification.actor_id, self.recipient.user_id)

    def test_approval_notifies_recipient_and_donor(self):
        item, claim = self.make_claim()
        self.login_as(self.admin)
        response = self.client.post(f'/admin/claims/{claim.claim_id}/review', data={'decision': 'approve'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notification.query.filter_by(user_id=self.recipient.user_id, event_type='claim_approved').count(), 1)
        self.assertEqual(Notification.query.filter_by(user_id=self.donor.user_id, event_type='claim_approved').count(), 1)

    def test_rejection_notifies_recipient(self):
        item, claim = self.make_claim()
        self.login_as(self.admin)
        self.client.post(f'/admin/claims/{claim.claim_id}/review', data={'decision': 'reject'})
        self.assertEqual(Notification.query.filter_by(user_id=self.recipient.user_id, event_type='claim_rejected').count(), 1)

    def test_fulfillment_notifies_recipient_and_donor(self):
        item, claim = self.make_claim(status='approved')
        self.login_as(self.admin)
        self.client.post(f'/admin/claims/{claim.claim_id}/fulfill', data={})
        self.assertEqual(Notification.query.filter_by(user_id=self.recipient.user_id, event_type='claim_fulfilled').count(), 1)
        self.assertEqual(Notification.query.filter_by(user_id=self.donor.user_id, event_type='donation_fulfilled').count(), 1)

    def test_user_can_mark_own_notification_read(self):
        notification = Notification(user_id=self.recipient.user_id, event_type='test', message='Hello', url_path='/recipient/dashboard')
        db.session.add(notification); db.session.commit()
        response = self.client.post(f'/notifications/{notification.notification_id}/read')
        self.assertEqual(response.status_code, 302)
        db.session.refresh(notification)
        self.assertIsNotNone(notification.read_at)

    def test_user_cannot_mark_another_users_notification_read(self):
        notification = Notification(user_id=self.donor.user_id, event_type='test', message='Private', url_path='/notifications')
        db.session.add(notification); db.session.commit()
        response = self.client.post(f'/notifications/{notification.notification_id}/read')
        self.assertEqual(response.status_code, 404)
        db.session.refresh(notification)
        self.assertIsNone(notification.read_at)

    def test_mark_all_read_only_changes_current_users_notifications(self):
        own = Notification(user_id=self.recipient.user_id, event_type='test', message='Mine')
        other = Notification(user_id=self.donor.user_id, event_type='test', message='Other')
        db.session.add_all([own, other]); db.session.commit()
        self.client.post('/notifications/read-all')
        db.session.refresh(own); db.session.refresh(other)
        self.assertIsNotNone(own.read_at)
        self.assertIsNone(other.read_at)

    def test_notification_inbox_renders(self):
        db.session.add(Notification(user_id=self.recipient.user_id, event_type='test', message='Inbox item'))
        db.session.commit()
        response = self.client.get('/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Inbox item', response.data)

    def make_claim(self, status='pending'):
        item = DonationItem(donor_id=self.donor.user_id, item_name='Bandages', category='goods', status='claimed')
        db.session.add(item); db.session.commit()
        claim = ClaimRequest(item_id=item.item_id, recipient_id=self.recipient.user_id, status=status)
        db.session.add(claim); db.session.commit()
        return item, claim


if __name__ == '__main__':
    unittest.main()
