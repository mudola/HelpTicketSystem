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
from models import User, Ticket, Comment, Attachment, Category
from forms import LoginForm, RegistrationForm, TicketForm, CommentForm, TicketUpdateForm, UserManagementForm, CategoryForm, AdminUserForm
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
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data,
            password_hash=generate_password_hash(form.password.data),
            role=form.role.data,
            is_verified=False,
            verification_token=token
        )
        db.session.add(user)
        db.session.commit()

        # Send verification email
        verify_url = url_for('verify_email', token=token, _external=True)
        msg = Message('Verify Your Email - ICT Helpdesk', recipients=[user.email])
        msg.body = f"Hello {user.full_name},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nIf you did not register, please ignore this email."
        mail.send(msg)

        flash('Registration successful! Please check your email to verify your account.', 'info')
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
    
    # Enhanced metrics for advanced dashboard
    today = datetime.utcnow().date()
    
    # Today's tickets
    today_tickets = Ticket.query.filter(
        func.date(Ticket.created_at) == today
    ).count()
    
    # Pending tickets (open + in_progress)
    pending_tickets = Ticket.query.filter(
        Ticket.status.in_(['open', 'in_progress'])
    ).count()
    
    # Overdue tickets
    overdue_tickets = Ticket.query.filter(
        Ticket.due_date < datetime.utcnow(),
        Ticket.status.in_(['open', 'in_progress'])
    ).count()
    
    # Average resolution time (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    resolved_tickets = Ticket.query.filter(
        Ticket.status.in_(['resolved', 'closed']),
        Ticket.closed_at.isnot(None),
        Ticket.created_at >= thirty_days_ago
    ).all()
    
    avg_resolution_hours = 0
    if resolved_tickets:
        total_hours = sum([(t.closed_at - t.created_at).total_seconds() / 3600 for t in resolved_tickets])
        avg_resolution_hours = total_hours / len(resolved_tickets)
    
    # Most active technician (last 30 days)
    most_active = db.session.query(
        User.full_name,
        func.count(Ticket.id).label('ticket_count')
    ).join(User.assigned_tickets)\
     .filter(
         Ticket.created_at >= thirty_days_ago,
         User.role.in_(['admin', 'intern'])
     ).group_by(User.id, User.full_name)\
     .order_by(func.count(Ticket.id).desc())\
     .first()
    
    # Top recurring issue (last 30 days)
    top_category = db.session.query(
        Category.name,
        func.count(Ticket.id).label('count')
    ).join(Ticket, Category.id == Ticket.category_id)\
     .filter(Ticket.created_at >= thirty_days_ago)\
     .group_by(Category.name)\
     .order_by(func.count(Ticket.id).desc())\
     .first()
    
    # Chart data - Tickets by day (last 7 days)
    tickets_by_day = []
    for i in range(7):
        date = datetime.utcnow() - timedelta(days=i)
        count = Ticket.query.filter(
            func.date(Ticket.created_at) == date.date()
        ).count()
        tickets_by_day.append({
            'date': date.strftime('%a'),
            'count': count
        })
    tickets_by_day.reverse()
    
    # Chart data - Tickets by category (last 30 days)
    category_chart = db.session.query(
        Category.name,
        func.count(Ticket.id).label('count')
    ).join(Ticket, Category.id == Ticket.category_id)\
     .filter(Ticket.created_at >= thirty_days_ago)\
     .group_by(Category.name)\
     .limit(5).all()
    
    # Chart data - Tickets by department
    dept_stats = {}
    recent_dept_tickets = Ticket.query.filter(
        Ticket.created_at >= thirty_days_ago
    ).all()
    
    for ticket in recent_dept_tickets:
        dept = 'Other'
        for d in ['USHR', 'LSHR', 'Staff clinic', 'Student clinic', 'Block A', 'Block B', 'Block C', 'SWA', 'UHS', 'Confucius']:
            if d.lower() in ticket.location.lower():
                dept = d
                break
        dept_stats[dept] = dept_stats.get(dept, 0) + 1
    
    department_chart = [{'department': k, 'count': v} for k, v in dept_stats.items()]
    
    # Technician workload
    from sqlalchemy import case
    technician_workload = db.session.query(
        User.full_name,
        func.sum(case((Ticket.status == 'open', 1), else_=0)).label('open_count'),
        func.sum(case((Ticket.status == 'in_progress', 1), else_=0)).label('progress_count'),
        func.sum(case((Ticket.status.in_(['resolved', 'closed']), 1), else_=0)).label('completed_count')
    ).join(User.assigned_tickets)\
     .filter(User.role.in_(['admin', 'intern']))\
     .group_by(User.id, User.full_name).all()

    # Get recent activity with assignees eager-loaded
    recent_tickets = Ticket.query.options(joinedload(Ticket.assignees)).order_by(desc(Ticket.updated_at)).limit(10).all()

    # Get user statistics
    user_stats = db.session.query(
        User.role,
        func.count(User.id).label('count')
    ).group_by(User.role).all()
    
    # Recent alerts/notifications
    alerts = []
    if overdue_tickets > 0:
        alerts.append({
            'type': 'danger',
            'icon': 'fas fa-exclamation-triangle',
            'message': f'{overdue_tickets} tickets overdue',
            'link': url_for('tickets_list', status='overdue')
        })
    
    if today_tickets > 10:
        alerts.append({
            'type': 'warning',
            'icon': 'fas fa-bell',
            'message': f'{today_tickets} new tickets today',
            'link': url_for('tickets_list')
        })
    
    if pending_tickets > 20:
        alerts.append({
            'type': 'info',
            'icon': 'fas fa-clipboard-list',
            'message': f'{pending_tickets} tickets pending',
            'link': url_for('tickets_list', status='open')
        })

    return render_template('admin_dashboard.html', 
                         stats=stats, 
                         recent_tickets=recent_tickets, 
                         user_stats=user_stats,
                         today_tickets=today_tickets,
                         pending_tickets=pending_tickets,
                         overdue_tickets=overdue_tickets,
                         avg_resolution_hours=avg_resolution_hours,
                         most_active=most_active,
                         top_category=top_category,
                         tickets_by_day=tickets_by_day,
                         category_chart=category_chart,
                         department_chart=department_chart,
                         technician_workload=technician_workload,
                         alerts=alerts)

