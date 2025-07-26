import os
from datetime import datetime, timedelta
from flask import render_template, flash, redirect, url_for, request, send_from_directory, abort, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc
from flask_mail import Message
import pytz
import uuid
from sqlalchemy.orm import joinedload

from app import app, db, mail
from models import User, Ticket, Comment, Attachment, Category, Notification, NotificationSettings
from forms import LoginForm, RegistrationForm, TicketForm, CommentForm, TicketUpdateForm, UserManagementForm, CategoryForm, AdminUserForm, NotificationSettingsForm, PasswordChangeForm, UserStatusForm
from utils import send_notification_email, get_dashboard_stats
from notification_utils import NotificationManager

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    # Handle form submission from index page
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'y'

        if username and password:
            # Admin login: only allow username '215030' and password 'admin123'
            if username == '215030':
                if password == 'admin123':
                    user = User.query.filter_by(username='215030').first()
                    if user:
                        login_user(user, remember=remember_me)
                        next_page = request.args.get('next')
                        if not next_page or not next_page.startswith('/'):
                            next_page = url_for('dashboard')
                        return redirect(next_page)
                    else:
                        flash('Admin user not found in database.', 'danger')
                else:
                    flash('Invalid admin password.', 'danger')
                return redirect(url_for('index'))

            # Intern default login
            if username == 'dctraining' and password == 'Dctraining2023':
                user = User.query.filter_by(username='dctraining').first()
                if user:
                    login_user(user, remember=remember_me)
                    next_page = request.args.get('next')
                    if not next_page or not next_page.startswith('/'):
                        next_page = url_for('dashboard')
                    return redirect(next_page)
                else:
                    flash('Intern user not found in database.', 'danger')
                return redirect(url_for('index'))

            # Payroll login for users/interns
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                if not user.is_active:
                    flash('Your account has been deactivated. Please contact administrator.', 'danger')
                    return redirect(url_for('index'))
                
                # Check if account is verified
                if not user.is_verified:
                    flash('Please verify your email address before logging in.', 'warning')
                    return redirect(url_for('index'))
                
                # Check approval status for interns only
                if user.role == 'intern' and not user.is_approved:
                    print(f"DEBUG: Intern {user.username} is not approved. is_approved={user.is_approved}, is_active={user.is_active}")
                    flash('Your intern account is pending admin approval. Please wait for activation.', 'warning')
                    return redirect(url_for('index'))
                
                print(f"DEBUG: User {user.username} login - role={user.role}, is_approved={user.is_approved}, is_active={user.is_active}")
                
                login_user(user, remember=remember_me)
                next_page = request.args.get('next')
                if not next_page or not next_page.startswith('/'):
                    next_page = url_for('dashboard')
                return redirect(next_page)

            flash('Invalid username or password', 'danger')
            return redirect(url_for('index'))

    # For GET requests, redirect to index page instead of showing separate login page
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first_or_404()
    if user.is_verified:
        flash('Account already verified. Please login.', 'info')
    else:
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        flash('Your email has been verified. You can now login.', 'success')
    return redirect(url_for('login'))

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

        # Generate verification token
        token = str(uuid.uuid4())
        
        # Auto-approve users, require admin approval only for interns
        is_approved = form.role.data in ['admin', 'user']
        is_active = form.role.data in ['admin', 'user']
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            password_hash=generate_password_hash(form.password.data),
            role=form.role.data,
            phone_number=getattr(form, 'phone_number', None) and form.phone_number.data,
            is_verified=False,
            is_approved=is_approved,
            is_active=is_active,
            verification_token=token
        )
        db.session.add(user)
        db.session.flush()  # Get the user ID
        
        # Send verification email (only if email is configured)
        try:
            if app.config.get('MAIL_USERNAME') and app.config.get('MAIL_PASSWORD'):
                verify_url = url_for('verify_email', token=token, _external=True)
                msg = Message('Verify Your Email - ICT Helpdesk', recipients=[user.email])
                msg.body = f"Hello {user.full_name},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nAfter verification, your account will need admin approval before you can access the system.\n\nIf you did not register, please ignore this email."
                mail.send(msg)
                email_sent = True
            else:
                email_sent = False
                # For development/testing, mark user as verified automatically
                user.is_verified = True
                user.verification_token = None
        except Exception as e:
            print(f"Email sending failed: {e}")
            email_sent = False
            # Mark user as verified automatically if email fails
            user.is_verified = True
            user.verification_token = None
        
        db.session.commit()
        
        # Notify all admins about new intern registration (users are auto-approved)
        if form.role.data == 'intern':
            NotificationManager.notify_new_user_registration(user)
        
        if form.role.data == 'user':
            if email_sent:
                flash('Registration successful! Please check your email to verify your account, then you can login.', 'info')
            else:
                flash('Registration successful! Your account has been automatically verified. You can now login.', 'info')
        else:  # intern
            if email_sent:
                flash('Registration successful! Please check your email to verify your account. Admin approval will be required before you can access the system.', 'info')
            else:
                flash('Registration successful! Your account has been automatically verified for testing. Admin approval will be required before you can access the system.', 'info')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))

    stats = get_dashboard_stats(current_user)

    # Show recent tickets where the user is an assignee (for both users and interns)
    recent_tickets = Ticket.query.join(Ticket.assignees).filter(User.id == current_user.id).order_by(desc(Ticket.updated_at)).limit(5).all()

    return render_template('dashboard.html', stats=stats, recent_tickets=recent_tickets)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        abort(403)

    stats = get_dashboard_stats(current_user)

    # Get recent activity with assignees eager-loaded
    recent_tickets = Ticket.query.options(joinedload(Ticket.assignees)).order_by(desc(Ticket.updated_at)).limit(10).all()

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
        # For interns, if status is 'assigned', show all assigned tickets
        if status_filter == 'assigned':
            query = query.filter(Ticket.assignees.any(id=current_user.id))
            status_filter = ''  # Clear status filter since we're showing all assigned tickets
        else:
            query = query.filter(Ticket.assignees.any(id=current_user.id))
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
        # Get selected assignees
        assignee_ids = form.assignees.data or []
        # Priority-based limits
        max_assignees = 1
        if form.priority.data == 'urgent':
            max_assignees = 3
        elif form.priority.data == 'high':
            max_assignees = 4
        elif form.priority.data == 'low':
            max_assignees = 1
        if len(assignee_ids) > max_assignees:
            flash(f'Maximum {max_assignees} assignees allowed for {form.priority.data.title()} priority.', 'danger')
            return render_template('ticket_form.html', form=form, title='New Ticket')
        # Limit: Only 1 active (open/in_progress) ticket per intern/technician
        if assignee_ids:
            for assigned_to_id in assignee_ids:
                active_task_count = Ticket.query.join(Ticket.assignees).filter(
                    User.id == assigned_to_id,
                    Ticket.status.in_(['open', 'in_progress'])
                ).count()
                if active_task_count >= 1:
                    flash('This technician/intern already has an active task assigned. Only 1 active task is allowed at a time.', 'danger')
                    return render_template('ticket_form.html', form=form, title='New Ticket')

        nairobi_tz = pytz.timezone('Africa/Nairobi')
        now_nairobi = datetime.now(nairobi_tz)
        # Compose location string from dropdowns if used
        location = form.location.data
        if form.location_unit.data:
            location = form.location_unit.data
            if form.location_subunit.data:
                location += f" - {form.location_subunit.data}"
            if form.location_detail.data:
                location += f" - {form.location_detail.data}"
        # If University MIS System Issue, append subcategory to description
        category_obj = Category.query.get(form.category_id.data)
        description = form.description.data
        if category_obj and category_obj.name == 'University MIS System Issue' and form.mis_subcategory.data:
            description = f"[{form.mis_subcategory.data}] " + description

        ticket = Ticket(
            location=location,
            description=description,
            priority=form.priority.data,
            created_by_id=current_user.id,
            category_id=form.category_id.data if form.category_id.data else None,
            status='in_progress' if assignee_ids else 'open',
            created_at=now_nairobi,
            updated_at=now_nairobi
        )
        db.session.add(ticket)
        db.session.flush()

        # Assign users
        for uid in assignee_ids:
            user = User.query.get(uid)
            if user:
                ticket.assignees.append(user)

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

        # Send notifications using the new system
        print(f"DEBUG: About to send notifications for new ticket {ticket.id}")
        NotificationManager.notify_new_ticket(ticket)
        print(f"DEBUG: Notifications sent for ticket {ticket.id}")

        flash('Ticket created successfully', 'success')
        return redirect(url_for('ticket_detail', id=ticket.id))

    return render_template('ticket_form.html', form=form, title='New Ticket')

