
from datetime import datetime, time
from flask import url_for
from flask_mail import Message
from app import db, mail
from models import Notification, NotificationSettings, User, Ticket
import logging

logger = logging.getLogger(__name__)

class NotificationManager:
    """Centralized notification management system"""
    
    @staticmethod
    def create_notification(user_id, ticket_id, notification_type, title, message, send_email=True):
        """Create a new notification for a user"""
        try:
            # Get user's notification settings
            settings = NotificationSettings.query.filter_by(user_id=user_id).first()
            if not settings:
                # Create default settings if none exist
                settings = NotificationSettings(user_id=user_id)
                db.session.add(settings)
                db.session.flush()
            
            # Check if user wants this type of notification
            app_enabled = getattr(settings, f"{notification_type}_app", True)
            email_enabled = getattr(settings, f"{notification_type}_email", True)
            
            # Skip if user has disabled all notifications for this type
            if not app_enabled and not email_enabled:
                logger.info(f"User {user_id} has disabled {notification_type} notifications")
                return None
            
            # Check do not disturb settings
            if settings.do_not_disturb and settings.dnd_start_time and settings.dnd_end_time:
                current_time = datetime.now().time()
                if settings.dnd_start_time <= current_time <= settings.dnd_end_time:
                    logger.info(f"User {user_id} is in do not disturb mode")
                    app_enabled = False
                    email_enabled = False
            
            # Create in-app notification if enabled
            notification = None
            if app_enabled:
                notification = Notification(
                    user_id=user_id,
                    ticket_id=ticket_id,
                    type=notification_type,
                    title=title,
                    message=message
                )
                db.session.add(notification)
                logger.info(f"Created in-app notification for user {user_id}: {title}")
                print(f"DEBUG: Created notification - User: {user_id}, Type: {notification_type}, Title: {title}")
            
            # Send email if enabled
            if email_enabled and send_email:
                email_sent = NotificationManager.send_email_notification(user_id, ticket_id, title, message)
                if notification:
                    notification.email_sent = email_sent
            
            db.session.commit()
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            db.session.rollback()
            return None
    
    @staticmethod
    def send_email_notification(user_id, ticket_id, title, message):
        """Send email notification"""
        try:
            from app import app
            
            # Skip email if mail is not properly configured
            if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
                logger.warning("Email not configured - skipping email notification")
                return False
            
            user = User.query.get(user_id)
            ticket = Ticket.query.get(ticket_id) if ticket_id else None
            
            if not user or not user.email:
                return False
            
            ticket_link = url_for('ticket_detail', id=ticket_id, _external=True) if ticket_id else ""
            
            # Enhanced email template with better styling
            email_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #007bff; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                    .content {{ background: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; }}
                    .footer {{ background: #6c757d; color: white; padding: 10px 20px; text-align: center; font-size: 12px; border-radius: 0 0 5px 5px; }}
                    .btn {{ background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 0; }}
                    .priority-urgent {{ color: #dc3545; font-weight: bold; }}
                    .priority-high {{ color: #fd7e14; font-weight: bold; }}
                    .priority-medium {{ color: #ffc107; font-weight: bold; }}
                    .priority-low {{ color: #28a745; font-weight: bold; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>🎫 ICT Helpdesk Notification</h2>
                    </div>
                    <div class="content">
                        <h3>{title}</h3>
                        <p>{message}</p>
                        {f'<p><strong>Ticket ID:</strong> #{ticket.id}</p>' if ticket else ''}
                        {f'<p><strong>Location:</strong> {ticket.location}</p>' if ticket else ''}
                        {f'<p><strong>Status:</strong> {ticket.status.replace("_", " ").title()}</p>' if ticket else ''}
                        {f'<p><strong>Priority:</strong> <span class="priority-{ticket.priority.lower()}">{ticket.priority.title()}</span></p>' if ticket else ''}
                        {f'<p><strong>Created:</strong> {ticket.created_at.strftime("%Y-%m-%d %H:%M")}</p>' if ticket else ''}
                        {f'<a href="{ticket_link}" class="btn">📋 View Ticket Details</a>' if ticket_link else ''}
                    </div>
                    <div class="footer">
                        <p>ICT Helpdesk System - Automated Notification</p>
                        <p>Please do not reply to this email. Use the helpdesk system for all communications.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg = Message(
                subject=f"🎫 ICT Helpdesk - {title}",
                recipients=[user.email],
                html=email_body
            )
            
            mail.send(msg)
            
            # Also try to send SMS if phone number is available
            NotificationManager.send_sms_notification(user, title, message)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    @staticmethod
    def send_sms_notification(user, title, message):
        """Send SMS notification (placeholder for SMS service integration)"""
        try:
            # This is a placeholder - you would integrate with an SMS service like Twilio, Africa's Talking, etc.
            phone_number = getattr(user, 'phone_number', None)
            
            if not phone_number:
                logger.info(f"No phone number for user {user.id}, skipping SMS")
                return False
            
            # Example SMS message format
            sms_message = f"ICT Helpdesk: {title[:50]}{'...' if len(title) > 50 else ''}"
            
            # TODO: Integrate with SMS service provider
            # For now, just log the SMS attempt
            logger.info(f"SMS would be sent to {phone_number}: {sms_message}")
            
            # Uncomment and configure when SMS service is available:
            # import requests
            # sms_api_url = "YOUR_SMS_PROVIDER_API_URL"
            # response = requests.post(sms_api_url, {
            #     'to': phone_number,
            #     'message': sms_message,
            #     'api_key': 'YOUR_SMS_API_KEY'
            # })
            # return response.status_code == 200
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS notification: {e}")
            return False
    
    @staticmethod
    def notify_new_ticket(ticket):
        """Send notifications for new ticket creation"""
        # Notify all assignees
        for assignee in ticket.assignees:
            NotificationManager.create_notification(
                user_id=assignee.id,
                ticket_id=ticket.id,
                notification_type='new_ticket',
                title=f'New Ticket Assigned: #{ticket.id}',
                message=f'A new ticket has been assigned to you by {ticket.creator.full_name if ticket.creator else "Unknown"}.\n\nDescription: {ticket.description[:100]}{"..." if len(ticket.description) > 100 else ""}'
            )
        
        # Notify admins if no assignees
        if not ticket.assignees:
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                NotificationManager.create_notification(
                    user_id=admin.id,
                    ticket_id=ticket.id,
                    notification_type='new_ticket',
                    title=f'New Unassigned Ticket: #{ticket.id}',
                    message=f'A new ticket has been created by {ticket.creator.full_name if ticket.creator else "Unknown"} and needs assignment.\n\nDescription: {ticket.description[:100]}{"..." if len(ticket.description) > 100 else ""}'
                )
    
    @staticmethod
    def notify_ticket_updated(ticket, updated_by):
        """Send notifications for ticket updates"""
        recipients = set()
        
        # Add ticket creator
        if ticket.creator:
            recipients.add(ticket.creator.id)
        
        # Add all assignees
        for assignee in ticket.assignees:
            recipients.add(assignee.id)
        
        # Don't notify the person who made the update
        recipients.discard(updated_by.id)
        
        for user_id in recipients:
            NotificationManager.create_notification(
                user_id=user_id,
                ticket_id=ticket.id,
                notification_type='ticket_updated',
                title=f'Ticket Updated: #{ticket.id}',
                message=f'Ticket "{ticket.description[:50]}{"..." if len(ticket.description) > 50 else ""}" has been updated by {updated_by.full_name}.\n\nStatus: {ticket.status.title()}\nPriority: {ticket.priority.title()}'
            )
    
    @staticmethod
    def notify_new_comment(ticket, comment_author):
        """Send notifications for new comments"""
        recipients = set()
        
        # Add ticket creator
        if ticket.creator:
            recipients.add(ticket.creator.id)
        
        # Add all assignees
        for assignee in ticket.assignees:
            recipients.add(assignee.id)
        
        # Don't notify the comment author
        recipients.discard(comment_author.id)
        
        for user_id in recipients:
            NotificationManager.create_notification(
                user_id=user_id,
                ticket_id=ticket.id,
                notification_type='new_comment',
                title=f'New Comment on Ticket #{ticket.id}',
                message=f'{comment_author.full_name} added a comment to ticket "{ticket.description[:50]}{"..." if len(ticket.description) > 50 else ""}".'
            )
    
    @staticmethod
    def notify_ticket_closed(ticket, closed_by):
        """Send notifications for ticket closure"""
        if ticket.creator and ticket.creator.id != closed_by.id:
            NotificationManager.create_notification(
                user_id=ticket.creator.id,
                ticket_id=ticket.id,
                notification_type='ticket_closed',
                title=f'Ticket Closed: #{ticket.id}',
                message=f'Your ticket "{ticket.description[:50]}{"..." if len(ticket.description) > 50 else ""}" has been closed by {closed_by.full_name}.'
            )
    
    @staticmethod
    def notify_ticket_overdue(ticket):
        """Send notifications for overdue tickets"""
        # Notify all assignees
        for assignee in ticket.assignees:
            NotificationManager.create_notification(
                user_id=assignee.id,
                ticket_id=ticket.id,
                notification_type='ticket_overdue',
                title=f'Ticket Overdue: #{ticket.id}',
                message=f'Ticket "{ticket.description[:50]}{"..." if len(ticket.description) > 50 else ""}" is now overdue.\n\nDue date was: {ticket.due_date.strftime("%Y-%m-%d %H:%M") if ticket.due_date else "Not set"}'
            )
        
        # Notify admins
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            if admin.id not in [a.id for a in ticket.assignees]:
                NotificationManager.create_notification(
                    user_id=admin.id,
                    ticket_id=ticket.id,
                    notification_type='ticket_overdue',
                    title=f'Ticket Overdue: #{ticket.id}',
                    message=f'Ticket "{ticket.description[:50]}{"..." if len(ticket.description) > 50 else ""}" assigned to {", ".join([a.full_name for a in ticket.assignees])} is overdue.'
                )
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Mark a notification as read"""
        try:
            notification = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
            if notification and not notification.is_read:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        try:
            notifications = Notification.query.filter_by(user_id=user_id, is_read=False).all()
            for notification in notifications:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
            db.session.commit()
            return len(notifications)
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def get_user_notifications(user_id, limit=20, unread_only=False):
        """Get notifications for a user"""
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications for a user"""
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()
    
    @staticmethod
    def clear_all_notifications(user_id):
        """Delete all notifications for a user"""
        try:
            notifications = Notification.query.filter_by(user_id=user_id).all()
            count = len(notifications)
            for notification in notifications:
                db.session.delete(notification)
            db.session.commit()
            return count
        except Exception as e:
            logger.error(f"Error clearing all notifications: {e}")
            db.session.rollback()
            return 0
    
    @staticmethod
    def notify_new_user_registration(user):
        """Send notifications to admins about new user registration"""
        from models import User
        
        admins = User.query.filter_by(role='admin', is_active=True).all()
        for admin in admins:
            NotificationManager.create_notification(
                user_id=admin.id,
                ticket_id=None,
                notification_type='user_registered',
                title=f'New User Registration: {user.full_name}',
                message=f'A new {user.role} has registered and needs approval.\n\nName: {user.full_name}\nEmail: {user.email}\nUsername: {user.username}\nRole: {user.role.title()}\n\nPlease review and approve their account in the user management section.'
            )
    
    @staticmethod
    def notify_user_approved(user, approved_by):
        """Send notification to user when their account is approved"""
        NotificationManager.create_notification(
            user_id=user.id,
            ticket_id=None,
            notification_type='account_approved',
            title='Account Approved - Welcome to ICT Helpdesk!',
            message=f'Your account has been approved by {approved_by.full_name}.\n\nYou can now access the ICT Helpdesk system and start working with tickets.\n\nWelcome to the team!'
        )
