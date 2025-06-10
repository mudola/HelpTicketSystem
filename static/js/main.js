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
    // This would typically make an AJAX call to get updated ticket status
    // For now, we'll just reload the page if there are any updates
    const ticketId = window.location.pathname.split('/').pop();
    if (ticketId && !isNaN(ticketId)) {
        fetch(`/api/ticket/${ticketId}/status`)
            .then(response => response.json())
            .then(data => {
                if (data.updated) {
                    // Show notification that ticket has been updated
                    showNotification('Ticket has been updated by another user. Refreshing...', 'info');
                    setTimeout(() => window.location.reload(), 2000);
                }
            })
            .catch(error => console.log('Status check failed:', error));
    }
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