@app.route('/ticket/<int:id>')
@login_required
def ticket_detail(id):
    ticket = Ticket.query.get_or_404(id)

    # Check permissions (admin can access any ticket)
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and current_user.id not in [u.id for u in ticket.assignees] and ticket.created_by_id != current_user.id:
        abort(403)
    # Admin has access to all tickets - no restriction needed

    # Get comments based on user role
    if current_user.role == 'user':
        comments = Comment.query.filter_by(ticket_id=id, is_internal=False).order_by(Comment.created_at).all()
    else:
        comments = Comment.query.filter_by(ticket_id=id).order_by(Comment.created_at).all()

    comment_form = CommentForm()
    update_form = TicketUpdateForm(user_role=current_user.role, current_status=ticket.status, obj=ticket) if current_user.role in ['admin', 'intern'] else None

    return render_template('ticket_detail.html', ticket=ticket, comments=comments, 
                         comment_form=comment_form, update_form=update_form)

@app.route('/ticket/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    ticket = Ticket.query.get_or_404(id)

    # Check permissions (admin can comment on any ticket)
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and current_user.id not in [u.id for u in ticket.assignees] and ticket.created_by_id != current_user.id:
        abort(403)
    # Admin has access to all tickets - no restriction needed

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

        # Send notifications using the new system
        NotificationManager.notify_new_comment(ticket, current_user)

        flash('Comment added successfully', 'success')

    return redirect(url_for('ticket_detail', id=id))

@app.route('/ticket/<int:id>/update', methods=['POST'])
@login_required
def update_ticket(id):
    if current_user.role not in ['admin', 'intern']:
        abort(403)

    ticket = Ticket.query.get_or_404(id)

    # Interns can only update tickets assigned to them
    if current_user.role == 'intern' and current_user not in ticket.assignees:
        abort(403)

    form = TicketUpdateForm(user_role=current_user.role, current_status=ticket.status)
    if form.validate_on_submit():
        old_status = ticket.status
        old_priority = ticket.priority
        old_assignees = set([u.id for u in ticket.assignees])

        # Prevent interns from closing tickets
        if current_user.role == 'intern' and form.status.data == 'closed':
            flash('Interns cannot close tickets. Only admins and ticket creators can close tickets.', 'danger')
            return redirect(url_for('ticket_detail', id=id))

        # Prevent interns from reverting resolved tickets
        if current_user.role == 'intern' and old_status == 'resolved' and form.status.data != 'resolved':
            flash('Interns cannot revert resolved tickets. Only administrators can modify resolved tickets.', 'danger')
            return redirect(url_for('ticket_detail', id=id))

        # Prevent reverting closed tickets
        if old_status == 'closed' and form.status.data != 'closed':
            flash('Cannot revert a closed ticket. Closed tickets cannot be reopened.', 'danger')
            return redirect(url_for('ticket_detail', id=id))

        # Prevent closing tickets that are not resolved
        if form.status.data == 'closed' and old_status != 'resolved':
            flash('Tickets can only be closed if they are resolved first.', 'danger')
            return redirect(url_for('ticket_detail', id=id))

        ticket.status = form.status.data
        ticket.priority = form.priority.data
        ticket.updated_at = datetime.utcnow()

        # Only admins can reassign tickets
        if current_user.role == 'admin':
            # Get new assignee IDs from form (should be a list)
            new_assignee_ids = form.assignees.data or []
            # Prevent assigning if intern/technician already has an active task
            for new_assigned_id in new_assignee_ids:
                active_task_count = Ticket.query.join(Ticket.assignees).filter(
                    User.id == new_assigned_id,
                    Ticket.status.in_(['open', 'in_progress']),
                    Ticket.id != ticket.id
                ).count()
                if active_task_count >= 1:
                    flash('This technician/intern already has an active task assigned. Only 1 active task is allowed at a time.', 'danger')
                    return render_template('ticket_detail.html', ticket=ticket, comments=Comment.query.filter_by(ticket_id=id).all(), comment_form=CommentForm(), update_form=form)
            # Update assignees
            ticket.assignees = [User.query.get(uid) for uid in new_assignee_ids if User.query.get(uid)]

            # Set due_date if assigned and not already set
            if new_assignee_ids and not ticket.due_date:
                ticket.due_date = datetime.utcnow() + timedelta(days=2)
            elif not new_assignee_ids:
                ticket.due_date = None

            # Auto-change status based on assignment
            if ticket.assignees and old_status == 'open':
                ticket.status = 'in_progress'
            elif not ticket.assignees and old_status == 'in_progress':
                ticket.status = 'open'

        # Set closed_at timestamp and closed_by if ticket is closed
        if form.status.data == 'closed' and old_status != 'closed':
            ticket.closed_at = datetime.utcnow()
            ticket.closed_by_id = current_user.id
            # Preserve assignees when closing ticket - do not clear them
        elif form.status.data != 'closed':
            ticket.closed_at = None
            ticket.closed_by_id = None

        # Log history for status change
        if old_status != ticket.status:
            from models import TicketHistory
            history = TicketHistory(
                ticket_id=ticket.id,
                user_id=current_user.id,
                action='status changed',
                field_changed='status',
                old_value=old_status,
                new_value=ticket.status
            )
            db.session.add(history)
        # Log history for priority change
        if old_priority != ticket.priority:
            from models import TicketHistory
            history = TicketHistory(
                ticket_id=ticket.id,
                user_id=current_user.id,
                action='priority changed',
                field_changed='priority',
                old_value=old_priority,
                new_value=ticket.priority
            )
            db.session.add(history)
        # Log history for reassignment
        if current_user.role == 'admin':
            new_assignees = set([u.id for u in ticket.assignees])
            if old_assignees != new_assignees:
                from models import TicketHistory
                history = TicketHistory(
                    ticket_id=ticket.id,
                    user_id=current_user.id,
                    action='reassigned',
                    field_changed='assignees',
                    old_value=str(list(old_assignees)),
                    new_value=str(list(new_assignees))
                )
                db.session.add(history)

        db.session.commit()

        # Send notifications using the new system
        NotificationManager.notify_ticket_updated(ticket, current_user)

        flash('Ticket updated successfully', 'success')

    return redirect(url_for('ticket_detail', id=id))

@app.route('/ticket/<int:id>/print')
@login_required
def print_ticket(id):
    ticket = Ticket.query.get_or_404(id)

    # Check permissions - only allow printing of closed tickets
    if ticket.status != 'closed':
        abort(403)

    # Check if user has access to view this ticket
    if current_user.role == 'user' and ticket.created_by_id != current_user.id:
        abort(403)
    elif current_user.role == 'intern' and current_user.id not in [u.id for u in ticket.assignees] and ticket.created_by_id != current_user.id:
        abort(403)

    # Get all comments (internal comments only for admin/intern)
    if current_user.role == 'user':
        comments = Comment.query.filter_by(ticket_id=id, is_internal=False).order_by(Comment.created_at).all()
    else:
        comments = Comment.query.filter_by(ticket_id=id).order_by(Comment.created_at).all()

    return render_template('print_ticket.html', ticket=ticket, comments=comments)

@app.route('/ticket/<int:id>/close', methods=['POST'])
@login_required
def close_ticket(id):
    ticket = Ticket.query.get_or_404(id)

    # Check permissions - only admins and ticket creators can close tickets
    if current_user.role != 'admin' and ticket.created_by_id != current_user.id:
        abort(403)

    # Check if ticket is already closed
    if ticket.status == 'closed':
        flash('Ticket is already closed', 'info')
        return redirect(url_for('ticket_detail', id=id))

    # Check if ticket is resolved before closing
    if ticket.status != 'resolved':
        flash('Ticket must be resolved before it can be closed', 'danger')
        return redirect(url_for('ticket_detail', id=id))

    ticket.status = 'closed'
    ticket.closed_at = datetime.utcnow()
    ticket.closed_by_id = current_user.id
    ticket.updated_at = datetime.utcnow()
    # Preserve assignees when closing - do not modify assignment

    # Log the closure
    from models import TicketHistory
    history = TicketHistory(
        ticket_id=ticket.id,
        user_id=current_user.id,
        action='ticket closed',
        field_changed='status',
        old_value='resolved',
        new_value='closed'
    )
    db.session.add(history)
    db.session.commit()

    # Send notifications using the new system
    NotificationManager.notify_ticket_closed(ticket, current_user)

    flash('Ticket closed successfully', 'success')
    return redirect(url_for('ticket_detail', id=id))

@app.route('/reports/pdf')
@login_required
def reports_pdf():
    if current_user.role != 'admin':
        abort(403)

    # Use same logic as main reports route for consistency
    date_range = request.args.get('date_range', 'weekly')
    end_date = datetime.utcnow()
    
    # Calculate start date based on range
    if date_range == 'daily':
        start_date = end_date - timedelta(days=1)
        days = 1
    elif date_range == 'weekly':
        start_date = end_date - timedelta(days=7)
        days = 7
    elif date_range == 'monthly':
        start_date = end_date - timedelta(days=30)
        days = 30
    else:
        start_date = end_date - timedelta(days=7)
        days = 7

    # Custom date range overrides preset ranges
    custom_start = request.args.get('start_date')
    custom_end = request.args.get('end_date')
    if custom_start and custom_end:
        try:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d')
            end_date = datetime.strptime(custom_end, '%Y-%m-%d')
        except ValueError:
            pass

    # Filter parameters
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', type=int)
    department_filter = request.args.get('department', '')

    # Build ticket query with filters
    ticket_query = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.created_at <= end_date
    )

    if status_filter:
        ticket_query = ticket_query.filter(Ticket.status == status_filter)
    if priority_filter:
        ticket_query = ticket_query.filter(Ticket.priority == priority_filter)
    if category_filter:
        ticket_query = ticket_query.filter(Ticket.category_id == category_filter)
    if department_filter:
        ticket_query = ticket_query.filter(Ticket.location.contains(department_filter))

    tickets = ticket_query.all()

    # Calculate statistics
    total_tickets = len(tickets)
    closed_tickets = len([t for t in tickets if t.status == 'closed'])

    # Staff performance
    staff_performance = db.session.query(
        User.full_name,
        User.role,
        func.count(Ticket.id).label('tickets_handled')
    ).join(User.assigned_tickets)\
     .filter(
         Ticket.created_at >= start_date,
         Ticket.created_at <= end_date,
         User.role.in_(['admin', 'intern'])
     ).group_by(User.id, User.full_name, User.role).all()

    # Category stats
    category_stats = db.session.query(
        Category.name,
        func.count(Ticket.id).label('count')
    ).join(Ticket, Category.id == Ticket.category_id)\
     .filter(Ticket.created_at >= start_date, Ticket.created_at <= end_date)

    if category_filter:
        category_stats = category_stats.filter(Category.id == category_filter)

    category_stats = category_stats.group_by(Category.name).all()

    # Priority and status stats
    priority_stats = {}
    status_stats = {}
    for t in tickets:
        priority_stats[t.priority] = priority_stats.get(t.priority, 0) + 1
        status_stats[t.status] = status_stats.get(t.status, 0) + 1

    priority_stats = [{'priority': k, 'count': v} for k, v in priority_stats.items()]
    status_stats = [{'status': k, 'count': v} for k, v in status_stats.items()]

    # Average resolution time
    resolved_tickets = [t for t in tickets if t.status in ['resolved', 'closed'] and t.closed_at]
    avg_resolution_time = None
    if resolved_tickets:
        total_time = sum([(t.closed_at - t.created_at).total_seconds() for t in resolved_tickets])
        avg_resolution_time = total_time / len(resolved_tickets) / 3600  # in hours

    return render_template('reports_pdf.html',
                         total_tickets=total_tickets,
                         closed_tickets=closed_tickets,
                         staff_performance=staff_performance,
                         category_stats=category_stats,
                         status_stats=status_stats,
                         priority_stats=priority_stats,
                         avg_resolution_time=avg_resolution_time,
                         tickets=tickets[:50],  # Limit for PDF
                         days=days,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         generated_date=datetime.utcnow())

