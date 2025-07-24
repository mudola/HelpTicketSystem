from datetime import datetime
from extensions import db
from flask_login import UserMixin
from sqlalchemy import Text

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # admin, intern, user
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(128), nullable=True)

    # Relationships
    tickets_created = db.relationship('Ticket', foreign_keys='Ticket.created_by_id', backref='creator', lazy='dynamic')
    assigned_tickets = db.relationship('Ticket', secondary='ticket_assignees', back_populates='assignees', lazy='selectin')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tickets = db.relationship('Ticket', backref='category', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'

# Association table for many-to-many Ticket <-> User (assignees)
ticket_assignees = db.Table('ticket_assignees',
    db.Column('ticket_id', db.Integer, db.ForeignKey('ticket.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(200), nullable=False)
    description = db.Column(Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='open')  # open, in_progress, resolved, closed
    priority = db.Column(db.String(20), nullable=False, default='medium')  # low, medium, high, urgent
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = db.Column(db.DateTime)
    closed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)

    # Foreign Keys
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))

    # Relationships
    comments = db.relationship('Comment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('Attachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    assignees = db.relationship('User', secondary=ticket_assignees, back_populates='assigned_tickets', lazy='selectin')
    closed_by = db.relationship('User', foreign_keys=[closed_by_id], backref='closed_tickets')

    def __repr__(self):
        return f'<Ticket {self.id}: {self.location}>'

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign Keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f'<Comment {self.id} on Ticket {self.ticket_id}>'

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer)
    content_type = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign Keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Relationships
    uploaded_by = db.relationship('User', backref='attachments')

    def __repr__(self):
        return f'<Attachment {self.original_filename}>'

class TicketHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # e.g., 'created', 'status changed', 'updated', etc.
    field_changed = db.Column(db.String(100), nullable=True)  # e.g., 'status', 'priority', etc.
    old_value = db.Column(db.String(200), nullable=True)
    new_value = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='ticket_histories')
    ticket = db.relationship('Ticket', backref='histories')

    def __repr__(self):
        return f'<TicketHistory {self.id} on Ticket {self.ticket_id}>'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=True)
    type = db.Column(db.String(50), nullable=False)  # new_ticket, ticket_updated, new_comment, ticket_closed, ticket_overdue, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    email_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref='notifications')
    ticket = db.relationship('Ticket', backref='notifications')

    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'

class NotificationSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    new_ticket_email = db.Column(db.Boolean, default=True)
    new_ticket_app = db.Column(db.Boolean, default=True)
    ticket_updated_email = db.Column(db.Boolean, default=True)
    ticket_updated_app = db.Column(db.Boolean, default=True)
    new_comment_email = db.Column(db.Boolean, default=True)
    new_comment_app = db.Column(db.Boolean, default=True)
    ticket_closed_email = db.Column(db.Boolean, default=True)
    ticket_closed_app = db.Column(db.Boolean, default=True)
    ticket_overdue_email = db.Column(db.Boolean, default=True)
    ticket_overdue_app = db.Column(db.Boolean, default=True)
    do_not_disturb = db.Column(db.Boolean, default=False)
    dnd_start_time = db.Column(db.Time, nullable=True)
    dnd_end_time = db.Column(db.Time, nullable=True)

    # Relationships
    user = db.relationship('User', backref='notification_settings', uselist=False)

    def __repr__(self):
        return f'<NotificationSettings for User {self.user_id}>'
