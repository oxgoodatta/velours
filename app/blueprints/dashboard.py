from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Order, Commission, Withdrawal

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    orders = Order.query.filter_by(user_id=current_user.id, status='paid').order_by(Order.paid_at.desc()).all()
    commissions = Commission.query.filter_by(referrer_id=current_user.id).order_by(Commission.created_at.desc()).all()
    total_earned = sum(c.amount for c in commissions)
    return render_template('store/dashboard.html',
                           orders=orders,
                           commissions=commissions,
                           total_earned=total_earned)


@dashboard_bp.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    amount = float(request.form.get('amount', 0))
    momo_number = request.form.get('momo_number', '').strip()
    momo_network = request.form.get('momo_network', '').strip()

    if amount <= 0 or amount > current_user.wallet_balance:
        flash('Invalid withdrawal amount.', 'error')
        return redirect(url_for('dashboard.index'))

    if not momo_number or not momo_network:
        flash('Please provide MoMo number and network.', 'error')
        return redirect(url_for('dashboard.index'))

    withdrawal = Withdrawal(
        user_id=current_user.id,
        amount=amount,
        momo_number=momo_number,
        momo_network=momo_network
    )
    current_user.wallet_balance -= amount
    db.session.add(withdrawal)
    db.session.commit()
    flash(f'Withdrawal of GHS {amount:.2f} submitted. Processing within 24 hours.', 'success')
    return redirect(url_for('dashboard.index'))
