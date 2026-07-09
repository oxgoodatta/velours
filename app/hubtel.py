"""
Hubtel Embedded Payment Gateway
================================
Uses Hubtel's "Receive Money" (Direct Debit) API.
- User enters MoMo number + network on YOUR page (no Hubtel redirect)
- Hubtel sends USSD prompt to user's phone
- User approves on their phone
- Hubtel POSTs callback to /payment/callback
- Your system fulfills the order

API Docs: https://developers.hubtel.com
Credentials from: https://unity.hubtel.com/account/api-accounts-add
Required: HUBTEL_CLIENT_ID, HUBTEL_CLIENT_SECRET, HUBTEL_MERCHANT_ACCOUNT
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
    return {'Authorization': f'Basic {encoded}', 'Content-Type': 'application/json'}


def get_hubtel_channel(network: str) -> str:
    """Maps network name to Hubtel channel string"""
    mapping = {
        'MTN': 'mtn-gh',
        'AirtelTigo': 'aireltigo-gh',
        'Telecel': 'vodafone-gh',  # Telecel was formerly Vodafone
    }
    return mapping.get(network, 'mtn-gh')


def initiate_momo_payment(amount: float, phone: str, network: str,
                           reference: str, description: str, customer_name: str,
                           customer_email: str) -> dict:
    """
    Initiates an embedded MoMo payment via Hubtel Direct Debit.
    Sends USSD prompt to user's phone — no page redirect needed.

    Returns:
        {'success': True, 'transaction_id': '...'}  on success
        {'success': False, 'message': '...'}         on failure
    """
    merchant_account = current_app.config['HUBTEL_MERCHANT_ACCOUNT']
    callback_url = current_app.config['HUBTEL_CALLBACK_URL']

    payload = {
        'CustomerName': customer_name,
        'CustomerEmail': customer_email,
        'CustomerMsisdn': phone,           # e.g. 0241234567
        'Channel': get_hubtel_channel(network),
        'Amount': amount,
        'ClientReference': reference,
        'Description': description,
        'PrimaryCallbackUrl': callback_url,
        'SecondaryCallbackUrl': callback_url,
    }

    url = f'https://api.hubtel.com/v1/merchantaccount/merchants/{merchant_account}/receive/mobilemoney'

    try:
        response = requests.post(url, json=payload, headers=_get_auth_header(), timeout=30)
        data = response.json()

        if response.status_code in (200, 201) and data.get('ResponseCode') in ('0', 0):
            return {
                'success': True,
                'transaction_id': data.get('Data', {}).get('TransactionId', ''),
                'message': 'Payment prompt sent to your phone. Approve to complete.'
            }
        return {
            'success': False,
            'message': data.get('ResponseMessage', 'Payment initiation failed. Check your number.')
        }
    except requests.exceptions.Timeout:
        return {'success': False, 'message': 'Hubtel is taking too long. Please try again.'}
    except Exception as e:
        return {'success': False, 'message': f'Connection error: {str(e)}'}


def verify_hubtel_payment(transaction_id: str) -> dict:
    """
    Verify a transaction status by ID.
    Used for polling or manual verification.
    """
    merchant_account = current_app.config['HUBTEL_MERCHANT_ACCOUNT']
    url = f'https://api.hubtel.com/v1/merchantaccount/merchants/{merchant_account}/transactions/status/{transaction_id}'

    try:
        response = requests.get(url, headers=_get_auth_header(), timeout=15)
        data = response.json()
        status = data.get('Data', {}).get('TransactionStatus', '')

        if status == 'Success':
            return {'success': True, 'status': 'paid'}
        elif status == 'Pending':
            return {'success': False, 'status': 'pending', 'message': 'Payment still pending'}
        return {'success': False, 'status': 'failed', 'message': data.get('ResponseMessage', 'Payment failed')}
    except Exception as e:
        return {'success': False, 'status': 'error', 'message': str(e)}


def generate_reference() -> str:
    return f'DS-{secrets.token_hex(8).upper()}'
