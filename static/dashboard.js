// Load dashboard data
async function loadDashboard() {
    try {
        // Load health status
        const health = await apiRequest('/health');
        displayHealthStatus(health);
        
        // Load API info
        const info = await apiRequest('/api/info');
        displayApiInfo(info);
        
        // Load real statistics
        const stats = await apiRequest('/api/stats');
        displayStats(stats);
        
        // Load recent logs
        const logs = await apiRequest('/api/logs/recent?limit=5');
        displayRecentLogs(logs);
        
    } catch (error) {
        console.error('Failed to load dashboard data:', error);
    }
}

function displayHealthStatus(health) {
    const statusContainer = document.getElementById('health-status');
    const services = health.services || {};
    
    let html = '';
    for (const [service, status] of Object.entries(services)) {
        const statusClass = status === 'healthy' ? 'status-healthy' : 'status-unhealthy';
        const icon = status === 'healthy' ? 'fas fa-check-circle' : 'fas fa-times-circle';
        
        html += `
            <div class="col-md-3 col-sm-6 mb-2">
                <div class="d-flex align-items-center">
                    <i class="${icon} me-2 ${statusClass}"></i>
                    <div>
                        <strong>${service.charAt(0).toUpperCase() + service.slice(1)}</strong>
                        <br>
                        <small class="${statusClass}">${status}</small>
                    </div>
                </div>
            </div>
        `;
    }
    
    statusContainer.innerHTML = html;
}

function displayApiInfo(info) {
    // Just log for now - real stats come from displayStats
    console.log('API Info:', info);
}

function displayStats(stats) {
    // Create a hash of current stats to detect changes
    const currentHash = JSON.stringify(stats);
    
    // Only update DOM if stats have changed
    if (currentHash !== lastStatsHash) {
        document.getElementById('total-media').textContent = stats.total_media || '0';
        document.getElementById('watched-items').textContent = stats.watched_items || '0';
        document.getElementById('sync-actions').textContent = stats.sync_actions || '0';
        document.getElementById('success-rate').textContent = (stats.success_rate || 0) + '%';
        
        lastStatsHash = currentHash;
        console.log('Stats updated due to changes');
    } else {
        console.log('Stats unchanged, skipping DOM update');
    }
}

function displayRecentLogs(logs) {
    const logsContainer = document.getElementById('recent-logs');
    
    if (logs.length === 0) {
        logsContainer.innerHTML = `
            <div class="text-center text-muted">
                <i class="fas fa-inbox fa-2x mb-2"></i>
                <p>No recent sync activity</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    logs.slice(0, 5).forEach(log => {
        const statusClass = log.status === 'completed' ? 'log-success' : 
                           log.status === 'failed' ? 'log-error' : 'log-warning';
        
        // Get action with icon
        const actionIcon = log.action === 'monitor' ? 'fas fa-plus' : 'fas fa-minus';
        const actionText = log.action === 'monitor' ? 'Monitor' : 'Unmonitor';
        
        // Format media title with episode/season info
        const formattedTitle = formatMediaTitle(log);
        
        // Format timestamp
        const formattedTime = formatTimestamp(log.created_at);
        
        html += `
            <div class="log-entry ${statusClass} mb-3">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <strong><i class="${actionIcon} me-1"></i>${actionText}</strong> - ${formattedTitle}
                        <br>
                        <small class="text-muted">${log.service} • ${formattedTime}</small>
                    </div>
                    <span class="badge bg-${log.status === 'completed' ? 'success' : 
                                                  log.status === 'failed' ? 'danger' : 'warning'}">
                        ${log.status}
                    </span>
                </div>
            </div>
        `;
    });
    
    logsContainer.innerHTML = html;
}


// Bulk sync polling variables
let bulkSyncPollingInterval = null;
let dashboardRefreshInterval = null;
let isDashboardRefreshPaused = false;
let lastUserActivity = Date.now();
let lastStatsHash = null;

// Show toaster notification function
function showToaster(type, title, message, duration = 5000) {
    const toasterId = 'toaster-' + Date.now();
    const toasterHtml = `
        <div id="${toasterId}" class="toast align-items-center text-white bg-${type} border-0" 
             role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999;">
            <div class="d-flex">
                <div class="toast-body">
                    <strong>${title}</strong><br>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" 
                        onclick="document.getElementById('${toasterId}').remove()"></button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', toasterHtml);
    
    // Auto-remove after duration
    setTimeout(() => {
        const toast = document.getElementById(toasterId);
        if (toast) toast.remove();
    }, duration);
}

