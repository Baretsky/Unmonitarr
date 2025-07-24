    // Show toast notification function
    function showToast(type, title, message, duration = 5000) {
      const toasterId = 'config-toaster-' + Date.now();

      // Color mapping for toast types
      const colors = {
        'success': '#198754',
        'danger': '#dc3545',
        'info': '#0dcaf0',
        'warning': '#ffc107'
      };

      const bgColor = colors[type] || colors['info'];

      const toasterHtml = `
        <div id="${toasterId}" style="
            position: fixed; 
            bottom: 20px; 
            right: 20px; 
            z-index: 99999; 
            min-width: 300px; 
            max-width: 400px;
            background-color: ${bgColor}; 
            color: white; 
            padding: 12px 16px; 
            border-radius: 8px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            font-family: system-ui, -apple-system, sans-serif;
            opacity: 0;
            transform: translateX(100%);
            transition: all 0.3s ease-in-out;
        ">
            <div style="display: flex; align-items: flex-start; justify-content: space-between;">
                <div style="flex: 1; margin-right: 12px;">
                    <div style="font-weight: bold; margin-bottom: 4px;">${title}</div>
                    <div style="font-size: 14px; line-height: 1.4;">${message}</div>
                </div>
                <button onclick="document.getElementById('${toasterId}').remove()" 
                        style="background: none; border: none; color: white; font-size: 18px; cursor: pointer; padding: 0; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center;">
                    ×
                </button>
            </div>
        </div>
    `;

      document.body.insertAdjacentHTML('beforeend', toasterHtml);

      // Show toast with animation
      const toast = document.getElementById(toasterId);

      if (toast) {
        // Force a reflow to ensure initial styles are applied
        toast.offsetHeight;

        setTimeout(() => {
          toast.style.opacity = '1';
          toast.style.transform = 'translateX(0)';
        }, 50);

        // Auto-remove after duration
        setTimeout(() => {
          if (toast && toast.parentNode) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
              if (toast && toast.parentNode) {
                toast.remove();
              }
            }, 300);
          }
        }, duration);
      }
    }

    // Test connection function
    async function testConnection(service, event) {
      const button = event ? event.target : document.activeElement;
      const originalHtml = button.innerHTML;

      // Show loading state
      button.disabled = true;
      button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Testing...';

      try {
        // Call health endpoint to test connections
        const health = await apiRequest('/health');

        let serviceStatus = '';
        let serviceDisplayName = '';

        switch (service) {
          case 'jellyfin':
            serviceStatus = health.services?.jellyfin || 'unknown';
            serviceDisplayName = 'Jellyfin';
            break;
          case 'sonarr':
            serviceStatus = health.services?.sonarr || 'unknown';
            serviceDisplayName = 'Sonarr';
            break;
          case 'radarr':
            serviceStatus = health.services?.radarr || 'unknown';
            serviceDisplayName = 'Radarr';
            break;
        }

        if (serviceStatus === 'healthy') {
          showToast('success', `${serviceDisplayName} Connection Test`,
            `✅ Connection successful! ${serviceDisplayName} is responding correctly.`);
        } else {
          showToast('danger', `${serviceDisplayName} Connection Test`,
            `❌ Connection failed! ${serviceDisplayName} is not responding or misconfigured.`);
        }

      } catch (error) {
        showToast('danger', 'Connection Test Error',
          `❌ Failed to test connection: ${error.message}`);
      } finally {
        // Restore button state
        button.disabled = false;
        button.innerHTML = originalHtml;
      }
    }

    // Load configuration data
    async function loadConfiguration() {
      try {
        const info = await apiRequest('/api/info');
        const settings = info.settings || {};

        // Update form fields from actual API endpoints
        document.getElementById('jellyfin-url').value = '••••••••••••••••';
        document.getElementById('jellyfin-key').value = '••••••••••••••••';
        document.getElementById('sonarr-url').value = '••••••••••••••••';
        document.getElementById('sonarr-key').value = '••••••••••••••••';
        document.getElementById('radarr-url').value = '••••••••••••••••';
        document.getElementById('radarr-key').value = '••••••••••••••••';

        document.getElementById('auto-sync').checked = settings.auto_sync_enabled || false;
        document.getElementById('sync-delay').value = settings.sync_delay_seconds || 5;
        document.getElementById('log-level').value = settings.log_level || 'INFO';

        // Set webhook URL and Authorization Header
        const webhookDetails = await apiRequest('/api/config/webhook-details');
        document.getElementById('webhook-url').value = webhookDetails.url;
        document.getElementById('webhook-auth-header').value = webhookDetails.authorization_header;
        document.getElementById('key-field').value = 'Authorization';

        // Set database path
        document.getElementById('db-path').value = '/app/data/unmonitarr.db';

      } catch (error) {
        console.error('Failed to load configuration:', error);
      }
    }

    async function regenerateToken() {
      const btn = document.getElementById('regenerate-token-btn');
      btn.disabled = true;
      btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Regenerating...';

      try {
        await apiRequest('/api/config/webhook-token/regenerate', { method: 'POST' });
        showToast('success', 'Token Regenerated', 'Webhook token has been successfully regenerated. Please update your Jellyfin webhook configuration.');
        loadConfiguration(); // Reload config to get the new URL and header
      } catch (error) {
        showToast('danger', 'Error', `Failed to regenerate token: ${error.message}`);
      } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Regenerate Webhook Token';
      }
    }

    function togglePassword(fieldId) {
      const field = document.getElementById(fieldId);
      const button = field.nextElementSibling;
      const icon = button.querySelector('i');

      if (field.type === 'password') {
        field.type = 'text';
        icon.className = 'fas fa-eye-slash';
      } else {
        field.type = 'password';
        icon.className = 'fas fa-eye';
      }
    }

    function copyToClipboard(fieldId) {
      const field = document.getElementById(fieldId);
      field.select();
      document.execCommand('copy');

      // Show feedback
      const button = field.nextElementSibling;
      const originalIcon = button.innerHTML;
      button.innerHTML = '<i class="fas fa-check text-success"></i>';

      setTimeout(() => {
        button.innerHTML = originalIcon;
      }, 1000);
    }


    function showDatabaseStats() {
      // This would make an API call to get database statistics
      alert('Database statistics feature coming soon!');
    }

    // Initialize configuration page
    document.addEventListener('DOMContentLoaded', function () {
      loadConfiguration();

      document.getElementById('regenerate-token-btn').addEventListener('click', regenerateToken);
    });