from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Order, User, Commission, Product
from app.hubtel import initiate_momo_payment, generate_reference
from datetime import datetime

payment_bp = Blueprint('payment', __name__)


def fulfill_order(order: Order):
    """Confirms payment, delivers product, fires commission, grants referral slots."""
    if order.status == 'paid':
        return

    order.status = 'paid'
    order.paid_at = datetime.utcnow()
    order.product.total_sales += 1

    buyer = User.query.get(order.user_id)

    # Grant referral slots based on purchase amount (GHS 100 = 10 slots)
    buyer.add_referral_slots(order.amount)

    # Fire commission if buyer was referred and referral code used
    if order.referral_code_used:
        referrer = User.query.filter_by(referral_code=order.referral_code_used).first()
        if referrer and referrer.id != buyer.id:
            commission_amount = order.product.commission_amount
            if commission_amount > 0:
                commission = Commission(
                    referrer_id=referrer.id,
                    order_id=order.id,
                    amount=commission_amount,
                    percentage_used=order.product.referral_commission_pct,
                    status='pending'
                )
                referrer.wallet_balance += commission_amount
                db.session.add(commission)

    db.session.commit()


@payment_bp.route('/initiate', methods=['POST'])
@login_required
def initiate():
    """Called from the embedded payment form on the product page (AJAX)."""
    data = request.get_json()
    product_id = data.get('product_id')
    phone = data.get('phone', '').strip()
    network = data.get('network', 'MTN')
    ref_code = data.get('ref_code', '').strip().upper()

    product = Product.query.get(product_id)
    if not product or not product.is_active:
        return jsonify({'success': False, 'message': 'Product not found.'})

    if not phone or len(phone) < 10:
        return jsonify({'success': False, 'message': 'Enter a valid 10-digit MoMo number.'})

    # Check referral code validity
    valid_ref = None
    if ref_code:
        referrer = User.query.filter_by(referral_code=ref_code).first()
        if referrer and referrer.can_refer and referrer.id != current_user.id:
            valid_ref = ref_code

    reference = generate_reference()

    # Create pending order
    order = Order(
        reference=reference,
        user_id=current_user.id,
        product_id=product.id,
        amount=product.price,
        status='pending',
        referral_code_used=valid_ref,
        momo_phone=phone,
        momo_network=network,
    )
    db.session.add(order)
    db.session.commit()

    # Initiate Hubtel direct debit (sends USSD prompt to user's phone)
    result = initiate_momo_payment(
        amount=product.price,
        phone=phone,
        network=network,
        reference=reference,
        description=f'{product.name} — {order.reference}',
        customer_name=current_user.name,
        customer_email=current_user.email,
    )

    if result.get('success'):
        order.hubtel_transaction_id = result.get('transaction_id', '')
        db.session.commit()
        return jsonify({
            'success': True,
            'message': result['message'],
            'reference': reference
        })

    # Initiation failed — mark order failed
    order.status = 'failed'
    db.session.commit()
    return jsonify({'success': False, 'message': result.get('message', 'Payment failed.')})


@payment_bp.route('/callback', methods=['POST', 'GET'])
def callback():
    """
    Hubtel calls this URL after payment success or failure.
    Handles both GET (redirect) and POST (webhook) from Hubtel.
    """
    data = request.get_json(silent=True) or request.args or {}

    # Hubtel sends ClientReference as the order reference
    reference = (data.get('ClientReference') or
                 data.get('Data', {}).get('ClientReference') if isinstance(data, dict) else None)

    status = (data.get('Status') or
              data.get('Data', {}).get('TransactionStatus') if isinstance(data, dict) else None)

    if reference:
        order = Order.query.filter_by(reference=reference).first()
        if order and status in ('Success', 'success', 'Successful', 'successful'):
            fulfill_order(order)
            if request.method == 'GET':
                return render_template('store/payment_success.html',
                                       order=order,
                                       product=order.product,
                                       referral_unlocked_now=True,
                                       slots_added=int(order.amount / 10))

    return jsonify({'status': 'received'}), 200


@payment_bp.route('/manual/confirm/<reference>', methods=['POST'])
def manual_confirm(reference):
    """Admin manually confirms an order (fallback)."""
    if not current_user.is_authenticated or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    order = Order.query.filter_by(reference=reference).first_or_404()
    fulfill_order(order)
    from flask import flash
    flash(f'Order {reference} confirmed and delivered.', 'success')
    return redirect(url_for('admin.orders'))
