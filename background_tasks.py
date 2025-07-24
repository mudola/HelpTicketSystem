
from datetime import datetime, timedelta
from app import app, db
from models import Ticket
from notification_utils import NotificationManager
import logging

logger = logging.getLogger(__name__)

def check_overdue_tickets():
    """Check for overdue tickets and send notifications"""
    with app.app_context():
        try:
            # Find tickets that are overdue
            now = datetime.utcnow()
            overdue_tickets = Ticket.query.filter(
                Ticket.due_date < now,
                Ticket.status.in_(['open', 'in_progress']),
                Ticket.due_date.isnot(None)
            ).all()
            
            for ticket in overdue_tickets:
                # Check if we already sent an overdue notification today
                from models import Notification
                today = datetime.utcnow().date()
                existing_notification = Notification.query.filter(
                    Notification.ticket_id == ticket.id,
                    Notification.type == 'ticket_overdue',
                    db.func.date(Notification.created_at) == today
                ).first()
                
                if not existing_notification:
                    NotificationManager.notify_ticket_overdue(ticket)
                    logger.info(f"Sent overdue notification for ticket #{ticket.id}")
            
            return len(overdue_tickets)
            
        except Exception as e:
            logger.error(f"Error checking overdue tickets: {e}")
            return 0

def cleanup_old_notifications():
    """Clean up old notifications (older than 30 days)"""
    with app.app_context():
        try:
            from models import Notification
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            old_notifications = Notification.query.filter(
                Notification.created_at < cutoff_date,
                Notification.is_read == True
            ).all()
            
            for notification in old_notifications:
                db.session.delete(notification)
            
            db.session.commit()
            logger.info(f"Cleaned up {len(old_notifications)} old notifications")
            return len(old_notifications)
            
        except Exception as e:
            logger.error(f"Error cleaning up notifications: {e}")
            db.session.rollback()
            return 0

if __name__ == "__main__":
    # Run tasks manually for testing
    print(f"Checked {check_overdue_tickets()} overdue tickets")
    print(f"Cleaned up {cleanup_old_notifications()} old notifications")
