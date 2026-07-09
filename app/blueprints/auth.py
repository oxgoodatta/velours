from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('store.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        referral_code = request.form.get('referral_code', '').strip().upper()

        if not name or not email or not password:
            flash('Please fill all required fields.', 'error')
            return render_template('auth/register.html', referral_code=referral_code)

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please sign in.', 'error')
            return render_template('auth/register.html', referral_code=referral_code)

        user = User(name=name, email=email, phone=phone)
        user.set_password(password)
        user.generate_referral_code()

        # Handle referral — only if referrer has slots remaining
        if referral_code:
            referrer = User.query.filter_by(referral_code=referral_code).first()
            if referrer and referrer.can_refer and referrer.id != user.id:
                user.referred_by_id = referrer.id
                referrer.referral_slots_used += 1

        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f'Welcome to the platform, {name}!', 'success')
        return redirect(url_for('store.index'))

    referral_code = request.args.get('ref', '')
    return render_template('auth/register.html', referral_code=referral_code)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('store.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            return redirect(request.args.get('next') or url_for('store.index'))
        flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('store.index'))
