from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user
from app.models import Product, Category, Order

store_bp = Blueprint('store', __name__)


@store_bp.route('/')
def index():
    featured = Product.query.filter_by(is_active=True, is_featured=True).limit(6).all()
    categories = Category.query.all()
    latest = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template('store/index.html', featured=featured, categories=categories, latest=latest)


@store_bp.route('/shop')
def shop():
    category_slug = request.args.get('category')
    search = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Product.query.filter_by(is_active=True)
    cat = None

    if category_slug:
        cat = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.filter_by(category_id=cat.id)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    products = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    categories = Category.query.all()

    return render_template('store/shop.html', products=products, categories=categories,
                           current_category=cat, search=search)


@store_bp.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    ref = request.args.get('ref', '')
    return render_template('store/product.html', product=product, ref=ref)
