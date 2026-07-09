from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import User, Product, Category, Order, Commission, Withdrawal
from datetime import datetime
import os
import re
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('store.index'))
        return f(*args, **kwargs)
    return decorated


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def allowed_file(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in current_app.config['ALLOWED_IMG_EXT']


def save_image(file, prefix='product'):
    filename = secure_filename(f'{prefix}-{file.filename}')
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return f'img/products/{filename}'


# ── DASHBOARD ────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'total_users': User.query.filter_by(is_admin=False).count(),
        'total_products': Product.query.count(),
        'total_orders': Order.query.filter_by(status='paid').count(),
        'total_revenue': db.session.query(db.func.sum(Order.amount)).filter_by(status='paid').scalar() or 0,
        'pending_withdrawals': Withdrawal.query.filter_by(status='pending').count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
    }
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders)


# ── CATEGORIES ───────────────────────────────────────────────────────────────
@admin_bp.route('/categories')
@admin_required
def categories():
    return render_template('admin/categories.html', categories=Category.query.all())


@admin_bp.route('/categories/create', methods=['GET', 'POST'])
@admin_required
def create_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Name required.', 'error')
            return render_template('admin/category_form.html', category=None)
        slug = slugify(name)
        if Category.query.filter_by(slug=slug).first():
            slug = f'{slug}-{Category.query.count() + 1}'
        cat = Category(name=name, slug=slug,
                       icon=request.form.get('icon', '📦').strip(),
                       description=request.form.get('description', '').strip())
        db.session.add(cat)
        db.session.commit()
        flash(f'Category "{name}" created.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', category=None)


