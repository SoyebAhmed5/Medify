"""Regression tests for claim review and handover workflow.

Run with: python -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault('SECRET_KEY', 'unit-test-secret-not-for-production')

from app import create_app
from models import ClaimRequest, DonationItem, User, db
from werkzeug.security import generate_password_hash


class ClaimManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / 'claims-test.db'
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
        self.admin_user = self.make_user('Admin', 'admin@claims.test', 'admin')
        self.donor = self.make_user('Donor', 'donor@claims.test', 'donor')
        self.recipient = self.make_user('Recipient NGO', 'ngo@claims.test', 'ngo')
        db.session.add_all([self.admin_user, self.donor, self.recipient])
        db.session.commit()
        self.client = self.app.test_client()
        self.login_as(self.admin_user)
        self.item = DonationItem(donor_id=self.donor.user_id, item_name='First aid kit',
                                 category='goods', status='claimed')
        db.session.add(self.item)
        db.session.commit()
        self.claim = ClaimRequest(item_id=self.item.item_id,
                                  recipient_id=self.recipient.user_id, status='pending')
        db.session.add(self.claim)
        db.session.commit()

    def make_user(self, name, email, role):
        return User(name=name, email=email,
                    password_hash=generate_password_hash('long-test-password'), role=role)

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

    def test_admin_claim_queue_renders_pending_claim(self):
        response = self.client.get('/admin/claims')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'First aid kit', response.data)
        self.assertIn(b'Recipient NGO', response.data)

    def test_admin_can_approve_claim_and_record_reviewer(self):
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={
            'decision': 'approve', 'remarks': 'Recipient details checked.'
        })
        db.session.refresh(self.claim)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.claim.status, 'approved')
        self.assertEqual(self.claim.reviewed_by, self.admin_user.user_id)
        self.assertIsNotNone(self.claim.reviewed_at)
        self.assertEqual(self.claim.fulfillment_notes, 'Recipient details checked.')
        self.assertEqual(db.session.get(DonationItem, self.item.item_id).status, 'claimed')

    def test_admin_can_reject_claim_and_release_donation(self):
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={
            'decision': 'reject', 'remarks': 'Unable to confirm need.'
        })
        db.session.refresh(self.claim)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.claim.status, 'rejected')
        self.assertEqual(db.session.get(DonationItem, self.item.item_id).status, 'verified')

    def test_invalid_decision_does_not_change_claim(self):
        self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={'decision': 'delete'})
        db.session.refresh(self.claim)
        self.assertEqual(self.claim.status, 'pending')
        self.assertIsNone(self.claim.reviewed_at)

    def test_non_admin_cannot_review_claim(self):
        self.login_as(self.recipient)
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={'decision': 'approve'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(db.session.get(ClaimRequest, self.claim.claim_id).status, 'pending')

    def test_claim_cannot_be_reviewed_twice(self):
        self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={'decision': 'approve'})
        self.client.post(f'/admin/claims/{self.claim.claim_id}/review', data={'decision': 'reject'})
        db.session.refresh(self.claim)
        self.assertEqual(self.claim.status, 'approved')
        self.assertEqual(db.session.get(DonationItem, self.item.item_id).status, 'claimed')

    def test_approved_claim_can_be_marked_fulfilled(self):
        self.claim.status = 'approved'
        self.claim.reviewed_by = self.admin_user.user_id
        db.session.commit()
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/fulfill', data={
            'fulfillment_notes': 'Handover confirmed by recipient.'
        })
        db.session.refresh(self.claim)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.claim.status, 'fulfilled')
        self.assertIsNotNone(self.claim.fulfilled_at)
        self.assertEqual(self.claim.fulfillment_notes, 'Handover confirmed by recipient.')

    def test_pending_claim_cannot_be_marked_fulfilled(self):
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/fulfill', data={})
        db.session.refresh(self.claim)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.claim.status, 'pending')
        self.assertIsNone(self.claim.fulfilled_at)

    def test_fulfilled_claim_cannot_be_fulfilled_again(self):
        self.claim.status = 'fulfilled'
        db.session.commit()
        response = self.client.post(f'/admin/claims/{self.claim.claim_id}/fulfill', data={})
        db.session.refresh(self.claim)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.claim.status, 'fulfilled')


if __name__ == '__main__':
    unittest.main()
