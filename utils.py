from datetime import datetime, timedelta
from flask_mail import Message
from flask import url_for
from sqlalchemy import func
from app import mail, db
from models import Ticket, User, Comment

def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    stats = {}
    
    if user.role == 'admin':
        # Admin sees all tickets
        stats['total_tickets'] = Ticket.query.count()
        stats['open_tickets'] = Ticket.query.filter_by(status='open').count()
        stats['in_progress_tickets'] = Ticket.query.filter_by(status='in_progress').count()
        stats['resolved_tickets'] = Ticket.query.filter_by(status='resolved').count()
        stats['closed_tickets'] = Ticket.query.filter_by(status='closed').count()
        
        # For admin, also show tickets that are open but assigned (should be in_progress)
        open_assigned = Ticket.query.filter(
            Ticket.status == 'open',
            Ticket.assignees.any(id=user.id)
        ).count()
        stats['open_tickets'] -= open_assigned
        stats['in_progress_tickets'] += open_assigned
        
    elif user.role == 'intern':
        # Intern sees assigned tickets
        stats['assigned_tickets'] = Ticket.query.filter(Ticket.assignees.any(id=user.id)).count()
        stats['my_open_tickets'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'open').count()
        stats['my_in_progress'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'in_progress').count()
        stats['my_resolved'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'resolved').count()
        stats['my_closed'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'closed').count()
        
    else:  # user role
        # User sees their own tickets
        user_tickets = Ticket.query.filter_by(created_by_id=user.id)
        stats['my_tickets'] = user_tickets.count()
        
        # For users, show actual status but consider assigned+open as in_progress
        stats['my_open'] = user_tickets.filter(
            Ticket.status == 'open',
            Ticket.assigned_to_id.is_(None)
        ).count()
        
        stats['my_in_progress'] = (
            user_tickets.filter_by(status='in_progress').count() +
            user_tickets.filter(
                Ticket.status == 'open',
                Ticket.assigned_to_id.isnot(None)
            ).count()
        )
        
        stats['my_resolved'] = user_tickets.filter_by(status='resolved').count()
        stats['my_closed'] = user_tickets.filter_by(status='closed').count()
    
    return stats

def send_notification_email(ticket, event_type):
    """Send notification email for ticket events"""
    try:
        recipients = []
        subject = ""
        template = ""
        
        if event_type == 'new_ticket':
            if ticket.assignee:
                recipients.append(ticket.assignee.email)
            subject = f"New Ticket Assigned: #{ticket.id} - {ticket.title}"
            template = f"""
            A new ticket has been assigned to you:
            
            Ticket ID: #{ticket.id}
            Title: {ticket.title}
            Priority: {ticket.priority}
            Created by: {ticket.creator.full_name}
            
            Please log in to the helpdesk system to view details.
            """
            
        elif event_type == 'ticket_updated':
            recipients.append(ticket.creator.email)
            if ticket.assignee and ticket.assignee.email != ticket.creator.email:
                recipients.append(ticket.assignee.email)
            subject = f"Ticket Updated: #{ticket.id} - {ticket.title}"
            template = f"""
            A ticket has been updated:
            
            Ticket ID: #{ticket.id}
            Title: {ticket.title}
            Status: {ticket.status}
            Priority: {ticket.priority}
            
            Please log in to the helpdesk system to view details.
            """
            
        elif event_type == 'new_comment':
            recipients.append(ticket.creator.email)
            if ticket.assignee and ticket.assignee.email != ticket.creator.email:
                recipients.append(ticket.assignee.email)
            subject = f"New Comment on Ticket: #{ticket.id} - {ticket.title}"
            template = f"""
            A new comment has been added to your ticket:
            
            Ticket ID: #{ticket.id}
            Title: {ticket.title}
            
            Please log in to the helpdesk system to view the comment.
            """
        
        if recipients:
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=template
            )
            mail.send(msg)
            
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def send_notification_email(ticket, event_type):
    """Send email notifications for ticket events"""
    try:
        recipients = []
        
        # Add ticket creator
        if ticket.creator and ticket.creator.email:
            recipients.append(ticket.creator.email)
        
        # Add assigned user
        if ticket.assignee and ticket.assignee.email:
            recipients.append(ticket.assignee.email)
        
        # Remove duplicates
        recipients = list(set(recipients))
        
        if not recipients:
            return
        
        subject_map = {
            'new_ticket': f'New Ticket Created: {ticket.title}',
            'ticket_updated': f'Ticket Updated: {ticket.title}',
            'new_comment': f'New Comment on Ticket: {ticket.title}'
        }
        
        subject = subject_map.get(event_type, f'Ticket Notification: {ticket.title}')
        
        msg = Message(
            subject=subject,
            recipients=recipients,
            html=f"""
            <h3>{subject}</h3>
            <p><strong>Ticket ID:</strong> #{ticket.id}</p>
            <p><strong>Title:</strong> {ticket.title}</p>
            <p><strong>Status:</strong> {ticket.status.title()}</p>
            <p><strong>Priority:</strong> {ticket.priority.title()}</p>
            <p><strong>Created by:</strong> {ticket.creator.full_name}</p>
            {f'<p><strong>Assigned to:</strong> {ticket.assignee.full_name}</p>' if ticket.assignee else ''}
            <p><a href="{url_for('ticket_detail', id=ticket.id, _external=True)}">View Ticket</a></p>
            """
        )
        
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email notification: {e}")

