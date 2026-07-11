"""
Hubtel Online Checkout API
===========================
Endpoint: https://payproxyapi.hubtel.com/items/initiate
Docs: https://developers.hubtel.com/docs/online-checkout-payments

This uses the Onsite Checkout (checkoutDirectUrl) so payment
happens embedded on your page without a full redirect.
"""

import requests
import secrets
import base64
from flask import current_app


def _get_auth_header():
    client_id = current_app.config['HUBTEL_CLIENT_ID']
    client_secret = current_app.config['HUBTEL_CLIENT_SECRET']
    credentials = f"{client_id}:{client_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
    }


def initiate_momo_payment(amount, phone, network, reference,
                           description, customer_name, customer_email):
    merchant_account = current_app.config['HUBTEL_MERCHANT_ACCOUNT']
    callback_url = current_app.config['HUBTEL_CALLBACK_URL']
    return_url = current_app.config.get('APP_URL', callback_url)

    payload = {
        'totalAmount': amount,
        'description': description,
        'callbackUrl': callback_url,
        'returnUrl': return_url + '/payment/success-redirect',
        'merchantAccountNumber': merchant_account,
        'cancellationUrl': return_url + '/payment/cancelled',
        'clientReference': reference,
        'payeeName': customer_name,
        'payeeMobileNumber': phone,
        'payeeEmail': customer_email,
    }

    url = 'https://payproxyapi.hubtel.com/items/initiate'
    headers = _get_auth_header()

    print("=== HUBTEL REQUEST ===")
    print("URL:", url)
    print("Payload:", payload)

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        print("=== HUBTEL RESPONSE ===")
        print("Status:", response.status_code)
        print("Body:", response.text[:500])

        if not response.text:
            return {'success': False, 'message': 'Hubtel returned empty response.'}

        data = response.json()
        response_code = str(data.get('responseCode', ''))

        if response_code == '0000':
            checkout_data = data.get('data', {})
            return {
                'success': True,
                'checkout_url': checkout_data.get('checkoutUrl', ''),
                'checkout_direct_url': checkout_data.get('checkoutDirectUrl', ''),
                'checkout_id': checkout_data.get('checkoutId', ''),
                'reference': reference,
                'message': 'Checkout initiated successfully.'
            }

        msg = data.get('message') or data.get('status') or f'Hubtel error (code: {response_code})'
        return {'success': False, 'message': msg}

    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Hubtel timed out. Please try again.'}
    except Exception as e:
        return {'success': False, 'message': f'Connection error: {str(e)}'}


def check_transaction_status(reference):
    """Check payment status — poll this after initiating"""
    merchant_account = current_app.config['HUBTEL_MERCHANT_ACCOUNT']
    url = f'https://api-txnstatus.hubtel.com/transactions/{merchant_account}/status'
    headers = _get_auth_header()

    try:
        response = requests.get(url, headers=headers,
                                params={'clientReference': reference}, timeout=15)
        if not response.text:
            return {'status': 'unknown'}

        data = response.json()
        status = data.get('data', {}).get('status', '').lower()

        if status == 'paid':
            return {'status': 'paid'}
        elif status == 'unpaid':
            return {'status': 'pending'}
        return {'status': 'pending'}
    except Exception as e:
        print("Status check error:", e)
        return {'status': 'unknown'}


def generate_reference():
    return f'VL-{secrets.token_hex(8).upper()}'