"""Recipient marketplace and claim-request workflow for NGO/hospital accounts."""
from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_, update

from models import ClaimRequest, DonationItem, db
from security import role_required

recipient = Blueprint('recipient', __name__, url_prefix='/recipient')
PAGE_SIZE = 9
REQUEST_HISTORY_LIMIT = 10


def _available_donations_query():
    """Only show verified, unclaimed donations; expired medicines are excluded."""
    return DonationItem.query.filter(
        DonationItem.status == 'verified',
        or_(
            DonationItem.category != 'medicine',
            DonationItem.expiry_date > date.today(),
        ),
    )


@recipient.route('/dashboard')
@role_required('ngo', 'hospital')
def dashboard():
    category = (request.args.get('category') or 'all').strip().lower()
    if category not in {'all', 'medicine', 'goods'}:
        category = 'all'
    search = (request.args.get('q') or '').strip()[:100]
    page = max(request.args.get('page', 1, type=int) or 1, 1)

    query = _available_donations_query()
    if category != 'all':
        query = query.filter_by(category=category)
    if search:
        query = query.filter(DonationItem.item_name.ilike(f'%{search}%'))
    pagination = query.order_by(DonationItem.created_at.desc(), DonationItem.item_id.desc()).paginate(
        page=page, per_page=PAGE_SIZE, error_out=False
    )

    my_requests_query = ClaimRequest.query.filter_by(recipient_id=current_user.user_id)
    my_requests = my_requests_query.order_by(ClaimRequest.request_date.desc()).limit(REQUEST_HISTORY_LIMIT).all()
    stats = {
        'available': _available_donations_query().count(),
        'requests': my_requests_query.count(),
        'pending': my_requests_query.filter_by(status='pending').count(),
        'approved': my_requests_query.filter_by(status='approved').count(),
    }
    return render_template(
        'recipient/dashboard.html', user=current_user, items=pagination.items,
        pagination=pagination, selected_category=category, search_query=search,
        my_requests=my_requests, stats=stats,
    )


@recipient.route('/claim/<int:item_id>', methods=['POST'])
@role_required('ngo', 'hospital')
def claim_donation(item_id):
    item = db.session.get(DonationItem, item_id)
    if item is None:
        abort(404)

    # Check the date as well as status so stale or manually altered records cannot
    # make expired medicine available to a recipient.
    if item.category == 'medicine' and (not item.expiry_date or item.expiry_date <= date.today()):
        flash('This medicine is expired or has no valid future expiry date.', 'danger')
        return redirect(url_for('recipient.dashboard'))
    if item.status != 'verified':
        flash('This donation is no longer available to claim.', 'warning')
        return redirect(url_for('recipient.dashboard'))

    # Atomically reserve the item. A concurrent recipient request can update only
    # one row from verified -> claimed, preventing two successful claims.
    try:
        result = db.session.execute(
            update(DonationItem)
            .where(DonationItem.item_id == item_id, DonationItem.status == 'verified')
            .values(status='claimed')
        )
        if result.rowcount != 1:
            db.session.rollback()
            flash('Another recipient has already requested this donation.', 'warning')
            return redirect(url_for('recipient.dashboard'))

        claim = ClaimRequest(item_id=item_id, recipient_id=current_user.user_id, status='pending')
        db.session.add(claim)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Claim request failed for donation %s', item_id)
        flash('We could not submit your request. Please try again.', 'danger')
        return redirect(url_for('recipient.dashboard'))

    flash('Request submitted. The donation is reserved while your request is pending.', 'success')
    return redirect(url_for('recipient.dashboard'))
