import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db, login_manager, mail
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://sql8785118:ZzV7IVGefP@sql8.freesqldatabase.com:3306/sql8785118'
#["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root:@localhost:3306/helpticket_system"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configure uploads
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure mail
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'localhost')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', 'helpdesk@company.com')

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
mail.init_app(app)


# Configure login manager
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize the database and create tables
with app.app_context():
    import models
    db.create_all()  # Creates tables in the helpticket_system database

    # Create a default admin user
    from models import User, Category
    from werkzeug.security import generate_password_hash

    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin_user = User(
            username='admin',
            email='admin@company.com',
            password_hash=generate_password_hash('admin123'),
            role='admin',
            full_name='System Administrator'
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created (username: admin, password: admin123)")

    # Create default categories
    default_categories = [
        ('Hardware', 'Computer hardware, printers, peripherals'),
        ('Software', 'Software installation, updates, licensing'),
        ('Network', 'Internet connectivity, WiFi, network access'),
        ('Email', 'Email setup, issues, and configuration'),
        ('Security', 'Password resets, account access, security concerns'),
        ('Other', 'General ICT support requests')
    ]

    for cat_name, cat_desc in default_categories:
        if not Category.query.filter_by(name=cat_name).first():
            category = Category(name=cat_name, description=cat_desc)
            db.session.add(category)

    db.session.commit()

@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}

# Import routes
import routes

