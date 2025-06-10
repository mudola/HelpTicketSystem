import os
from datetime import datetime, timedelta
from flask import render_template, flash, redirect, url_for, request, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc
from flask_mail import Message

from app import app, db, mail
from models import User, Ticket, Comment, Attachment, Category
from forms import LoginForm, RegistrationForm, TicketForm, CommentForm, TicketUpdateForm, UserManagementForm, CategoryForm
from utils import send_notification_email, get_dashboard_stats

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('dashboard')
            return redirect(next_page)
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return render_template('register.html', form=form)
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Email already registered', 'danger')
            return render_template('register.html', form=form)
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            password_hash=generate_password_hash(form.password.data),
            role=form.role.data
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    stats = get_dashboard_stats(current_user)
    
    # Get recent tickets based on user role
    if current_user.role == 'intern':
        recent_tickets = Ticket.query.filter_by(assigned_to_id=current_user.id).order_by(desc(Ticket.updated_at)).limit(5).all()
    else:  # user
        recent_tickets = Ticket.query.filter_by(created_by_id=current_user.id).order_by(desc(Ticket.updated_at)).limit(5).all()
    
    return render_template('dashboard.html', stats=stats, recent_tickets=recent_tickets)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        abort(403)
    
    stats = get_dashboard_stats(current_user)
    
    # Get recent activity
    recent_tickets = Ticket.query.order_by(desc(Ticket.updated_at)).limit(10).all()
    
    # Get user statistics
    user_stats = db.session.query(
        User.role,
        func.count(User.id).label('count')
    ).group_by(User.role).all()
    
    return render_template('admin_dashboard.html', stats=stats, recent_tickets=recent_tickets, user_stats=user_stats)