def get_dashboard_stats(user):
    """Get dashboard statistics based on user role"""
    stats = {}
    
    if user.role == 'admin':
        stats['total_tickets'] = Ticket.query.count()
        stats['open_tickets'] = Ticket.query.filter_by(status='open').count()
        stats['in_progress_tickets'] = Ticket.query.filter_by(status='in_progress').count()
        stats['closed_tickets'] = Ticket.query.filter_by(status='closed').count()
        stats['total_users'] = User.query.count()
        
        # Urgent tickets
        stats['urgent_tickets'] = Ticket.query.filter_by(priority='urgent').filter(
            Ticket.status.in_(['open', 'in_progress'])
        ).count()
        
    elif user.role == 'intern':
        stats['assigned_tickets'] = Ticket.query.filter(Ticket.assignees.any(id=user.id)).count()
        stats['my_open_tickets'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'open').count()
        stats['my_in_progress'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'in_progress').count()
        stats['my_resolved'] = Ticket.query.filter(Ticket.assignees.any(id=user.id), Ticket.status == 'resolved').count()
        
    else:  # user
        stats['my_tickets'] = Ticket.query.filter_by(created_by_id=user.id).count()
        stats['my_open'] = Ticket.query.filter_by(
            created_by_id=user.id, status='open'
        ).count()
        stats['my_in_progress'] = Ticket.query.filter_by(
            created_by_id=user.id, status='in_progress'
        ).count()
        stats['my_closed'] = Ticket.query.filter_by(
            created_by_id=user.id, status='closed'
        ).count()
    
    return stats

def get_priority_badge_class(priority):
    """Get Bootstrap badge class for priority"""
    classes = {
        'low': 'bg-secondary',
        'medium': 'bg-warning',
        'high': 'bg-danger',
        'urgent': 'bg-danger'
    }
    return classes.get(priority, 'bg-secondary')

def get_status_badge_class(status):
    """Get Bootstrap badge class for status"""
    classes = {
        'open': 'bg-primary',
        'in_progress': 'bg-warning',
        'resolved': 'bg-success',
        'closed': 'bg-secondary'
    }
    return classes.get(status, 'bg-secondary')

def format_datetime(dt):
    """Format datetime for display"""
    if not dt:
        return 'N/A'
    return dt.strftime('%Y-%m-%d %H:%M')

def time_ago(dt):
    """Get human-readable time difference"""
    if not dt:
        return 'N/A'
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

# Template filters
def nl2br(value):
    """Convert newlines to HTML line breaks"""
    if not value:
        return value
    return value.replace('\n', '<br>')

def register_template_filters(app):
    app.jinja_env.filters['priority_badge'] = get_priority_badge_class
    app.jinja_env.filters['status_badge'] = get_status_badge_class
    app.jinja_env.filters['format_datetime'] = format_datetime
    app.jinja_env.filters['time_ago'] = time_ago
    app.jinja_env.filters['nl2br'] = nl2br

# Register filters
from app import app as flask_app
register_template_filters(flask_app)