async function startBulkSyncPolling() {
    // Pause dashboard refresh during bulk sync
    pauseDashboardRefresh();
    
    // Poll every 2 seconds during sync
    bulkSyncPollingInterval = setInterval(async () => {
        try {
            const status = await apiRequest('/api/sync/bulk/status');
            updateBulkSyncUI(status);
            
            if (status.completed) {
                stopBulkSyncPolling();
                handleBulkSyncCompletion(status);
            }
        } catch (error) {
            console.error('Polling error:', error);
        }
    }, 2000);
}

function stopBulkSyncPolling() {
    if (bulkSyncPollingInterval) {
        clearInterval(bulkSyncPollingInterval);
        bulkSyncPollingInterval = null;
    }
    
    // Resume dashboard refresh after bulk sync
    resumeDashboardRefresh();
}

function updateBulkSyncUI(status) {
    const buttonAll = document.getElementById('bulk-sync-all-btn');
    const buttonSeries = document.getElementById('bulk-sync-series-btn');
    const buttonMovies = document.getElementById('bulk-sync-movies-btn');
    const progressDiv = document.getElementById('bulk-sync-progress');
    
    if (status.is_running) {
        const percentage = Math.round(status.progress.percentage);
        
        // Disable all buttons during sync
        if (buttonAll) buttonAll.disabled = true;
        if (buttonSeries) buttonSeries.disabled = true;
        if (buttonMovies) buttonMovies.disabled = true;

        // Update the text of the button that initiated the sync
        let activeBtn;
        if (status.sync_type === 'series' && buttonSeries) activeBtn = buttonSeries;
        else if (status.sync_type === 'movies' && buttonMovies) activeBtn = buttonMovies;
        else if (buttonAll) activeBtn = buttonAll; // Default to all if type is not specified or is 'all'

        if (activeBtn) {
            activeBtn.innerHTML = `
                <i class="fas fa-spinner fa-spin me-2"></i>
                ${percentage}% (${status.progress.processed}/${status.progress.total})
            `;
        }

        // Update progress bar
        progressDiv.innerHTML = `
            <div class="alert alert-info mb-0">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span><i class="fas fa-sync fa-spin me-2"></i><strong>Bulk sync in progress...</strong></span>
                    <span>${percentage}%</span>
                </div>
                <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         style="width: ${percentage}%" 
                         role="progressbar"></div>
                </div>
                <small class="mt-2 d-block">
                    ${status.current_item ? `Processing: ${status.current_item}` : 'Initializing...'}
                </small>
            </div>
        `;
    }
}

function handleBulkSyncCompletion(status) {
    const button = document.getElementById('bulk-sync-btn');
    const progressDiv = document.getElementById('bulk-sync-progress');
    
    // Restore the button
    button.disabled = false;
    button.innerHTML = '<i class="fas fa-download me-2"></i>Start Bulk Sync';
    progressDiv.classList.add('d-none');
    
    // Show notification
    if (status.success) {
        showToaster('success', 'Bulk Sync Completed!', 
                   `${status.progress.synced} items synchronized successfully out of ${status.progress.total}`);
    } else {
        const errorCount = status.errors.length;
        showToaster('danger', 'Bulk Sync Failed', 
                   `${errorCount} error(s) detected. Check logs for more details.`);
    }
    
    // Reload dashboard data after bulk sync completion
    loadDashboard();
}

// Dashboard refresh management functions
function pauseDashboardRefresh() {
    isDashboardRefreshPaused = true;
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
        dashboardRefreshInterval = null;
    }
    console.log('Dashboard refresh paused during bulk sync');
}