@app.route('/tickets')
@login_required
def tickets_list():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    
    query = Ticket.query
    
    # Apply role-based filtering
    if current_user.role == 'user':
        query = query.filter_by(created_by_id=current_user.id)
    elif current_user.role == 'intern':
        query = query.filter_by(assigned_to_id=current_user.id)
    # Admin can see all tickets
    
    # Apply filters
    if status_filter:
        query = query.filter_by(status=status_filter)
    if priority_filter:
        query = query.filter_by(priority=priority_filter)
    
    tickets = query.order_by(desc(Ticket.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('tickets_list.html', tickets=tickets, status_filter=status_filter, priority_filter=priority_filter)

@app.route('/ticket/new', methods=['GET', 'POST'])
@login_required
def new_ticket():
    form = TicketForm()
    
    if form.validate_on_submit():
        # Create new ticket
        ticket = Ticket(
            title=form.title.data,
            description=form.description.data,
            priority=form.priority.data,
            created_by_id=current_user.id,
            category_id=form.category_id.data if form.category_id.data else None,
            assigned_to_id=form.assigned_to_id.data if form.assigned_to_id.data else None
        )
        
        db.session.add(ticket)
        db.session.flush()  # Get the ticket ID
        
        # Handle file upload
        if form.attachments.data and form.attachments.data.filename:
            file = form.attachments.data
            filename = secure_filename(file.filename)
            if filename:
                try:
                    # Generate unique filename
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    attachment = Attachment(
                        filename=filename,
                        original_filename=file.filename,
                        file_size=os.path.getsize(file_path),
                        content_type=file.content_type,
                        ticket_id=ticket.id,
                        uploaded_by_id=current_user.id
                    )
                    db.session.add(attachment)
                except Exception as e:
                    flash(f'Error uploading file: {str(e)}', 'danger')
                    return render_template('ticket_form.html', form=form, title='New Ticket')
        
        db.session.commit()
        
        # Send notification email
        if ticket.assigned_to_id:
            send_notification_email(ticket, 'new_ticket')
        
        flash('Ticket created successfully', 'success')
        return redirect(url_for('ticket_detail', id=ticket.id))
    
    return render_template('ticket_form.html', form=form, title='New Ticket')

@app.route('/ticket/<int:id>')
@login_required
def ticket_detail(id):
    ticket = Ticket.query.get_or_404(id)
    
    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and ticket.assigned_to_id != current_user.id:
        abort(403)
    
    # Get comments based on user role
    if current_user.role == 'user':
        comments = Comment.query.filter_by(ticket_id=id, is_internal=False).order_by(Comment.created_at).all()
    else:
        comments = Comment.query.filter_by(ticket_id=id).order_by(Comment.created_at).all()
    
    comment_form = CommentForm()
    update_form = TicketUpdateForm(obj=ticket) if current_user.role in ['admin', 'intern'] else None
    
    return render_template('ticket_detail.html', ticket=ticket, comments=comments, 
                         comment_form=comment_form, update_form=update_form)

@app.route('/ticket/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    ticket = Ticket.query.get_or_404(id)
    
    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and ticket.assigned_to_id != current_user.id:
        abort(403)
    
    form = CommentForm()
    if form.validate_on_submit():
        # Users cannot create internal comments
        is_internal = form.is_internal.data if current_user.role in ['admin', 'intern'] else False
        
        comment = Comment(
            content=form.content.data,
            is_internal=is_internal,
            ticket_id=id,
            author_id=current_user.id
        )
        db.session.add(comment)
        
        # Update ticket timestamp
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Send notification email
        send_notification_email(ticket, 'new_comment')
        
        flash('Comment added successfully', 'success')
    
    return redirect(url_for('ticket_detail', id=id))

@app.route('/ticket/<int:id>/update', methods=['POST'])
@login_required
def update_ticket(id):
    if current_user.role not in ['admin', 'intern']:
        abort(403)
    
    ticket = Ticket.query.get_or_404(id)
    
    # Interns can only update tickets assigned to them
    if current_user.role == 'intern' and ticket.assigned_to_id != current_user.id:
        abort(403)
    
    form = TicketUpdateForm()
    if form.validate_on_submit():
        old_status = ticket.status
        ticket.status = form.status.data
        ticket.priority = form.priority.data
        ticket.updated_at = datetime.utcnow()
        
        # Only admins can reassign tickets
        if current_user.role == 'admin':
            ticket.assigned_to_id = form.assigned_to_id.data if form.assigned_to_id.data else None
        
        # Set closed_at timestamp if ticket is closed
        if form.status.data == 'closed' and old_status != 'closed':
            ticket.closed_at = datetime.utcnow()
        elif form.status.data != 'closed':
            ticket.closed_at = None
        
        db.session.commit()
        
        # Send notification email
        send_notification_email(ticket, 'ticket_updated')
        
        flash('Ticket updated successfully', 'success')
    
    return redirect(url_for('ticket_detail', id=id))

@app.route('/ticket/<int:id>/close', methods=['POST'])
@login_required
def close_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    
    # Check permissions - users can close their own tickets, interns and admins can close assigned tickets
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and ticket.assigned_to_id != current_user.id:
        abort(403)
    
    ticket.status = 'closed'
    ticket.closed_at = datetime.utcnow()
    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Ticket closed successfully', 'success')
    return redirect(url_for('ticket_detail', id=id))

@app.route('/reports')
@login_required
def reports():
    if current_user.role != 'admin':
        abort(403)
    
    # Date range filter
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Ticket statistics
    total_tickets = Ticket.query.filter(Ticket.created_at >= start_date).count()
    closed_tickets = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.status == 'closed'
    ).count()
    
    # Activity by user
    user_activity = db.session.query(
        User.full_name,
        User.role,
        func.count(Ticket.id).label('tickets_created')
    ).join(Ticket, User.id == Ticket.created_by_id)\
     .filter(Ticket.created_at >= start_date)\
     .group_by(User.id, User.full_name, User.role)\
     .all()
    
    # Intern activity
    intern_activity = db.session.query(
        User.full_name,
        func.count(Ticket.id).label('tickets_assigned')
    ).join(Ticket, User.id == Ticket.assigned_to_id)\
     .filter(Ticket.created_at >= start_date, User.role == 'intern')\
     .group_by(User.id, User.full_name)\
     .all()
    
    # Tickets by status
    status_stats = db.session.query(
        Ticket.status,
        func.count(Ticket.id).label('count')
    ).filter(Ticket.created_at >= start_date)\
     .group_by(Ticket.status)\
     .all()
    
    # Tickets by priority
    priority_stats = db.session.query(
        Ticket.priority,
        func.count(Ticket.id).label('count')
    ).filter(Ticket.created_at >= start_date)\
     .group_by(Ticket.priority)\
     .all()
    
    # Average resolution time
    resolved_tickets = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.status.in_(['resolved', 'closed']),
        Ticket.closed_at.isnot(None)
    ).all()
    
    avg_resolution_time = None
    if resolved_tickets:
        total_time = sum([(t.closed_at - t.created_at).total_seconds() for t in resolved_tickets])
        avg_resolution_time = total_time / len(resolved_tickets) / 3600  # in hours
    
    return render_template('reports.html',
                         total_tickets=total_tickets,
                         closed_tickets=closed_tickets,
                         user_activity=user_activity,
                         intern_activity=intern_activity,
                         status_stats=status_stats,
                         priority_stats=priority_stats,
                         avg_resolution_time=avg_resolution_time,
                         days=days)

@app.route('/admin/users')
@login_required
def user_management():
    if current_user.role != 'admin':
        abort(403)
    
    users = User.query.all()
    form = UserManagementForm()
    category_form = CategoryForm()
    categories = Category.query.all()
    
    return render_template('user_management.html', users=users, form=form, 
                         category_form=category_form, categories=categories)

@app.route('/admin/users/update_password', methods=['POST'])
@login_required
def update_user_password():
    if current_user.role != 'admin':
        abort(403)
    
    form = UserManagementForm()
    if form.validate_on_submit():
        user = User.query.get_or_404(form.user_id.data)
        user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        flash(f'Password updated for {user.full_name}', 'success')
    
    return redirect(url_for('user_management'))

@app.route('/admin/categories', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'admin':
        abort(403)
    
    form = CategoryForm()
    if form.validate_on_submit():
        # Check if category already exists
        existing = Category.query.filter_by(name=form.name.data).first()
        if existing:
            flash('Category already exists', 'danger')
        else:
            category = Category(
                name=form.name.data,
                description=form.description.data
            )
            db.session.add(category)
            db.session.commit()
            flash('Category added successfully', 'success')
    
    return redirect(url_for('user_management'))

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    # Verify user has access to the file
    attachment = Attachment.query.filter_by(filename=filename).first_or_404()
    ticket = attachment.ticket
    
    # Check permissions
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and ticket.assigned_to_id != current_user.id:
        abort(403)
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404