@app.route('/tickets')
@login_required
def tickets_list():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    overdue_filter = request.args.get('overdue', '')

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
    if overdue_filter == 'true':
        query = query.filter(
            Ticket.due_date < datetime.utcnow(),
            Ticket.status.in_(['open', 'in_progress'])
        )

    tickets = query.order_by(desc(Ticket.created_at)).paginate(
        page=page, per_page=10, error_out=False
    )

    return render_template('tickets_list.html', tickets=tickets, status_filter=status_filter, priority_filter=priority_filter, overdue_filter=overdue_filter)

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

        # Send notification email (now for all assignees)
        if ticket.assignees:
            send_notification_email(ticket, 'new_ticket')

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

        # Send notification email
        send_notification_email(ticket, 'ticket_updated')

        flash('Ticket updated successfully', 'success')

    return redirect(url_for('ticket_detail', id=id))

@app.route('/reports/print')
@login_required
def print_reports():
    """Print-friendly version of reports with current filters"""
    if current_user.role != 'admin':
        abort(403)
    
    # Get the same data as the regular reports page
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()
    
    # Filter parameters
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    
    # Build ticket query with filters
    ticket_query = Ticket.query.filter(
        Ticket.created_at >= start_date,
        Ticket.created_at <= end_date
    )
    
    if status_filter:
        ticket_query = ticket_query.filter(Ticket.status == status_filter)
    if priority_filter:
        ticket_query = ticket_query.filter(Ticket.priority == priority_filter)
    
    tickets = ticket_query.all()
    
    # Calculate statistics
    total_tickets = len(tickets)
    open_tickets = len([t for t in tickets if t.status == 'open'])
    in_progress_tickets = len([t for t in tickets if t.status == 'in_progress'])
    resolved_tickets = len([t for t in tickets if t.status == 'resolved'])
    closed_tickets = len([t for t in tickets if t.status == 'closed'])
    
    return render_template('reports_print.html',
                         total_tickets=total_tickets,
                         open_tickets=open_tickets,
                         in_progress_tickets=in_progress_tickets, 
                         resolved_tickets=resolved_tickets,
                         closed_tickets=closed_tickets,
                         tickets=tickets[:50],  # Limit for printing
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'),
                         generated_date=datetime.utcnow())

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

    flash('Ticket closed successfully', 'success')
    return redirect(url_for('ticket_detail', id=id))

@app.route('/reports/pdf')
@login_required
def reports_pdf():
    if current_user.role != 'admin':
        abort(403)

    # Use same logic as main reports route for consistency
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    # Custom date range
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

    # Enhanced filters
    days = request.args.get('days', 30, type=int)
    start_date = datetime.utcnow() - timedelta(days=days)
    end_date = datetime.utcnow()

    # Custom date range
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
    categories = Category.query.all()

    return render_template('user_management.html', users=users, form=form, 
                         admin_user_form=admin_user_form, category_form=category_form, categories=categories)

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

