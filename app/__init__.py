from flask import Flask, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config
import os

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'

    @login_manager.unauthorized_handler
    def unauthorized():
        # If it's an AJAX/JSON request return JSON instead of redirect
        if request.is_json or request.headers.get('Content-Type') == 'application/json':
            return jsonify({'success': False, 'message': 'Please sign in to continue.'}), 401
        return redirect(url_for('auth.login'))

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_globals():
        return {
            'APP_NAME': app.config['APP_NAME'],
            'APP_TAGLINE': app.config['APP_TAGLINE'],
        }

    from app.blueprints.auth import auth_bp
    from app.blueprints.store import store_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.payment import payment_bp
    from app.blueprints.dashboard import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(store_bp, url_prefix='/')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(payment_bp, url_prefix='/payment')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')

    return app