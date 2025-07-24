// Main JavaScript for ICT Helpdesk System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // File upload preview
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function(event) {
            const file = event.target.files[0];
            if (file) {
                const fileInfo = document.createElement('small');
                fileInfo.className = 'text-muted d-block mt-1';
                fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;

                // Remove existing file info
                const existingInfo = input.parentNode.querySelector('.file-info');
                if (existingInfo) {
                    existingInfo.remove();
                }

                fileInfo.className += ' file-info';
                input.parentNode.appendChild(fileInfo);
            }
        });
    });

    // Confirmation dialogs for destructive actions
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            const message = button.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(message)) {
                event.preventDefault();
            }
        });
    });

    // Real-time character counter for textareas
    const textareas = document.querySelectorAll('textarea[maxlength]');
    textareas.forEach(function(textarea) {
        const maxLength = textarea.getAttribute('maxlength');
        const counter = document.createElement('small');
        counter.className = 'text-muted float-end';
        textarea.parentNode.appendChild(counter);

        function updateCounter() {
            const remaining = maxLength - textarea.value.length;
            counter.textContent = `${textarea.value.length}/${maxLength}`;
            counter.className = remaining < 50 ? 'text-danger float-end' : 'text-muted float-end';
        }

        textarea.addEventListener('input', updateCounter);
        updateCounter();
    });

    // Auto-refresh ticket status (every 30 seconds)
    if (window.location.pathname.includes('/ticket/')) {
        setInterval(function() {
            refreshTicketStatus();
        }, 30000);
    }

    // Search functionality for tables
    const searchInputs = document.querySelectorAll('.table-search');
    searchInputs.forEach(function(input) {
        input.addEventListener('input', function() {
            const searchTerm = input.value.toLowerCase();
            const table = input.closest('.card').querySelector('table tbody');
            const rows = table.querySelectorAll('tr');

            rows.forEach(function(row) {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    });

    // New notification management system
document.addEventListener('DOMContentLoaded', function() {
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    const notificationsList = document.getElementById('notifications-list');
    const notificationBadge = document.getElementById('notification-badge');
    const markAllReadBtn = document.getElementById('mark-all-read');

    function loadNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(notifications => {
                notificationsList.innerHTML = '';

                if (notifications.length === 0) {
                    notificationsList.innerHTML = '<li><div class="dropdown-item text-muted text-center">No notifications</div></li>';
                } else {
                    notifications.forEach(notification => {
                        const listItem = document.createElement('li');
                        const isUnread = !notification.is_read;

                        listItem.innerHTML = `
                            <div class="dropdown-item notification-item ${isUnread ? 'notification-unread' : ''}" 
                                 data-notification-id="${notification.id}" 
                                 ${notification.link ? `onclick="handleNotificationClick(${notification.id}, '${notification.link}')"` : ''} 
                                 style="cursor: ${notification.link ? 'pointer' : 'default'};">
                                <div class="d-flex">
                                    <div class="flex-shrink-0 me-2">
                                        <i class="fas fa-${getNotificationIcon(notification.type)} ${getNotificationColor(notification.type)}"></i>
                                    </div>
                                    <div class="flex-grow-1">
                                        <h6 class="mb-1 ${isUnread ? 'fw-bold' : ''}">${notification.title}</h6>
                                        <p class="mb-1 small">${notification.message}</p>
                                        <small class="text-muted">${notification.created_at}</small>
                                        ${isUnread ? '<span class="badge bg-primary ms-2">New</span>' : ''}
                                    </div>
                                </div>
                            </div>
                        `;
                        notificationsList.appendChild(listItem);
                    });
                }
            })
            .catch(error => {
                console.error('Error loading notifications:', error);
                notificationsList.innerHTML = '<li><div class="dropdown-item text-danger text-center">Error loading notifications</div></li>';
            });
    }

    function updateUnreadCount() {
        fetch('/api/notifications/unread_count')
            .then(response => response.json())
            .then(data => {
                const count = data.count;
                notificationBadge.textContent = count;
                notificationBadge.style.display = count > 0 ? 'inline' : 'none';
            })
            .catch(error => {
                console.error('Error loading unread count:', error);
            });
    }

    function getNotificationIcon(type) {
        const icons = {
            'new_ticket': 'plus-circle',
            'ticket_updated': 'edit',
            'new_comment': 'comment',
            'ticket_closed': 'check-circle',
            'ticket_overdue': 'exclamation-triangle'
        };
        return icons[type] || 'bell';
    }

    function getNotificationColor(type) {
        const colors = {
            'new_ticket': 'text-success',
            'ticket_updated': 'text-warning',
            'new_comment': 'text-info',
            'ticket_closed': 'text-success',
            'ticket_overdue': 'text-danger'
        };
        return colors[type] || 'text-primary';
    }

    // Handle notification click
    window.handleNotificationClick = function(notificationId, link) {
        // Mark as read
        fetch(`/api/notifications/${notificationId}/mark_read`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        }).then(() => {
            updateUnreadCount();
            loadNotifications();
        });

        // Navigate to link
        if (link && link !== 'null') {
            window.location.href = link;
        }
    };

    // Mark all as read
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch('/api/notifications/mark_all_read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            }).then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateUnreadCount();
                    loadNotifications();
                    showNotification(`Marked ${data.marked_count} notifications as read`, 'success');
                }
            }).catch(error => {
                console.error('Error marking notifications as read:', error);
            });
        });
    }

    if (notificationsDropdown && notificationsList && notificationBadge) {
        // Initial load
        loadNotifications();
        updateUnreadCount();

        // Refresh every 30 seconds
        setInterval(() => {
            updateUnreadCount();
        }, 30000);

        // Load notifications when dropdown is opened
        notificationsDropdown.addEventListener('show.bs.dropdown', loadNotifications);
    }

    // Request notification permission on page load
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
});

    // Utility functions
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function refreshTicketStatus() {
    // Placeholder for future real-time status updates
    // Currently disabled to prevent console errors
}

function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Form helpers
function clearForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.reset();
        form.classList.remove('was-validated');
    }
}

function setFormData(formId, data) {
    const form = document.getElementById(formId);
    if (form) {
        Object.keys(data).forEach(key => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                field.value = data[key];
            }
        });
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl+N for new ticket
    if (event.ctrlKey && event.key === 'n') {
        event.preventDefault();
        window.location.href = '/ticket/new';
    }

    // Ctrl+D for dashboard
    if (event.ctrlKey && event.key === 'd') {
        event.preventDefault();
        window.location.href = '/dashboard';
    }

    // Escape to close modals
    if (event.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }
});

// Print functionality
function printTicket(ticketId) {
    const printWindow = window.open(`/ticket/${ticketId}/print`, '_blank');
    printWindow.onload = function() {
        printWindow.print();
        printWindow.close();
    };
}

// Export functionality
function exportTickets(format = 'csv') {
    const params = new URLSearchParams(window.location.search);
    params.set('export', format);
    window.location.href = `/tickets?${params.toString()}`;
}

// Theme toggler (if needed)
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
}

// Load saved theme
function loadTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-bs-theme', savedTheme);
}

// Initialize theme on load
loadTheme();