@app.route('/api/ticket_counts')
@login_required
def api_ticket_counts():
    """API endpoint to get current ticket counts for real-time updates"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get current ticket counts
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter_by(status='open').count()
    in_progress_tickets = Ticket.query.filter_by(status='in_progress').count()
    resolved_tickets = Ticket.query.filter_by(status='resolved').count()
    closed_tickets = Ticket.query.filter_by(status='closed').count()
    
    # Calculate overdue tickets
    overdue_tickets = Ticket.query.filter(
        Ticket.due_date < datetime.utcnow(),
        Ticket.status.in_(['open', 'in_progress'])
    ).count()
    
    return jsonify({
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'in_progress_tickets': in_progress_tickets,
        'resolved_tickets': resolved_tickets,
        'closed_tickets': closed_tickets,
        'overdue_tickets': overdue_tickets,
        'last_updated': datetime.utcnow().isoformat()
    })

@app.route('/api/notifications')
@login_required
def api_notifications():
    # Only for IT staff (interns, admins)
    if current_user.role not in ['admin', 'intern']:
        return jsonify([])

    from datetime import datetime, timedelta

    # Get tickets created in the last 24 hours or recently updated
    recent_cutoff = datetime.utcnow() - timedelta(hours=24)

    query = Ticket.query
    if current_user.role == 'intern':
        # For interns: show tickets assigned to them or newly created tickets
        query = query.filter(
            db.or_(
                Ticket.assignees.any(User.id == current_user.id),
                Ticket.created_at >= recent_cutoff
            )
        )
    # Admin can see all tickets

    recent_tickets = query.order_by(Ticket.created_at.desc()).limit(15).all()
    notifications = []

    for t in recent_tickets:
        # Determine notification type
        is_new = (datetime.utcnow() - t.created_at).total_seconds() < 3600  # Less than 1 hour old
        notification_type = 'new' if is_new else 'updated'

        notifications.append({
            'id': t.id,
            'type': notification_type,
            'title': f"{'New Ticket Created' if is_new else 'Ticket Updated'}",
            'description': t.description[:60] + ('...' if len(t.description) > 60 else ''),
            'status': t.status,
            'priority': t.priority,
            'created_at': t.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': t.updated_at.strftime('%Y-%m-%d %H:%M'),
            'created_by': t.creator.full_name if t.creator else 'Unknown',
            'link': url_for('ticket_detail', id=t.id)
        })
    return jsonify(notifications)


@app.route('/analytics')
@login_required
def analytics_dashboard():
    if current_user.role != 'admin':
        abort(403)

    # Quick stats for last 30 days
    start_date = datetime.utcnow() - timedelta(days=30)

    # Current ticket status counts
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter_by(status='open').count()
    in_progress_tickets = Ticket.query.filter_by(status='in_progress').count()
    resolved_tickets = Ticket.query.filter_by(status='resolved').count()
    closed_tickets = Ticket.query.filter_by(status='closed').count()
    
    # Overdue tickets
    overdue_tickets = Ticket.query.filter(
        Ticket.due_date < datetime.utcnow(),
        Ticket.status.in_(['open', 'in_progress'])
    ).count()

    # Daily stats (today)
    today = datetime.utcnow().date()
    daily_total = Ticket.query.filter(func.date(Ticket.created_at) == today).count()
    daily_in_progress = Ticket.query.filter(
        func.date(Ticket.created_at) == today,
        Ticket.status == 'in_progress'
    ).count()
    daily_resolved = Ticket.query.filter(
        func.date(Ticket.created_at) == today,
        Ticket.status.in_(['resolved', 'closed'])
    ).count()
    daily_closed = Ticket.query.filter(
        func.date(Ticket.created_at) == today,
        Ticket.status == 'closed'
    ).count()

    # Weekly stats (last 7 days)
    week_start = datetime.utcnow() - timedelta(days=7)
    weekly_total = Ticket.query.filter(Ticket.created_at >= week_start).count()
    weekly_open = Ticket.query.filter(
        Ticket.created_at >= week_start,
        Ticket.status == 'open'
    ).count()
    weekly_in_progress = Ticket.query.filter(
        Ticket.created_at >= week_start,
        Ticket.status == 'in_progress'
    ).count()
    weekly_resolved = Ticket.query.filter(
        Ticket.created_at >= week_start,
        Ticket.status == 'resolved'
    ).count()
    weekly_closed = Ticket.query.filter(
        Ticket.created_at >= week_start,
        Ticket.status == 'closed'
    ).count()

    # Key performance indicators for last 30 days
    monthly_total = Ticket.query.filter(Ticket.created_at >= start_date).count()
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
                         open_tickets=open_tickets,
                         in_progress_tickets=in_progress_tickets,
                         resolved_tickets=resolved_tickets,
                         closed_tickets=closed_tickets,
                         overdue_tickets=overdue_tickets,
                         daily_total=daily_total,
                         daily_in_progress=daily_in_progress,
                         daily_resolved=daily_resolved,
                         daily_closed=daily_closed,
                         weekly_total=weekly_total,
                         weekly_open=weekly_open,
                         weekly_in_progress=weekly_in_progress,
                         weekly_resolved=weekly_resolved,
                         weekly_closed=weekly_closed,
                         monthly_total=monthly_total,
                         resolved_this_month=resolved_this_month,
                         sla_percentage=sla_percentage,
                         top_categories=top_categories)