@admin_bp.route('/categories/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_category(id):
    cat = Category.query.get_or_404(id)
    if request.method == 'POST':
        cat.name = request.form.get('name', cat.name).strip()
        cat.icon = request.form.get('icon', cat.icon).strip()
        cat.description = request.form.get('description', '').strip()
        db.session.commit()
        flash('Category updated.', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', category=cat)


@admin_bp.route('/categories/<int:id>/delete', methods=['POST'])
@admin_required
def delete_category(id):
    db.session.delete(Category.query.get_or_404(id))
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin.categories'))


# ── PRODUCTS ─────────────────────────────────────────────────────────────────
@admin_bp.route('/products')
@admin_required
def products():
    return render_template('admin/products.html',
                           products=Product.query.order_by(Product.created_at.desc()).all())


@admin_bp.route('/products/create', methods=['GET', 'POST'])
@admin_required
def create_product():
    from app.models import Subcategory
    categories = Category.query.all()
    subcategories = Subcategory.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = float(request.form.get('price', 0))
        commission_pct = float(request.form.get('referral_commission_pct', 0))

        if not name or price <= 0:
            flash('Name and price are required.', 'error')
            return render_template('admin/product_form.html', product=None, categories=categories)

        slug = slugify(name)
        if Product.query.filter_by(slug=slug).first():
            slug = f'{slug}-{Product.query.count() + 1}'

        product = Product(
            name=name, slug=slug,
            description=request.form.get('description', '').strip(),
            price=price,
            referral_commission_pct=commission_pct,
            category_id=request.form.get('category_id') or None,
            subcategory_id=request.form.get('subcategory_id') or None,
            delivery_content=request.form.get('delivery_content', '').strip(),
            is_featured=request.form.get('is_featured') == 'on',
        )

        f = request.files.get('preview_image')
        if f and f.filename and allowed_file(f.filename):
            product.preview_image = save_image(f, slug)

        db.session.add(product)
        db.session.commit()
        flash(f'Product "{name}" created.', 'success')
        return redirect(url_for('admin.products'))

    return render_template('admin/product_form.html', product=None, categories=categories, subcategories=subcategories)


@admin_bp.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    from app.models import Subcategory
    product = Product.query.get_or_404(id)
    categories = Category.query.all()
    subcategories = Subcategory.query.all()
    if request.method == 'POST':
        product.name = request.form.get('name', product.name).strip()
        product.description = request.form.get('description', '').strip()
        product.price = float(request.form.get('price', product.price))
        product.referral_commission_pct = float(request.form.get('referral_commission_pct', 0))
        product.category_id = request.form.get('category_id') or None
        product.subcategory_id = request.form.get('subcategory_id') or None
        product.delivery_content = request.form.get('delivery_content', '').strip()
        product.is_featured = request.form.get('is_featured') == 'on'
        product.is_active = request.form.get('is_active') == 'on'

        f = request.files.get('preview_image')
        if f and f.filename and allowed_file(f.filename):
            product.preview_image = save_image(f, product.slug)

        db.session.commit()
        flash('Product updated.', 'success')
        return redirect(url_for('admin.products'))
    return render_template('admin/product_form.html', product=product, categories=categories, subcategories=subcategories)


@admin_bp.route('/products/<int:id>/delete', methods=['POST'])
@admin_required
def delete_product(id):
    db.session.delete(Product.query.get_or_404(id))
    db.session.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin.products'))


# ── ORDERS ───────────────────────────────────────────────────────────────────
@admin_bp.route('/orders')
@admin_required
def orders():
    status = request.args.get('status', '')
    q = Order.query.order_by(Order.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    return render_template('admin/orders.html', orders=q.all(), status_filter=status)


@admin_bp.route('/orders/<reference>/confirm', methods=['POST'])
@admin_required
def confirm_order(reference):
    from app.blueprints.payment import fulfill_order
    order = Order.query.filter_by(reference=reference).first_or_404()
    fulfill_order(order)
    flash(f'Order {reference} confirmed.', 'success')
    return redirect(url_for('admin.orders'))


# ── WITHDRAWALS ───────────────────────────────────────────────────────────────
@admin_bp.route('/withdrawals')
@admin_required
def withdrawals():
    status = request.args.get('status', 'pending')
    return render_template('admin/withdrawals.html',
                           withdrawals=Withdrawal.query.filter_by(status=status).order_by(Withdrawal.created_at.desc()).all(),
                           status_filter=status)


@admin_bp.route('/withdrawals/<int:id>/approve', methods=['POST'])
@admin_required
def approve_withdrawal(id):
    w = Withdrawal.query.get_or_404(id)
    w.status = 'approved'
    w.processed_at = datetime.utcnow()
    w.admin_note = request.form.get('note', '')
    db.session.commit()
    flash(f'Withdrawal of GHS {w.amount:.2f} approved.', 'success')
    return redirect(url_for('admin.withdrawals'))


@admin_bp.route('/withdrawals/<int:id>/reject', methods=['POST'])
@admin_required
def reject_withdrawal(id):
    w = Withdrawal.query.get_or_404(id)
    w.user.wallet_balance += w.amount
    w.status = 'rejected'
    w.processed_at = datetime.utcnow()
    w.admin_note = request.form.get('note', 'Rejected by admin')
    db.session.commit()
    flash(f'Withdrawal rejected and GHS {w.amount:.2f} refunded.', 'info')
    return redirect(url_for('admin.withdrawals'))


# ── USERS ─────────────────────────────────────────────────────────────────────
@admin_bp.route('/users')
@admin_required
def users():
    return render_template('admin/users.html',
                           users=User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all())


# ── ADMIN ACCOUNTS (2-admin management) ──────────────────────────────────────
@admin_bp.route('/admins')
@admin_required
def admins():
    return render_template('admin/admins.html',
                           admins=User.query.filter_by(is_admin=True).all())


@admin_bp.route('/admins/promote', methods=['POST'])
@admin_required
def promote_admin():
    email = request.form.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('No user found with that email.', 'error')
    elif user.is_admin:
        flash(f'{user.name} is already an admin.', 'info')
    elif User.query.filter_by(is_admin=True).count() >= 2:
        flash('Maximum of 2 admin accounts allowed. Remove one first.', 'error')
    else:
        user.is_admin = True
        db.session.commit()
        flash(f'{user.name} promoted to admin.', 'success')
    return redirect(url_for('admin.admins'))


@admin_bp.route('/admins/<int:id>/remove', methods=['POST'])
@admin_required
def remove_admin(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash("You can't remove yourself.", 'error')
    else:
        user.is_admin = False
        db.session.commit()
        flash(f'{user.name} removed from admin.', 'success')
    return redirect(url_for('admin.admins'))


@admin_bp.route('/admins/change-password', methods=['POST'])
@admin_required
def change_password():
    current_pw = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    if not current_user.check_password(current_pw):
        flash('Current password is incorrect.', 'error')
    elif len(new_pw) < 6:
        flash('New password must be at least 6 characters.', 'error')
    else:
        current_user.set_password(new_pw)
        db.session.commit()
        flash('Password updated successfully.', 'success')
    return redirect(url_for('admin.admins'))


# ── SUBCATEGORIES ─────────────────────────────────────────────────────────────
from app.models import Subcategory

@admin_bp.route('/subcategories')
@admin_required
def subcategories():
    all_subs = Subcategory.query.order_by(Subcategory.category_id, Subcategory.name).all()
    categories = Category.query.all()
    return render_template('admin/subcategories.html', subcategories=all_subs, categories=categories)


@admin_bp.route('/subcategories/create', methods=['GET', 'POST'])
@admin_required
def create_subcategory():
    categories = Category.query.all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        if not name or not category_id:
            flash('Name and category are required.', 'error')
            return render_template('admin/subcategory_form.html', sub=None, categories=categories)

        cat = Category.query.get(category_id)
        slug = f"{cat.slug}-{slugify(name)}"
        if Subcategory.query.filter_by(slug=slug).first():
            slug = f'{slug}-{Subcategory.query.count() + 1}'

        sub = Subcategory(
            name=name, slug=slug,
            category_id=category_id,
            description=request.form.get('description', '').strip()
        )

        f = request.files.get('cover_image')
        if f and f.filename and allowed_file(f.filename):
            sub.cover_image = save_image(f, slug)

        db.session.add(sub)
        db.session.commit()
        flash(f'Subcategory "{name}" created.', 'success')
        return redirect(url_for('admin.subcategories'))
    return render_template('admin/subcategory_form.html', sub=None, categories=categories)


@admin_bp.route('/subcategories/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_subcategory(id):
    sub = Subcategory.query.get_or_404(id)
    categories = Category.query.all()
    if request.method == 'POST':
        sub.name = request.form.get('name', sub.name).strip()
        sub.category_id = request.form.get('category_id', sub.category_id)
        sub.description = request.form.get('description', '').strip()

        f = request.files.get('cover_image')
        if f and f.filename and allowed_file(f.filename):
            sub.cover_image = save_image(f, sub.slug)

        db.session.commit()
        flash('Subcategory updated.', 'success')
        return redirect(url_for('admin.subcategories'))
    return render_template('admin/subcategory_form.html', sub=sub, categories=categories)


@admin_bp.route('/subcategories/<int:id>/delete', methods=['POST'])
@admin_required
def delete_subcategory(id):
    db.session.delete(Subcategory.query.get_or_404(id))
    db.session.commit()
    flash('Subcategory deleted.', 'success')
    return redirect(url_for('admin.subcategories'))