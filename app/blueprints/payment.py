from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Order, User, Commission, Product
from app.hubtel import initiate_momo_payment, check_transaction_status, generate_reference
from datetime import datetime
import traceback

payment_bp = Blueprint('payment', __name__)


def fulfill_order(order: Order):
    if order.status == 'paid':
        return

    order.status = 'paid'
    order.paid_at = datetime.utcnow()
    order.product.total_sales += 1

    buyer = User.query.get(order.user_id)

    # Grant referral slots to buyer based on purchase amount
    buyer.add_referral_slots(order.amount)

    # Find referrer — from order ref code OR buyer's referred_by relationship
    referrer = None
    if order.referral_code_used:
        referrer = User.query.filter_by(referral_code=order.referral_code_used).first()
    elif buyer.referred_by_id:
        referrer = User.query.get(buyer.referred_by_id)

    if referrer and referrer.id != buyer.id:
        commission_amount = order.product.commission_amount
        print(f'Commission: GHS{commission_amount} to {referrer.name} for order {order.reference}')

        if commission_amount > 0:
            # No duplicate commission for same order
            existing = Commission.query.filter_by(order_id=order.id).first()
            if not existing:
                commission = Commission(
                    referrer_id=referrer.id,
                    order_id=order.id,
                    amount=commission_amount,
                    percentage_used=order.product.referral_commission_pct,
                    status='pending'
                )
                referrer.wallet_balance += commission_amount
                db.session.add(commission)

                # Consume one referral slot on buyer's FIRST purchase only
                paid_count = Order.query.filter_by(
                    user_id=buyer.id, status='paid'
                ).count()
                if paid_count == 1 and referrer.referral_slots_remaining > 0:
                    referrer.referral_slots_used += 1

                print(f'Commission added. {referrer.name} wallet: GHS{referrer.wallet_balance}')

    db.session.commit()


@payment_bp.route('/initiate', methods=['POST'])
@login_required
def initiate():
    try:
        data = request.get_json(force=True, silent=True) or {}
        product_id = data.get('product_id')
        phone = str(data.get('phone', '')).strip()
        network = data.get('network', 'MTN')
        ref_code = str(data.get('ref_code', '')).strip().upper()

        product = Product.query.get(product_id)
        if not product or not product.is_active:
            return jsonify({'success': False, 'message': 'Product not found.'})

        valid_ref = None
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer and referrer.id != current_user.id:
                valid_ref = ref_code

        reference = generate_reference()

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

        result = initiate_momo_payment(
            amount=product.price,
            phone=phone,
            network=network,
            reference=reference,
            description=product.name[:50],
            customer_name=current_user.name,
            customer_email=current_user.email or f'{current_user.id}@velours.com',
        )

        if result.get('success'):
            order.hubtel_transaction_id = result.get('checkout_id', '')
            db.session.commit()
            return jsonify({
                'success': True,
                'reference': reference,
                'checkout_url': result.get('checkout_url', ''),
                'checkout_direct_url': result.get('checkout_direct_url', ''),
                'message': 'Checkout initiated.'
            })

        order.status = 'failed'
        db.session.commit()
        return jsonify({'success': False, 'message': result.get('message', 'Payment initiation failed.')})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'})


@payment_bp.route('/status/<reference>')
@login_required
def status(reference):
    order = Order.query.filter_by(reference=reference, user_id=current_user.id).first()
    if not order:
        return jsonify({'status': 'not_found'})

    if order.status == 'paid':
        return jsonify({'status': 'paid',
                        'redirect': url_for('store.payment_success', reference=reference)})

    hubtel_status = check_transaction_status(reference)
    if hubtel_status.get('status') == 'paid':
        fulfill_order(order)
        return jsonify({'status': 'paid',
                        'redirect': url_for('store.payment_success', reference=reference)})

    if order.status == 'failed':
        return jsonify({'status': 'failed'})

    return jsonify({'status': 'pending'})


@payment_bp.route('/callback', methods=['POST', 'GET'])
def callback():
    try:
        data = request.get_json(silent=True) or {}
        response_code = str(data.get('ResponseCode', ''))
        callback_data = data.get('Data', {})
        reference = callback_data.get('ClientReference', '')
        cb_status = callback_data.get('Status', '')

        print("=== CALLBACK ===", response_code, reference, cb_status)

        if reference and response_code == '0000' and cb_status.lower() == 'success':
            order = Order.query.filter_by(reference=reference).first()
            if order:
                fulfill_order(order)

        return jsonify({'status': 'received'}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error'}), 500


@payment_bp.route('/success-redirect')
def success_redirect():
    reference = request.args.get('clientReference', '')
    if reference:
        order = Order.query.filter_by(reference=reference).first()
        if order:
            fulfill_order(order)
            return redirect(url_for('store.payment_success', reference=reference))
    return redirect(url_for('store.index'))


@payment_bp.route('/cancelled')
def cancelled():
    flash('Payment was cancelled.', 'info')
    return redirect(url_for('store.shop'))


@payment_bp.route('/manual/confirm/<reference>', methods=['POST'])
@login_required
def manual_confirm(reference):
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 401
    order = Order.query.filter_by(reference=reference).first_or_404()
    fulfill_order(order)
    flash(f'Order {reference} confirmed.', 'success')
    return redirect(url_for('admin.orders'))