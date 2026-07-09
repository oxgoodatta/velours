from datetime import datetime
import secrets
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    referral_code = db.Column(db.String(12), unique=True, nullable=True)
    referral_unlocked = db.Column(db.Boolean, default=False)
    referral_slots_total = db.Column(db.Integer, default=0)
    referral_slots_used = db.Column(db.Integer, default=0)
    referred_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    wallet_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='buyer', lazy=True, foreign_keys='Order.user_id')
    commissions = db.relationship('Commission', backref='earner', lazy=True, foreign_keys='Commission.referrer_id')
    referred_users = db.relationship('User', backref=db.backref('referred_by', remote_side=[id]), lazy=True)

    @property
    def referral_slots_remaining(self):
        return max(0, self.referral_slots_total - self.referral_slots_used)

    @property
    def can_refer(self):
        return self.referral_unlocked and self.referral_slots_remaining > 0

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_referral_code(self):
        self.referral_code = secrets.token_hex(5).upper()

    def add_referral_slots(self, purchase_amount):
        slots = int(purchase_amount / 10)
        self.referral_slots_total += slots
        if not self.referral_unlocked:
            self.referral_unlocked = True


class Category(db.Model):
    """Top-level category e.g. Social Media Templates"""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(10), default='📦')
    cover_image = db.Column(db.String(300), nullable=True)  # folder cover image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subcategories = db.relationship('Subcategory', backref='category', lazy=True, cascade='all, delete-orphan')
    products = db.relationship('Product', backref='category', lazy=True)

    @property
    def cover(self):
        """Returns cover image or first subcategory cover or first product image"""
        if self.cover_image:
            return self.cover_image
        for sub in self.subcategories:
            if sub.cover_image:
                return sub.cover_image
            for p in sub.products:
                if p.preview_image:
                    return p.preview_image
        for p in self.products:
            if p.preview_image:
                return p.preview_image
        return None

    @property
    def total_products(self):
        count = len([p for p in self.products if p.is_active])
        for sub in self.subcategories:
            count += len([p for p in sub.products if p.is_active])
        return count


class Subcategory(db.Model):
    """Second-level e.g. Grand Opening, Flash Sale"""
    __tablename__ = 'subcategories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover_image = db.Column(db.String(300), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='subcategory', lazy=True)

    @property
    def cover(self):
        if self.cover_image:
            return self.cover_image
        for p in self.products:
            if p.preview_image:
                return p.preview_image
        return None

    @property
    def active_products(self):
        return [p for p in self.products if p.is_active]


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    referral_commission_pct = db.Column(db.Float, default=0.0)
    preview_image = db.Column(db.String(300), nullable=True)
    delivery_content = db.Column(db.Text, nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    subcategory_id = db.Column(db.Integer, db.ForeignKey('subcategories.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    total_sales = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='product', lazy=True)

    @property
    def commission_amount(self):
        return round(self.price * self.referral_commission_pct / 100, 2)


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    referral_code_used = db.Column(db.String(12), nullable=True)
    hubtel_transaction_id = db.Column(db.String(100), nullable=True)
    momo_phone = db.Column(db.String(20), nullable=True)
    momo_network = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    commission = db.relationship('Commission', backref='order', uselist=False)


class Commission(db.Model):
    __tablename__ = 'commissions'
    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    percentage_used = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


class Withdrawal(db.Model):
    __tablename__ = 'withdrawals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    momo_number = db.Column(db.String(20), nullable=False)
    momo_network = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    admin_note = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='withdrawals')