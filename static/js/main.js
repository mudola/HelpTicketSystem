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

    // Notifications polling for IT staff
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    const notificationsList = document.getElementById('notifications-list');
    const notificationBadge = document.getElementById('notification-badge');

    let lastNotificationCheck = new Date();

    function fetchNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                if (data.notifications && data.notifications.length > 0) {
                    notificationsList.innerHTML = '';
                    let unreadCount = 0;
                    data.notifications.forEach(n => {
                        const li = document.createElement('li');
                        li.innerHTML = `<a href="${n.url || '#'}" class="dropdown-item${n.unread ? ' fw-bold' : ''}">
                            <span class="me-2"><i class="${n.icon || 'fas fa-ticket-alt'}"></i></span>
                            ${n.message}
                            <br><span class="text-muted small">${n.time_ago}</span>
                        </a>`;
                        notificationsList.appendChild(li);
                        if (n.unread) unreadCount++;
                    });
                    notificationBadge.textContent = unreadCount;
                    notificationBadge.classList.toggle('d-none', unreadCount === 0);
                } else {
                    notificationsList.innerHTML = '<span class="dropdown-item text-muted small">No new notifications</span>';
                    notificationBadge.classList.add('d-none');
                }
            })
            .catch(() => {
                notificationsList.innerHTML = '<span class="dropdown-item text-danger small">Error loading notifications</span>';
                notificationBadge.classList.add('d-none');
            });
    }

    if (notificationsDropdown && notificationsList && notificationBadge) {
        fetchNotifications();
        setInterval(fetchNotifications, 30000); // Poll every 30 seconds
        notificationsDropdown.addEventListener('show.bs.dropdown', fetchNotifications);
    }

    // Auto-refresh notifications every 30 seconds
    setInterval(loadNotifications, 30000);

    // Function to show desktop notifications for new tickets
    function showDesktopNotification(ticket) {
        if ("Notification" in window && Notification.permission === "granted") {
            const notification = new Notification(`New Ticket #${ticket.id}`, {
                body: `${ticket.description}\nPriority: ${ticket.priority.toUpperCase()}`,
                icon: '/static/favicon.ico',
                tag: `ticket-${ticket.id}`
            });

            notification.onclick = function() {
                window.open(ticket.link, '_blank');
                notification.close();
            };
        }
    }

    // Request notification permission on page load
    document.addEventListener('DOMContentLoaded', function() {
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission();
        }
    });

    function loadNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(notifications => {
                const dropdown = document.getElementById('notifications-dropdown');
                const badge = document.getElementById('notifications-badge');

                if (notifications.length === 0) {
                    dropdown.innerHTML = '<li><a class="dropdown-item text-muted" href="#">No new notifications</a></li>';
                    badge.style.display = 'none';
                    return;
                }

                dropdown.innerHTML = '';
                let newTicketCount = 0;

                notifications.forEach(notification => {
                    const item = document.createElement('li');
                    const isNew = notification.type === 'new';
                    const notificationClass = isNew ? 'notification-new' : 'notification-updated';
                    const icon = isNew ? '🎫' : '📝';

                    item.innerHTML = `
                        <a class="dropdown-item ${notificationClass}" href="${notification.link}">
                            <div class="notification-item">
                                <div class="d-flex justify-content-between">
                                    <strong>${icon} Ticket #${notification.id}</strong>
                                    <small class="badge bg-${notification.priority === 'urgent' ? 'danger' : notification.priority === 'high' ? 'warning' : 'secondary'}">${notification.priority}</small>
                                </div>
                                <div class="mt-1">
                                    <small>${notification.description}</small>
                                </div>
                                <div class="d-flex justify-content-between mt-1">
                                    <small class="text-muted">${isNew ? 'Created' : 'Updated'}: ${isNew ? notification.created_at : notification.updated_at}</small>
                                    <small class="text-muted">by ${notification.created_by}</small>
                                </div>
                            </div>
                        </a>
                    `;
                    dropdown.appendChild(item);

                    // Check if this is a new ticket created since last check
                    const ticketTime = new Date(notification.created_at);
                    if (isNew && ticketTime > lastNotificationCheck) {
                        newTicketCount++;
                        showDesktopNotification(notification);
                    }
                });

                lastNotificationCheck = new Date();
                badge.textContent = notifications.length;
                badge.style.display = notifications.length > 0 ? 'inline' : 'none';

                // Show visual alert for new tickets
                if (newTicketCount > 0) {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-info alert-dismissible fade show position-fixed';
                    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
                    alertDiv.innerHTML = `
                        <strong>New Ticket${newTicketCount > 1 ? 's' : ''} Created!</strong>
                        ${newTicketCount > 1 ? `${newTicketCount} new tickets have` : 'A new ticket has'} been created.
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
            })
            .catch(error => console.error('Error loading notifications:', error));
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