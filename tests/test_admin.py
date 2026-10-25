"""Regression tests for admin donation verification.

Run with: python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'unit-test-secret-not-for-production')

from app import create_app
from models import DonationItem, User, VerificationLog, db
from werkzeug.security import generate_password_hash


class AdminVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'admin-test.db'
        self.app = create_app({
            'TESTING': True,
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'unit-test-secret-not-for-production',
            'SQLALCHEMY_DATABASE_URI': f'sqlite:///{self.db_path.as_posix()}',
            'UPLOAD_FOLDER': str(Path(self.temp_dir.name) / 'uploads'),
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.admin_user = User(name='Admin Test', email='admin@example.test',
                               password_hash=generate_password_hash('long-test-password'), role='admin')
        self.donor = User(name='Donor Test', email='donor@example.test',
                          password_hash=generate_password_hash('long-test-password'), role='donor')
        db.session.add_all([self.admin_user, self.donor])
        db.session.commit()
        self.client = self.app.test_client()
        self.login_as(self.admin_user)

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def login_as(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.user_id)
            sess['_fresh'] = True

    def make_item(self, status='pending', category='goods'):
        item = DonationItem(donor_id=self.donor.user_id, item_name='Warm blankets',
                            category=category, status=status)
        db.session.add(item)
        db.session.commit()
        return item

    def test_admin_dashboard_has_real_stats_and_queue(self):
        self.make_item()
        response = self.client.get('/admin/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Pending donations', response.data)
        self.assertIn(b'Warm blankets', response.data)

    def test_admin_can_verify_pending_donation_and_log_decision(self):
        item = self.make_item()
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={
            'decision': 'verify', 'remarks': 'Item details reviewed.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'verified')
        log = VerificationLog.query.one()
        self.assertEqual(log.verified_by, self.admin_user.user_id)
        self.assertEqual(log.remarks, 'Item details reviewed.')

    def test_admin_can_reject_pending_donation_and_log_decision(self):
        item = self.make_item()
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={
            'decision': 'reject', 'remarks': 'Insufficient details.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'rejected')
        self.assertEqual(VerificationLog.query.one().remarks, 'Insufficient details.')

    def test_processed_donation_cannot_be_reviewed_again(self):
        item = self.make_item(status='verified')
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={'decision': 'reject'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'verified')
        self.assertEqual(VerificationLog.query.count(), 0)

    def test_invalid_decision_does_not_change_donation(self):
        item = self.make_item()
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={'decision': 'delete'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'pending')
        self.assertEqual(VerificationLog.query.count(), 0)

    def test_non_admin_cannot_review_donation(self):
        item = self.make_item()
        self.login_as(self.donor)
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={'decision': 'verify'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'pending')

    def test_expired_medicine_cannot_be_verified(self):
        from datetime import date, timedelta
        item = self.make_item(category='medicine')
        item.expiry_date = date.today() - timedelta(days=1)
        db.session.commit()
        response = self.client.post(f'/admin/donations/{item.item_id}/review', data={'decision': 'verify'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'pending')
        self.assertEqual(VerificationLog.query.count(), 0)


if __name__ == '__main__':
    unittest.main()
