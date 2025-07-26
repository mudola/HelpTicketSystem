// Global variables and initialization
document.addEventListener('DOMContentLoaded', function() {
    // Notification system
    const notificationsDropdown = document.getElementById('notificationsDropdown');
    const notificationsList = document.getElementById('notifications-list');
    const notificationBadge = document.getElementById('notification-badge');
    const markAllReadBtn = document.getElementById('mark-all-read');

    // Load notifications
    function loadNotifications() {
        if (!notificationsList) return;

        fetch('/api/notifications')
            .then(response => response.json())
            .then(notifications => {
                if (notifications.length === 0) {
                    notificationsList.innerHTML = '<li class="dropdown-item text-center text-muted">No notifications</li>';
                    return;
                }

                notificationsList.innerHTML = '';
                notifications.forEach(notification => {
                    const notificationElement = document.createElement('li');
                    const isNew = !notification.is_read ? 'notification-new' : '';
                    const iconClass = getNotificationIcon(notification.type);
                    const colorClass = getNotificationColor(notification.type);

                    notificationElement.innerHTML = `
                        <a class="dropdown-item ${isNew}" href="#" onclick="handleNotificationClick(${notification.id}, '${notification.link || ''}')">
                            <div class="d-flex align-items-start">
                                <div class="flex-shrink-0 me-3">
                                    <i class="fas fa-${iconClass} ${colorClass}"></i>
                                </div>
                                <div class="flex-grow-1">
                                    <h6 class="mb-1">${notification.title}</h6>
                                    <p class="mb-1 small text-muted">${notification.message}</p>
                                    <small class="text-muted">${notification.created_at}</small>
                                </div>
                            </div>
                        </a>
                    `;
                    notificationsList.appendChild(notificationElement);
                });
            })
            .catch(error => {
                console.error('Error loading notifications:', error);
                if (notificationsList) {
                    notificationsList.innerHTML = '<li class="dropdown-item text-center text-danger">Error loading notifications</li>';
                }
            });
    }

    // Update unread count
    function updateUnreadCount() {
        fetch('/api/notifications/unread_count')
            .then(response => response.json())
            .then(data => {
                const count = data.count || 0;
                if (count > 0) {
                    notificationBadge.textContent = count > 99 ? '99+' : count;
                    notificationBadge.style.display = 'flex';
                    notificationBadge.classList.add('new-notification');

                    // Remove animation after 3 seconds
                    setTimeout(() => {
                        notificationBadge.classList.remove('new-notification');
                    }, 3000);
                } else {
                    notificationBadge.style.display = 'none';
                    notificationBadge.classList.remove('new-notification');
                }
            })
            .catch(error => {
                console.error('Error updating unread count:', error);
            });
    }

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

    // Utility functions
    function getNotificationIcon(type) {
        const icons = {
            'new_ticket': 'plus-circle',
            'ticket_updated': 'edit',
            'new_comment': 'comment',
            'ticket_closed': 'check-circle',
            'ticket_overdue': 'exclamation-triangle',
            'user_registered': 'user-plus',
            'account_approved': 'check-circle'
        };
        return icons[type] || 'bell';
    }

    function getNotificationColor(type) {
        const colors = {
            'new_ticket': 'text-success',
            'ticket_updated': 'text-warning',
            'new_comment': 'text-info',
            'ticket_closed': 'text-success',
            'ticket_overdue': 'text-danger',
            'user_registered': 'text-primary',
            'account_approved': 'text-success'
        };
        return colors[type] || 'text-primary';
    }

    // Show notification toast
    function showNotification(message, type = 'info') {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
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
        }).catch(error => {
            console.error('Error marking notification as read:', error);
        });

        // Navigate to link
        if (link && link !== 'null' && link !== 'None') {
            window.location.href = link;
        }
    };

    // Auto-complete for ticket descriptions
    const descriptionInput = document.getElementById('description');
    if (descriptionInput) {
        let suggestionsCache = [];

        // Load suggestions
        fetch('/api/ticket_descriptions')
            .then(response => response.json())
            .then(data => {
                suggestionsCache = data;
            })
            .catch(error => {
                console.error('Error loading ticket descriptions:', error);
            });

        // Create datalist for suggestions
        const datalist = document.createElement('datalist');
        datalist.id = 'description-suggestions';
        descriptionInput.setAttribute('list', 'description-suggestions');
        descriptionInput.parentNode.appendChild(datalist);

        // Update suggestions on input
        descriptionInput.addEventListener('input', function() {
            const value = this.value.toLowerCase();
            const matches = suggestionsCache.filter(desc => 
                desc.toLowerCase().includes(value)
            ).slice(0, 10);

            datalist.innerHTML = '';
            matches.forEach(match => {
                const option = document.createElement('option');
                option.value = match;
                datalist.appendChild(option);
            });
        });
    }

    // Enhanced form validation
    const forms = document.querySelectorAll('form[data-validate]');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });

            if (!isValid) {
                e.preventDefault();
                showNotification('Please fill in all required fields', 'danger');
            }
        });
    });

    // Real-time search functionality
    const searchInputs = document.querySelectorAll('[data-search]');
    searchInputs.forEach(input => {
        const targetTable = document.querySelector(input.dataset.search);
        if (targetTable) {
            input.addEventListener('input', function() {
                const searchTerm = this.value.toLowerCase();
                const rows = targetTable.querySelectorAll('tbody tr');

                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    row.style.display = text.includes(searchTerm) ? '' : 'none';
                });
            });
        }
    });

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Dynamic form handling
    const locationSelect = document.getElementById('location');
    const locationUnitSelect = document.getElementById('location_unit');
    const locationSubunitSelect = document.getElementById('location_subunit');
    const locationDetailSelect = document.getElementById('location_detail');

    if (locationUnitSelect && locationSubunitSelect && locationDetailSelect) {
        const subunits = {
            'SWA': ['LSHR', 'USHR'],
            'UHS': ['Staff clinic', 'Student clinic'],
            'Confucius': ['Block A', 'Block B', 'Block C']
        };

        const locations = {
            'LSHR': ['Location 1', 'Location 2'],
            'USHR': ['Location 3', 'Location 4'],
            'Staff clinic': ['Location 5', 'Location 6'],
            'Student clinic': ['Location 7', 'Location 8'],
            'Block A': ['Location 9', 'Location 10'],
            'Block B': ['Location 11', 'Location 12'],
            'Block C': ['Location 13', 'Location 14']
        };

        locationUnitSelect.addEventListener('change', function() {
            const selectedUnit = this.value;
            locationSubunitSelect.innerHTML = '<option value="">-- Select Subunit --</option>';
            locationDetailSelect.innerHTML = '<option value="">-- Select Location --</option>';

            if (selectedUnit && subunits[selectedUnit]) {
                subunits[selectedUnit].forEach(subunit => {
                    const option = document.createElement('option');
                    option.value = subunit;
                    option.textContent = subunit;
                    locationSubunitSelect.appendChild(option);
                });
            }
        });

        locationSubunitSelect.addEventListener('change', function() {
            const selectedSubunit = this.value;
            locationDetailSelect.innerHTML = '<option value="">-- Select Location --</option>';

            if (selectedSubunit && locations[selectedSubunit]) {
                locations[selectedSubunit].forEach(location => {
                    const option = document.createElement('option');
                    option.value = location;
                    option.textContent = location;
                    locationDetailSelect.appendChild(option);
                });
            }
        });
    }
});

// Global utility functions
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

function showPasswordModal(userId, userName) {
    const modal = document.getElementById('passwordModal');
    if (modal) {
        document.getElementById('userId').value = userId;
        document.getElementById('userName').textContent = userName;
        new bootstrap.Modal(modal).show();
    }
}

function showInternDetails(id, fullName, email, username, phone, registered) {
    const modal = document.getElementById('internDetailsModal');
    if (modal) {
        document.getElementById('internFullName').textContent = fullName;
        document.getElementById('internUsername').textContent = username;
        document.getElementById('internEmail').textContent = email;
        document.getElementById('internPhone').textContent = phone || 'N/A';
        document.getElementById('internRegistered').textContent = registered;
        new bootstrap.Modal(modal).show();
    }
}