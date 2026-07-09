from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user
from app.models import Product, Category, Subcategory, Order

store_bp = Blueprint('store', __name__)


@store_bp.route('/')
def index():
    featured = Product.query.filter_by(is_active=True, is_featured=True).limit(6).all()
    categories = Category.query.all()
    latest = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).limit(8).all()
    return render_template('store/index.html', featured=featured, categories=categories, latest=latest)


@store_bp.route('/shop')
def shop():
    """Top level — shows all category folders"""
    categories = Category.query.all()
    return render_template('store/shop.html', categories=categories)


@store_bp.route('/shop/<cat_slug>')
def category(cat_slug):
    """Second level — shows subcategory folders inside a category"""
    cat = Category.query.filter_by(slug=cat_slug).first_or_404()
    return render_template('store/category.html', category=cat)


@store_bp.route('/shop/<cat_slug>/<sub_slug>')
def subcategory(cat_slug, sub_slug):
    """Third level — shows all products inside a subcategory"""
    cat = Category.query.filter_by(slug=cat_slug).first_or_404()
    sub = Subcategory.query.filter_by(slug=sub_slug, category_id=cat.id).first_or_404()
    page = request.args.get('page', 1, type=int)
    products = Product.query.filter_by(
        subcategory_id=sub.id, is_active=True
    ).order_by(Product.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template('store/subcategory.html', category=cat, subcategory=sub, products=products)


@store_bp.route('/search')
def search():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    products = Product.query.filter(
        Product.is_active == True,
        Product.name.ilike(f'%{q}%')
    ).paginate(page=page, per_page=12, error_out=False) if q else None
    return render_template('store/search.html', products=products, q=q)


@store_bp.route('/product/<slug>')
def product_detail(slug):
    product = Product.query.filter_by(slug=slug, is_active=True).first_or_404()
    ref = request.args.get('ref', '')
    return render_template('store/product.html', product=product, ref=ref)