function resumeDashboardRefresh() {
    isDashboardRefreshPaused = false;
    startDashboardRefresh();
    console.log('Dashboard refresh resumed after bulk sync');
}

function startDashboardRefresh() {
    // Clear any existing interval
    if (dashboardRefreshInterval) {
        clearInterval(dashboardRefreshInterval);
    }
    
    // Only start if not paused
    if (!isDashboardRefreshPaused) {
        // Refresh every 30 seconds, but only when not doing bulk sync
        dashboardRefreshInterval = setInterval(() => {
            if (!isDashboardRefreshPaused) {
                // Only refresh if user has been active recently (within 5 minutes)
                const timeSinceActivity = Date.now() - lastUserActivity;
                if (timeSinceActivity < 5 * 60 * 1000) {
                    console.log('Auto-refreshing dashboard data');
                    loadDashboard();
                } else {
                    console.log('User inactive, skipping dashboard refresh');
                }
            }
        }, 30000);
    }
}

// Track user activity
function trackUserActivity() {
    lastUserActivity = Date.now();
}

// Add activity listeners
document.addEventListener('click', trackUserActivity);
document.addEventListener('keypress', trackUserActivity);
document.addEventListener('scroll', trackUserActivity);
document.addEventListener('mousemove', trackUserActivity);

// Manual refresh function
async function manualRefresh() {
    const refreshBtn = document.getElementById('refresh-btn');
    const originalContent = refreshBtn.innerHTML;
    
    try {
        // Show loading state
        refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
        refreshBtn.disabled = true;
        
        // Force refresh
        console.log('Manual refresh triggered');
        await loadDashboard();
        
        // Show success feedback
        refreshBtn.innerHTML = '<i class="fas fa-check me-1"></i>Updated';
        setTimeout(() => {
            refreshBtn.innerHTML = originalContent;
            refreshBtn.disabled = false;
        }, 1000);
        
    } catch (error) {
        console.error('Manual refresh failed:', error);
        refreshBtn.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>Error';
        setTimeout(() => {
            refreshBtn.innerHTML = originalContent;
            refreshBtn.disabled = false;
        }, 2000);
    }
}

async function checkOngoingBulkSync() {
    try {
        const status = await apiRequest('/api/sync/bulk/status');
        if (status.is_running) {
            // Resume polling if a sync was in progress
            startBulkSyncPolling();
            updateBulkSyncUI(status);
        }
    } catch (error) {
        console.error('Failed to check bulk sync status:', error);
    }
}

async function bulkSync(syncType = 'all') {
    let buttonId;
    let endpoint;
    let buttonText;

    switch (syncType) {
        case 'series':
            buttonId = 'bulk-sync-series-btn';
            endpoint = '/api/sync/bulk/series';
            buttonText = '<i class="fas fa-tv me-2"></i>Sync Series';
            break;
        case 'movies':
            buttonId = 'bulk-sync-movies-btn';
            endpoint = '/api/sync/bulk/movies';
            buttonText = '<i class="fas fa-film me-2"></i>Sync Movies';
            break;
        case 'all':
        default:
            buttonId = 'bulk-sync-all-btn';
            endpoint = '/api/sync/bulk';
            buttonText = '<i class="fas fa-download me-2"></i>Start Full Sync';
            break;
    }

    const button = document.getElementById(buttonId);
    const progressDiv = document.getElementById('bulk-sync-progress');
    
    try {
        // Check if a sync is already in progress
        const currentStatus = await apiRequest('/api/sync/bulk/status');
        if (currentStatus.is_running) {
            showToaster('warning', 'Sync in Progress', 'A bulk sync is already running');
            return;
        }
        
        // Start the sync
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Starting...';
        progressDiv.classList.remove('d-none');
        
        const result = await apiRequest(endpoint, { method: 'POST' });
        
        if (result.status === 'processing') {
            // Start polling
            showToaster('info', 'Bulk Sync Started', 'Synchronization has started in the background');
            startBulkSyncPolling();
        } else {
            throw new Error(result.error || 'Unknown error');
        }
        
    } catch (error) {
        console.error('Bulk sync error:', error);
        showToaster('danger', 'Startup Error', `Unable to start bulk sync: ${error.message}`);
        
        // Restore button on error
        button.disabled = false;
        button.innerHTML = buttonText;
        progressDiv.classList.add('d-none');
    }
}

