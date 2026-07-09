import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── APP IDENTITY ─────────────────────────────────────────────────────────
    # Change APP_NAME here and it reflects everywhere: navbar, footer, emails, titles
    APP_NAME     = os.environ.get('APP_NAME', 'DigiStoreGH')
    APP_TAGLINE  = os.environ.get('APP_TAGLINE', "Ghana's #1 Digital Marketplace")
    APP_URL      = os.environ.get('APP_URL', 'http://localhost:5000')

    # ── SECURITY ─────────────────────────────────────────────────────────────
    SECRET_KEY   = os.environ.get('SECRET_KEY', 'change-this-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///digistore.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # ── HUBTEL PAYMENT (embedded direct debit — no redirect) ─────────────────
    # Get keys from: https://unity.hubtel.com/account/api-accounts-add
    HUBTEL_CLIENT_ID     = os.environ.get('HUBTEL_CLIENT_ID', '')
    HUBTEL_CLIENT_SECRET = os.environ.get('HUBTEL_CLIENT_SECRET', '')
    HUBTEL_MERCHANT_ACCOUNT = os.environ.get('HUBTEL_MERCHANT_ACCOUNT', '')  # HMxxxxxxxx
    HUBTEL_CALLBACK_URL  = os.environ.get('HUBTEL_CALLBACK_URL', f"{os.environ.get('APP_URL','http://localhost:5000')}/payment/callback")

    # ── UPLOADS ───────────────────────────────────────────────────────────────
    UPLOAD_FOLDER    = os.path.join(os.path.dirname(__file__), 'app', 'static', 'img', 'products')
    ALLOWED_IMG_EXT  = {'png', 'jpg', 'jpeg', 'webp'}
