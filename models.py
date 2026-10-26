from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# ---------------- USER TABLE ----------------
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'donor', 'ngo', 'hospital', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Flask-Login ko user_id chahiye 'id' naam se — isliye property banate hain
    def get_id(self):
        return str(self.user_id)


# ---------------- DONATION ITEM TABLE ----------------
class DonationItem(db.Model):
    __tablename__ = 'donation_items'

    item_id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    item_name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'medicine' or 'goods'
    expiry_date = db.Column(db.Date, nullable=True)  # goods ke liye null ho sakta hai
    image_path = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, verified, claimed, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship — donor ka data easily access karne ke liye
    donor = db.relationship('User', backref='donations')


# ---------------- CLAIM REQUEST TABLE ----------------
class ClaimRequest(db.Model):
    __tablename__ = 'claim_requests'

    claim_id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('donation_items.item_id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, fulfilled
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    fulfillment_notes = db.Column(db.Text, nullable=True)

    item = db.relationship('DonationItem', backref='claims')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='claims')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='claim_reviews')


# ---------------- VERIFICATION LOG TABLE ----------------
class VerificationLog(db.Model):
    __tablename__ = 'verification_logs'

    log_id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('donation_items.item_id'), nullable=False)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship('DonationItem', backref='verification_logs')
    admin = db.relationship('User', backref='verifications')

# ---------------- NOTIFICATION TABLE ----------------
class Notification(db.Model):
    """In-app notification owned by one user."""
    __tablename__ = 'notifications'

    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True)
    event_type = db.Column(db.String(40), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    url_path = db.Column(db.String(200), nullable=False, default='/notifications')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    actor = db.relationship('User', foreign_keys=[actor_id])