function updateBulkSyncUI(status) {
    const buttonAll = document.getElementById('bulk-sync-all-btn');
    const buttonSeries = document.getElementById('bulk-sync-series-btn');
    const buttonMovies = document.getElementById('bulk-sync-movies-btn');
    const progressDiv = document.getElementById('bulk-sync-progress');
    
    if (status.is_running) {
        const percentage = Math.round(status.progress.percentage);
        
        // Disable all buttons during sync
        if (buttonAll) buttonAll.disabled = true;
        if (buttonSeries) buttonSeries.disabled = true;
        if (buttonMovies) buttonMovies.disabled = true;

        // Update the text of the button that initiated the sync
        let activeBtn;
        if (status.sync_type === 'series' && buttonSeries) activeBtn = buttonSeries;
        else if (status.sync_type === 'movies' && buttonMovies) activeBtn = buttonMovies;
        else if (buttonAll) activeBtn = buttonAll; // Default to all if type is not specified or is 'all'

        if (activeBtn) {
            activeBtn.innerHTML = `
                <i class="fas fa-spinner fa-spin me-2"></i>
                ${percentage}% (${status.progress.processed}/${status.progress.total})
            `;
        }

        // Update progress bar
        progressDiv.innerHTML = `
            <div class="alert alert-info mb-0">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span><i class="fas fa-sync fa-spin me-2"></i><strong>Bulk sync in progress...</strong></span>
                    <span>${percentage}%</span>
                </div>
                <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         style="width: ${percentage}%" 
                         role="progressbar"></div>
                </div>
                <small class="mt-2 d-block">
                    ${status.current_item ? `Processing: ${status.current_item}` : 'Initializing...'}
                </small>
            </div>
        `;
    }
}

function handleBulkSyncCompletion(status) {
    const buttonAll = document.getElementById('bulk-sync-all-btn');
    const buttonSeries = document.getElementById('bulk-sync-series-btn');
    const buttonMovies = document.getElementById('bulk-sync-movies-btn');
    const progressDiv = document.getElementById('bulk-sync-progress');
    
    // Restore all buttons
    if (buttonAll) {
        buttonAll.disabled = false;
        buttonAll.innerHTML = '<i class="fas fa-download me-2"></i>Start Full Sync';
    }
    if (buttonSeries) {
        buttonSeries.disabled = false;
        buttonSeries.innerHTML = '<i class="fas fa-tv me-2"></i>Sync Series';
    }
    if (buttonMovies) {
        buttonMovies.disabled = false;
        buttonMovies.innerHTML = '<i class="fas fa-film me-2"></i>Sync Movies';
    }
    progressDiv.classList.add('d-none');
    
    // Show notification
    if (status.success) {
        showToaster('success', 'Bulk Sync Completed!', 
                   `${status.progress.synced} items synchronized successfully out of ${status.progress.total}`);
    } else {
        const errorCount = status.errors.length;
        showToaster('danger', 'Bulk Sync Failed', 
                   `${errorCount} error(s) detected. Check logs for more details.`);
    }
    
    // Reload dashboard data after bulk sync completion
    loadDashboard();
}

// Warn user if they try to close page during sync
window.addEventListener('beforeunload', function(e) {
    if (bulkSyncPollingInterval) {
        e.preventDefault();
        e.returnValue = 'A bulk sync is in progress. Are you sure you want to leave?';
        return e.returnValue;
    }
});

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    loadDashboard();
    
    // Check if there's an ongoing sync on page load
    checkOngoingBulkSync();
    
    // Start intelligent dashboard refresh
    startDashboardRefresh();
});