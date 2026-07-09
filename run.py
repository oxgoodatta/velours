from app import create_app, db
from app.models import User, Category
import os

app = create_app()


def seed():
    with app.app_context():
        db.create_all()

        # ── TWO ADMIN ACCOUNTS ─────────────────────────────────────────────
        admins = [
            {
                'name': os.environ.get('ADMIN1_NAME', 'Admin One'),
                'email': os.environ.get('ADMIN1_EMAIL', 'admin1@digistore.com'),
                'password': os.environ.get('ADMIN1_PASSWORD', 'Admin@123'),
            },
            {
                'name': os.environ.get('ADMIN2_NAME', 'Admin Two'),
                'email': os.environ.get('ADMIN2_EMAIL', 'admin2@digistore.com'),
                'password': os.environ.get('ADMIN2_PASSWORD', 'Admin@456'),
            },
        ]

        for a in admins:
            if not User.query.filter_by(email=a['email']).first():
                user = User(name=a['name'], email=a['email'], is_admin=True, referral_unlocked=True)
                user.set_password(a['password'])
                user.generate_referral_code()
                db.session.add(user)
                print(f'✅ Admin: {a["email"]} / {a["password"]}')

        # ── STARTER CATEGORIES ─────────────────────────────────────────────
        starter = [
            ('Social Media Templates', 'social-media', '📱', 'Facebook, Instagram & WhatsApp templates'),
            ('Business & Branding', 'business', '💼', 'Business cards, flyers, brand kits'),
            ('Church & Events', 'church-events', '⛪', 'Bulletins, programs, event flyers'),
            ('CV & Career', 'cv-career', '🎓', 'CV templates, cover letters, LinkedIn banners'),
            ('Storybooks', 'storybooks', '📚', 'Ghanaian children storybooks and educational PDFs'),
            ('eBooks & Guides', 'ebooks', '📖', 'How-to guides, business tips, info products'),
        ]
        for name, slug, icon, desc in starter:
            if not Category.query.filter_by(slug=slug).first():
                db.session.add(Category(name=name, slug=slug, icon=icon, description=desc))
                print(f'✅ Category: {name}')

        db.session.commit()
        print(f'\n🚀 {os.environ.get("APP_NAME", "DigiStoreGH")} is ready!')
        print(f'   Admin 1: {admins[0]["email"]} / {admins[0]["password"]}')
        print(f'   Admin 2: {admins[1]["email"]} / {admins[1]["password"]}')
        print(f'   Admin panel: /admin')


if __name__ == '__main__':
    seed()
    app.run(debug=True, host='0.0.0.0', port=5000)
