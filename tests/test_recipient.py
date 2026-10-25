"""Regression tests for recipient browsing and claim requests.

Run with: python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'unit-test-secret-not-for-production')

from app import create_app
from models import ClaimRequest, DonationItem, User, db
from werkzeug.security import generate_password_hash


class RecipientWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'recipient-test.db'
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
        password_hash = generate_password_hash('long-test-password')
        self.donor = User(name='Donor Test', email='donor-recipient@example.test', password_hash=password_hash, role='donor')
        self.ngo = User(name='NGO Test', email='ngo@example.test', password_hash=password_hash, role='ngo')
        self.hospital = User(name='Hospital Test', email='hospital@example.test', password_hash=password_hash, role='hospital')
        self.admin_user = User(name='Admin Test', email='admin-recipient@example.test', password_hash=password_hash, role='admin')
        db.session.add_all([self.donor, self.ngo, self.hospital, self.admin_user])
        db.session.commit()
        self.client = self.app.test_client()
        self.login_as(self.ngo)

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

    def make_item(self, name='Warm blankets', category='goods', status='verified', expiry_date=None):
        item = DonationItem(donor_id=self.donor.user_id, item_name=name, category=category,
                            status=status, expiry_date=expiry_date)
        db.session.add(item)
        db.session.commit()
        return item

    def test_dashboard_shows_only_available_verified_donations(self):
        available = self.make_item(name='Available blankets')
        self.make_item(name='Awaiting review', status='pending')
        self.make_item(name='Rejected item', status='rejected')
        self.make_item(name='Expired medicine', category='medicine', expiry_date=date.today() - timedelta(days=1))
        response = self.client.get('/recipient/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Available blankets', response.data)
        self.assertNotIn(b'Awaiting review', response.data)
        self.assertNotIn(b'Rejected item', response.data)
        self.assertNotIn(b'Expired medicine', response.data)
        self.assertEqual(available.status, 'verified')

    def test_ngo_can_claim_verified_donation(self):
        item = self.make_item()
        response = self.client.post(f'/recipient/claim/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'claimed')
        claim = ClaimRequest.query.one()
        self.assertEqual(claim.recipient_id, self.ngo.user_id)
        self.assertEqual(claim.status, 'pending')

    def test_hospital_can_claim_verified_donation(self):
        item = self.make_item(name='First aid supplies')
        self.login_as(self.hospital)
        response = self.client.post(f'/recipient/claim/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClaimRequest.query.one().recipient_id, self.hospital.user_id)

    def test_second_recipient_cannot_claim_already_reserved_item(self):
        item = self.make_item()
        self.client.post(f'/recipient/claim/{item.item_id}')
        self.login_as(self.hospital)
        response = self.client.post(f'/recipient/claim/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClaimRequest.query.count(), 1)
        self.assertEqual(ClaimRequest.query.one().recipient_id, self.ngo.user_id)

    def test_recipient_cannot_claim_pending_or_rejected_donation(self):
        pending = self.make_item(name='Pending box', status='pending')
        rejected = self.make_item(name='Rejected box', status='rejected')
        self.client.post(f'/recipient/claim/{pending.item_id}')
        self.client.post(f'/recipient/claim/{rejected.item_id}')
        self.assertEqual(ClaimRequest.query.count(), 0)
        self.assertEqual(db.session.get(DonationItem, pending.item_id).status, 'pending')
        self.assertEqual(db.session.get(DonationItem, rejected.item_id).status, 'rejected')

    def test_donor_cannot_access_recipient_dashboard_or_claim(self):
        item = self.make_item()
        self.login_as(self.donor)
        self.assertEqual(self.client.get('/recipient/dashboard').status_code, 403)
        self.assertEqual(self.client.post(f'/recipient/claim/{item.item_id}').status_code, 403)
        self.assertEqual(ClaimRequest.query.count(), 0)

    def test_expired_medicine_cannot_be_claimed_even_if_status_is_verified(self):
        item = self.make_item(name='Expired tablets', category='medicine',
                              expiry_date=date.today() - timedelta(days=1))
        response = self.client.post(f'/recipient/claim/{item.item_id}')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ClaimRequest.query.count(), 0)
        self.assertEqual(db.session.get(DonationItem, item.item_id).status, 'verified')

    def test_dashboard_search_filters_available_donations(self):
        self.make_item(name='Warm blankets')
        self.make_item(name='First aid supplies')
        response = self.client.get('/recipient/dashboard?q=blankets')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Warm blankets', response.data)
        self.assertNotIn(b'First aid supplies', response.data)


if __name__ == '__main__':
    unittest.main()