@app.route('/reports')
@login_required
def reports():
    if current_user.role != 'admin':
        abort(403)

    # Enhanced filters with new date range options
    date_range = request.args.get('date_range', 'weekly')
    end_date = datetime.utcnow()
    
    # Calculate start date based on range
    if date_range == 'daily':
        start_date = end_date - timedelta(days=1)
        days = 1
    elif date_range == 'weekly':
        start_date = end_date - timedelta(days=7)
        days = 7
    elif date_range == 'monthly':
        start_date = end_date - timedelta(days=30)
        days = 30
    else:
        # Default to weekly if invalid option
        start_date = end_date - timedelta(days=7)
        days = 7

    # Custom date range overrides preset ranges
    custom_start = request.args.get('start_date')
    custom_end = request.args.get('end_date')
    if custom_start and custom_end:
        try:
            start_date = datetime.strptime(custom_start, '%Y-%m-%d')
            end_date = datetime.strptime(custom_end, '%Y-%m-%d')
            days = (end_date - start_date).days
        except ValueError:
            pass

    # Filter parameters
    created_by = request.args.get('created_by', type=int)
    attended_by = request.args.get('attended_by', type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    category_filter = request.args.get('category', type=int)
    department_filter = request.args.get('department', '')
    location_filter = request.args.get('location', '')
    subunit_filter = request.args.get('subunit', '')

    # All reference data for dropdowns
    all_users = User.query.order_by(User.full_name).all()
    all_categories = Category.query.order_by(Category.name).all()
    departments = ['SWA', 'UHS', 'Confucius']
    subunits = {
        'SWA': ['LSHR', 'USHR'],
        'UHS': ['Staff clinic', 'Student clinic'],
        'Confucius': ['Block A', 'Block B', 'Block C']
    }
    locations = {
        'LSHR': ['Location 1', 'Location 2'],
        'USHR': ['Location 3', 'Location 4'],
        'Staff clinic': ['Location 5', 'Location 6'],
        'Student clinic': ['Location 7', 'Location 8'],
        'Block A': ['Location 9', 'Location 10'],
        'Block B': ['Location 11', 'Location 12'],
        'Block C': ['Location 13', 'Location 14']
    }

    # Build ticket query with enhanced filters
    ticket_query = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.created_at <= end_date
    )

    if created_by:
        ticket_query = ticket_query.filter(Ticket.created_by_id == created_by)
    if attended_by:
        ticket_query = ticket_query.filter(Ticket.assignees.any(User.id == attended_by))
    if status_filter:
        ticket_query = ticket_query.filter(Ticket.status == status_filter)
    if priority_filter:
        ticket_query = ticket_query.filter(Ticket.priority == priority_filter)
    if category_filter:
        ticket_query = ticket_query.filter(Ticket.category_id == category_filter)
    if location_filter:
        ticket_query = ticket_query.filter(Ticket.location.contains(location_filter))
    elif subunit_filter:
        ticket_query = ticket_query.filter(Ticket.location.contains(subunit_filter))
    elif department_filter:
        ticket_query = ticket_query.filter(Ticket.location.contains(department_filter))

    tickets = ticket_query.all()

    # Enhanced statistics
    total_tickets = len(tickets)
    open_tickets = len([t for t in tickets if t.status == 'open'])
    in_progress_tickets = len([t for t in tickets if t.status == 'in_progress'])
    resolved_tickets = len([t for t in tickets if t.status == 'resolved'])
    closed_tickets = len([t for t in tickets if t.status == 'closed'])

    # Tickets by category
    category_stats = db.session.query(
        Category.name,
        func.count(Ticket.id).label('count')
    ).join(Ticket, Category.id == Ticket.category_id)\
     .filter(Ticket.created_at >= start_date, Ticket.created_at <= end_date)

    if category_filter:
        category_stats = category_stats.filter(Category.id == category_filter)
    if department_filter:
        category_stats = category_stats.filter(Ticket.location.contains(department_filter))

    category_stats = category_stats.group_by(Category.name).all()

    # Tickets by department/location
    department_stats = {}
    for ticket in tickets:
        dept = 'Other'
        # Check for more specific subunits first, then general departments
        for d in ['USHR', 'LSHR', 'Staff clinic', 'Student clinic', 'Block A', 'Block B', 'Block C', 'SWA', 'UHS', 'Confucius']:
            if d.lower() in ticket.location.lower():
                dept = d
                break
        department_stats[dept] = department_stats.get(dept, 0) + 1
    department_stats = [{'department': k, 'count': v} for k, v in department_stats.items()]

    # Staff performance
    staff_performance = db.session.query(
        User.full_name,
        User.role,
        func.count(Ticket.id).label('tickets_handled'),
        func.avg(
            func.julianday(Ticket.closed_at) - func.julianday(Ticket.created_at)
        ).label('avg_resolution_days')
    ).join(User.assigned_tickets)\
     .filter(
         Ticket.created_at >= start_date,
         Ticket.created_at <= end_date,
         Ticket.status.in_(['resolved', 'closed']),
         User.role.in_(['admin', 'intern'])
     )

    if attended_by:
        staff_performance = staff_performance.filter(User.id == attended_by)

    staff_performance = staff_performance.group_by(User.id, User.full_name, User.role).all()

    # Response and resolution times
    tickets_with_times = [t for t in tickets if t.status in ['resolved', 'closed'] and t.closed_at]
    avg_resolution_time = None
    resolution_times = []

    if tickets_with_times:
        total_time = sum([(t.closed_at - t.created_at).total_seconds() for t in tickets_with_times])
        avg_resolution_time = total_time / len(tickets_with_times) / 3600  # in hours
        resolution_times = [
            {
                'ticket_id': t.id,
                'hours': (t.closed_at - t.created_at).total_seconds() / 3600
            } for t in tickets_with_times
        ]

    # Overdue tickets
    overdue_tickets = []
    for ticket in tickets:
        if ticket.due_date and ticket.status not in ['resolved', 'closed']:
            if datetime.utcnow() > ticket.due_date:
                overdue_tickets.append(ticket)

    # Priority distribution
    priority_stats = {}
    for t in tickets:
        priority_stats[t.priority] = priority_stats.get(t.priority, 0) + 1
    priority_stats = [{'priority': k, 'count': v} for k, v in priority_stats.items()]

    # Status distribution
    status_stats = [
        {'status': 'open', 'count': open_tickets},
        {'status': 'in_progress', 'count': in_progress_tickets},
        {'status': 'resolved', 'count': resolved_tickets},
        {'status': 'closed', 'count': closed_tickets}
    ]

    # Trend data (last 7 days)
    trend_data = []
    for i in range(7):
        date = datetime.utcnow() - timedelta(days=i)
        day_tickets = Ticket.query.filter(
            func.date(Ticket.created_at) == date.date()
        ).count()
        trend_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'count': day_tickets
        })
    trend_data.reverse()

    return render_template('reports.html',
                         total_tickets=total_tickets,
                         open_tickets=open_tickets,
                         in_progress_tickets=in_progress_tickets,
                         resolved_tickets=resolved_tickets,
                         closed_tickets=closed_tickets,
                         category_stats=category_stats,
                         department_stats=department_stats,
                         staff_performance=staff_performance,
                         priority_stats=priority_stats,
                         status_stats=status_stats,
                         avg_resolution_time=avg_resolution_time,
                         resolution_times=resolution_times,
                         overdue_tickets=overdue_tickets,
                         trend_data=trend_data,
                         days=days,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         datetime=datetime,
                         now=datetime.utcnow,
                         tickets=tickets,
                         all_users=all_users,
                         all_categories=all_categories,
                         departments=departments,
                         created_by=created_by or '',
                         attended_by=attended_by or '',
                         status_filter=status_filter,
                         priority_filter=priority_filter,
                         category_filter=category_filter or '',
                         department_filter=department_filter,
                         location_filter=location_filter,
                         subunit_filter=subunit_filter)

