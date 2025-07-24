let currentPage = 1;
let totalPages = 1;
let currentFilters = {};

// Load logs data
async function loadLogs(page = 1, filters = {}) {
    try {
        // Build API URL with query parameters
        const params = new URLSearchParams();
        params.append('limit', '50');
        params.append('skip', (page - 1) * 50);
        
        if (filters.status) params.append('status', filters.status);
        if (filters.service) params.append('service', filters.service);
        if (filters.action) params.append('action', filters.action);
        if (filters.date) params.append('date_range', filters.date);
        
        const url = `/api/logs?${params.toString()}`;
        const response = await apiRequest(url);
        
        if (response && response.length > 0) {
            displayLogs(response);
            updatePagination(page, Math.ceil(response.length / 50));
        } else {
            showEmptyState();
        }
        
    } catch (error) {
        console.error('Failed to load logs:', error);
        showEmptyState();
    }
}

function displayLogs(logs) {
    const tbody = document.getElementById('logs-table-body');
    
    if (logs.length === 0) {
        showEmptyState();
        return;
    }
    
    let html = '';
    logs.forEach(log => {
        const statusBadge = getStatusBadge(log.status);
        const serviceBadge = getServiceBadge(log.service);
        const actionBadge = getActionBadge(log.action);
        
        // Format media title and timestamp
        const formattedTitle = formatMediaTitle(log);
        const formattedTime = formatTimestamp(log.created_at);
        
        html += `
            <tr>
                <td>
                    <small>${formattedTime}</small>
                </td>
                <td>
                    <strong>${formattedTitle}</strong>
                    <br>
                    <small class="text-muted">${log.jellyfin_id}</small>
                </td>
                <td>${actionBadge}</td>
                <td>${serviceBadge}</td>
                <td>${statusBadge}</td>
                <td>
                    ${log.error_message ? 
                        `<span class="text-danger" title="${log.error_message}">
                            <i class="fas fa-exclamation-triangle"></i>
                        </span>` : 
                        '<span class="text-muted">-</span>'
                    }
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="showLogDetail(${log.id})" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    ${log.status === 'failed' ? 
                        `<button class="btn btn-sm btn-outline-warning" onclick="retrySync(${log.id})" title="Retry Sync">
                            <i class="fas fa-redo"></i>
                        </button>` : 
                        ''
                    }
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    document.getElementById('empty-state').style.display = 'none';
    document.querySelector('.table-responsive').style.display = 'block';
}

function getStatusBadge(status) {
    const badges = {
        'completed': '<span class="badge bg-success">Completed</span>',
        'failed': '<span class="badge bg-danger">Failed</span>',
        'processing': '<span class="badge bg-primary">Processing</span>',
        'pending': '<span class="badge bg-warning">Pending</span>'
    };
    return badges[status] || `<span class="badge bg-secondary">${status}</span>`;
}

function getServiceBadge(service) {
    const badges = {
        'sonarr': '<span class="badge bg-success">Sonarr</span>',
        'radarr': '<span class="badge bg-warning text-dark">Radarr</span>'
    };
    return badges[service] || `<span class="badge bg-secondary">${service}</span>`;
}

function getActionBadge(action) {
    const badges = {
        'monitor': '<span class="badge bg-primary"><i class="fas fa-plus me-1"></i>Monitor</span>',
        'unmonitor': '<span class="badge bg-dark"><i class="fas fa-minus me-1"></i>Unmonitor</span>'
    };
    return badges[action] || `<span class="badge bg-secondary">${action}</span>`;
}

function showEmptyState() {
    document.querySelector('.table-responsive').style.display = 'none';
    document.getElementById('pagination-container').style.display = 'none';
    document.getElementById('empty-state').style.display = 'block';
}

function updatePagination(page, total) {
    currentPage = page;
    totalPages = total;
    
    document.getElementById('current-page').textContent = page;
    
    if (total > 1) {
        document.getElementById('pagination-container').style.display = 'block';
    } else {
        document.getElementById('pagination-container').style.display = 'none';
    }
}

function loadPage(page) {
    if (page < 1 || page > totalPages) return;
    loadLogs(page, currentFilters);
}

function applyFilters() {
    currentFilters = {
        status: document.getElementById('filter-status').value,
        service: document.getElementById('filter-service').value,
        action: document.getElementById('filter-action').value,
        date: document.getElementById('filter-date').value
    };
    
    loadLogs(1, currentFilters);
}

function clearFilters() {
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-service').value = '';
    document.getElementById('filter-action').value = '';
    document.getElementById('filter-date').value = '';
    
    currentFilters = {};
    loadLogs(1, {});
}

function refreshLogs() {
    loadLogs(currentPage, currentFilters);
}

function exportLogs() {
    // This would trigger a download of logs in CSV format
    alert('Export functionality coming soon!');
}

async function showLogDetail(logId) {
    try {
        // Fetch detailed log information from API
        const logDetail = await apiRequest(`/api/logs/${logId}`);
        
        const statusBadge = getStatusBadge(logDetail.status);
        const serviceBadge = getServiceBadge(logDetail.service);
        const actionBadge = getActionBadge(logDetail.action);
        
        const detailHtml = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Log Information</h6>
                    <table class="table table-sm">
                        <tr><td><strong>ID:</strong></td><td>${logDetail.id}</td></tr>
                        <tr><td><strong>Timestamp:</strong></td><td>${formatTimestamp(logDetail.created_at)}</td></tr>
                        <tr><td><strong>Status:</strong></td><td>${statusBadge}</td></tr>
                        <tr><td><strong>Action:</strong></td><td>${actionBadge}</td></tr>
                        <tr><td><strong>Service:</strong></td><td>${serviceBadge}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h6>Media Information</h6>
                    <table class="table table-sm">
                        <tr><td><strong>Title:</strong></td><td>${formatMediaTitle(logDetail)}</td></tr>
                        <tr><td><strong>Jellyfin ID:</strong></td><td>${logDetail.jellyfin_id}</td></tr>
                        <tr><td><strong>Type:</strong></td><td>${logDetail.media_type || 'Unknown'}</td></tr>
                        <tr><td><strong>External ID:</strong></td><td>${logDetail.external_id || '-'}</td></tr>
                    </table>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-12">
                    <h6>Processing Details</h6>
                    ${logDetail.error_message ? 
                        `<div class="alert alert-danger">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            ${logDetail.error_message}
                        </div>` : 
                        `<div class="alert alert-success">
                            <i class="fas fa-check-circle me-2"></i>
                            Successfully processed sync operation
                        </div>`
                    }
                </div>
            </div>
        `;
        
        document.getElementById('log-detail-body').innerHTML = detailHtml;
        
        // Set current log ID and show/hide retry button
        currentLogId = logId;
        const retryButton = document.getElementById('retry-button');
        if (logDetail.status === 'failed') {
            retryButton.style.display = 'inline-block';
        } else {
            retryButton.style.display = 'none';
        }
        
        new bootstrap.Modal(document.getElementById('logDetailModal')).show();
        
    } catch (error) {
        console.error('Failed to load log details:', error);
        alert('Failed to load log details');
    }
}

let currentLogId = null;

async function retrySync(logId) {
    if (!logId) {
        alert('Invalid log ID');
        return;
    }
    
    if (!confirm('Are you sure you want to retry this sync operation?')) {
        return;
    }
    
    try {
        const response = await apiRequest(`/api/logs/${logId}/retry`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.status === 'retry_started') {
            showNotification('success', `Retry initiated for ${response.media_title}`);
            // Refresh the logs to show updated status
            setTimeout(() => refreshLogs(), 1000);
        } else {
            showNotification('error', 'Failed to initiate retry');
        }
        
    } catch (error) {
        console.error('Failed to retry sync:', error);
        showNotification('error', `Failed to retry sync: ${error.message || 'Unknown error'}`);
    }
}

async function retryCurrentLog() {
    if (currentLogId) {
        await retrySync(currentLogId);
        // Close the modal
        bootstrap.Modal.getInstance(document.getElementById('logDetailModal')).hide();
        currentLogId = null;
    }
}

async function bulkRetryFailed() {
    if (!confirm('This will retry all failed syncs from the last 24 hours. Continue?')) {
        return;
    }
    
    try {
        const response = await apiRequest('/api/logs/retry/bulk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.status === 'bulk_retry_started') {
            showNotification('success', `Bulk retry initiated for ${response.retried_count} failed syncs`);
            // Refresh the logs to show updated status
            setTimeout(() => refreshLogs(), 2000);
        } else if (response.status === 'no_failed_logs') {
            showNotification('info', response.message);
        } else {
            showNotification('error', 'Failed to initiate bulk retry');
        }
        
    } catch (error) {
        console.error('Failed to bulk retry:', error);
        showNotification('error', `Failed to bulk retry: ${error.message || 'Unknown error'}`);
    }
}

function showNotification(type, message) {
    // Create a notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}


// Initialize logs page
document.addEventListener('DOMContentLoaded', function() {
    loadLogs();
    
    // Auto-refresh every 30 seconds
    setInterval(() => {
        if (!document.querySelector('.modal.show')) {
            refreshLogs();
        }
    }, 30000);
});