@app.route('/admin/users')
@login_required
def user_management():
    if current_user.role != 'admin':
        abort(403)

    users = User.query.all()
    form = UserManagementForm()
    admin_user_form = AdminUserForm()
    category_form = CategoryForm()
    status_form = UserStatusForm()
    categories = Category.query.all()

    return render_template('user_management.html', users=users, form=form, 
                         admin_user_form=admin_user_form, category_form=category_form, 
                         status_form=status_form, categories=categories)

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

@app.route('/admin/users/create', methods=['POST'])
@login_required
def create_user():
    if current_user.role != 'admin':
        abort(403)

    form = AdminUserForm()
    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('user_management'))

        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Email already registered', 'danger')
            return redirect(url_for('user_management'))

        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            password_hash=generate_password_hash(form.password.data),
            role=form.role.data
        )
        db.session.add(user)
        db.session.commit()
        flash(f'User {user.full_name} created successfully', 'success')

    return redirect(url_for('user_management'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        abort(403)

    user = User.query.get_or_404(user_id)

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash('You cannot delete your own account', 'danger')
        return redirect(url_for('user_management'))

    # Update tickets created by this user to show deleted user
    tickets_created = Ticket.query.filter_by(created_by_id=user_id).all()
    for ticket in tickets_created:
        ticket.created_by_id = None

    # Remove user from assignees for all tickets
    tickets_assigned = Ticket.query.join(Ticket.assignees).filter(User.id == user_id).all()
    for ticket in tickets_assigned:
        ticket.assignees = [u for u in ticket.assignees if u.id != user_id]
        if ticket.status == 'in_progress' and not ticket.assignees:
            ticket.status = 'open'

    # Update comments by this user
    comments = Comment.query.filter_by(author_id=user_id).all()
    for comment in comments:
        comment.author_id = None

    # Delete the user
    db.session.delete(user)
    db.session.commit()

    flash(f'User {user.full_name} deleted successfully', 'success')
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
    elif current_user.role == 'intern' and current_user.id not in [u.id for u in ticket.assignees]:
        abort(403)

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/ticket/<int:ticket_id>/delete', methods=['POST'])
@login_required
def delete_ticket(ticket_id):
    if current_user.role != 'admin':
        abort(403)

    ticket = Ticket.query.get_or_404(ticket_id)

    # Delete associated records in the correct order
    # Delete ticket history first
    from models import TicketHistory
    TicketHistory.query.filter_by(ticket_id=ticket_id).delete()

    # Delete comments and attachments
    Comment.query.filter_by(ticket_id=ticket_id).delete()
    Attachment.query.filter_by(ticket_id=ticket_id).delete()

    # Clear assignees (many-to-many relationship)
    ticket.assignees.clear()

    # Delete the ticket
    db.session.delete(ticket)
    db.session.commit()

    flash('Ticket deleted successfully', 'success')
    return redirect(url_for('tickets_list'))

@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# Make datetime available in all templates
@app.context_processor
def inject_datetime():
    return dict(datetime=datetime)

@app.route('/api/ticket_descriptions')
@login_required
def api_ticket_descriptions():
    # Only allow for authenticated users
    descriptions = db.session.query(Ticket.description).order_by(Ticket.created_at.desc()).limit(100).all()
    # Remove duplicates and short entries
    unique_desc = list({d[0].strip() for d in descriptions if d[0] and len(d[0].strip()) > 10})
    return jsonify(unique_desc)

@app.route('/api/notifications')
@login_required
def api_notifications():
    """Get notifications for current user"""
    print(f"DEBUG: Loading notifications for user {current_user.id}")
    notifications = NotificationManager.get_user_notifications(current_user.id, limit=20)
    print(f"DEBUG: Found {len(notifications)} notifications")
    
    notification_data = []
    for notification in notifications:
        notification_data.append({
            'id': notification.id,
            'type': notification.type,
            'title': notification.title,
            'message': notification.message,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
            'ticket_id': notification.ticket_id,
            'link': url_for('ticket_detail', id=notification.ticket_id) if notification.ticket_id else None
        })
    
    return jsonify(notification_data)

@app.route('/api/notifications/unread_count')
@login_required
def api_unread_count():
    """Get count of unread notifications"""
    count = NotificationManager.get_unread_count(current_user.id)
    print(f"DEBUG: Unread count for user {current_user.id}: {count}")
    return jsonify({'count': count})

@app.route('/api/notifications/<int:notification_id>/mark_read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """Mark a notification as read"""
    success = NotificationManager.mark_as_read(notification_id, current_user.id)
    return jsonify({'success': success})

@app.route('/api/notifications/mark_all_read', methods=['POST'])
@login_required
def api_mark_all_read():
    """Mark all notifications as read"""
    count = NotificationManager.mark_all_as_read(current_user.id)
    return jsonify({'success': True, 'marked_count': count})

@app.route('/api/notifications/recent')
@login_required
def api_recent_notifications():
    """Get recent notifications since timestamp for real-time updates"""
    since_timestamp = request.args.get('since', type=int)
    if since_timestamp:
        since_datetime = datetime.fromtimestamp(since_timestamp / 1000)
        notifications = Notification.query.filter(
            Notification.user_id == current_user.id,
            Notification.created_at > since_datetime
        ).order_by(Notification.created_at.desc()).limit(10).all()
    else:
        notifications = []
    
    notification_data = []
    for notification in notifications:
        notification_data.append({
            'id': notification.id,
            'type': notification.type,
            'title': notification.title,
            'message': notification.message,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
            'ticket_id': notification.ticket_id,
            'link': url_for('ticket_detail', id=notification.ticket_id) if notification.ticket_id else None
        })
    
    return jsonify(notification_data)


@app.route('/analytics')
@login_required
def analytics_dashboard():
    if current_user.role != 'admin':
        abort(403)

    # Quick stats for last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)

    # Key performance indicators
    total_tickets = Ticket.query.filter(Ticket.created_at >= start_date).count()
    resolved_this_month = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.status.in_(['resolved', 'closed'])
    ).count()

    # SLA compliance (assuming 2-day target)
    sla_compliant = 0
    sla_total = 0
    for ticket in Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.status.in_(['resolved', 'closed']),
        Ticket.closed_at.isnot(None)
    ).all():
        sla_total += 1
        resolution_time = (ticket.closed_at - ticket.created_at).total_seconds() / 3600
        if resolution_time <= 48:  # 48 hours = 2 days
            sla_compliant += 1

    sla_percentage = (sla_compliant / sla_total * 100) if sla_total > 0 else 0

    # Top categories
    top_categories = db.session.query(
        Category.name,
        func.count(Ticket.id).label('count')
    ).join(Ticket, Category.id == Ticket.category_id)\
     .filter(Ticket.created_at >= start_date)\
     .group_by(Category.name)\
     .order_by(func.count(Ticket.id).desc())\
     .limit(5).all()

    return render_template('analytics_dashboard.html',
                         total_tickets=total_tickets,
                         resolved_this_month=resolved_this_month,
                         sla_percentage=sla_percentage,
                         top_categories=top_categories)

@app.route('/notifications/settings', methods=['GET', 'POST'])
@login_required
def notification_settings():
    """Manage notification settings for current user"""
    settings = NotificationSettings.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = NotificationSettings(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    form = NotificationSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        # Update settings from form
        form.populate_obj(settings)
        
        # Handle time fields specially - set to None if empty
        if form.dnd_start_time.data and form.dnd_start_time.data.strip():
            try:
                settings.dnd_start_time = datetime.strptime(form.dnd_start_time.data, '%H:%M').time()
            except ValueError:
                settings.dnd_start_time = None
        else:
            settings.dnd_start_time = None
            
        if form.dnd_end_time.data and form.dnd_end_time.data.strip():
            try:
                settings.dnd_end_time = datetime.strptime(form.dnd_end_time.data, '%H:%M').time()
            except ValueError:
                settings.dnd_end_time = None
        else:
            settings.dnd_end_time = None
        
        db.session.commit()
        flash('Notification settings updated successfully', 'success')
        return redirect(url_for('notification_settings'))
    
    return render_template('notification_settings.html', settings=settings, form=form)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allow users to change their own password"""
    form = PasswordChangeForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not check_password_hash(current_user.password_hash, form.current_password.data):
            flash('Current password is incorrect', 'danger')
            return render_template('change_password.html', form=form)
        
        # Update password
        current_user.password_hash = generate_password_hash(form.new_password.data)
        db.session.commit()
        
        flash('Password changed successfully', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html', form=form)

@app.route('/admin/users/<int:user_id>/toggle_status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Admin route to activate/deactivate user accounts"""
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        flash('You cannot deactivate your own account', 'danger')
        return redirect(url_for('user_management'))
    
    # Toggle status
    user.is_active = not user.is_active
    status_text = 'activated' if user.is_active else 'deactivated'
    
    # If deactivating, remove from all assigned tickets
    if not user.is_active:
        tickets_assigned = Ticket.query.join(Ticket.assignees).filter(User.id == user_id).all()
        for ticket in tickets_assigned:
            ticket.assignees = [u for u in ticket.assignees if u.id != user_id]
            if ticket.status == 'in_progress' and not ticket.assignees:
                ticket.status = 'open'
    
    db.session.commit()
    flash(f'User {user.full_name} has been {status_text}', 'success')
    return redirect(url_for('user_management'))



@app.route('/admin/pending_users')
@login_required
def pending_users():
    """Show pending user approvals"""
    if current_user.role != 'admin':
        abort(403)
    
    pending_users = User.query.filter_by(
        is_approved=False,
        is_verified=True,
        role='intern'
    ).order_by(User.created_at.desc()).all()
    
    return render_template('pending_users.html', pending_users=pending_users)

@app.route('/admin/users/<int:user_id>/approve', methods=['POST'])
@login_required
def approve_user_account(user_id):
    """Approve a pending user account"""
    if current_user.role != 'admin':
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    if user.is_approved:
        flash(f'{user.full_name} is already approved', 'info')
        return redirect(url_for('pending_users'))
    
    # Approve the user
    user.is_approved = True
    user.is_active = True
    user.approved_by_id = current_user.id
    user.approved_at = datetime.utcnow()
    
    db.session.commit()
    
    # Send notification to the approved user
    try:
        NotificationManager.notify_user_approved(user, current_user)
    except:
        pass  # Don't fail if notification fails
    
    flash(f'{user.full_name} has been approved and can now login', 'success')
    return redirect(url_for('pending_users'))