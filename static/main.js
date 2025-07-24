        // Auto-refresh functionality (deprecated - now handled by individual pages)
        function autoRefresh() {
            // This function is deprecated. Individual pages now handle their own refresh logic
            // to avoid interfering with bulk sync operations and provide better user experience.
        }
        
        // API helper functions
        async function apiRequest(url, options = {}) {
            try {
                const response = await fetch(url, {
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
                    ...options
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                return await response.json();
            } catch (error) {
                console.error('API request failed:', error);
                throw error;
            }
        }
        
        // Format timestamp according to user's locale
        function formatTimestamp(isoString) {
            if (!isoString) return 'N/A';
            
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffHours = diffMs / (1000 * 60 * 60);
            const diffDays = diffMs / (1000 * 60 * 60 * 24);
            
            // If less than 1 hour ago, show relative time
            if (diffHours < 1) {
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                if (diffMinutes < 1) return 'Just now';
                return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
            }
            
            // If less than 24 hours ago, show hours
            if (diffHours < 24) {
                const hours = Math.floor(diffHours);
                return `${hours} hour${hours > 1 ? 's' : ''} ago`;
            }
            
            // If less than 7 days ago, show days
            if (diffDays < 7) {
                const days = Math.floor(diffDays);
                return `${days} day${days > 1 ? 's' : ''} ago`;
            }
            
            // Otherwise show formatted date based on user's locale
            return date.toLocaleDateString(navigator.language, { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        // Format media title based on type
        function formatMediaTitle(mediaItem) {
            if (!mediaItem) return 'Unknown Media';
            
            const mediaType = mediaItem.media_type || mediaItem.item_type;
            const title = mediaItem.title || mediaItem.media_title || mediaItem.item_name;
            
            // For movies, just show the title
            if (mediaType === 'movie' || mediaType === 'Movie') {
                return title;
            }
            
            // For episodes, show: Series Name S01E01 - Episode Title
            if (mediaType === 'episode' || mediaType === 'Episode') {
                // Use the direct series_name field from the database
                const seriesName = mediaItem.series_name || 'Unknown Series';
                const seasonNum = mediaItem.season_number || mediaItem.SeasonNumber || mediaItem.ParentIndexNumber;
                const episodeNum = mediaItem.episode_number || mediaItem.EpisodeNumber || mediaItem.IndexNumber;
                const episodeTitle = title;
                
                if (seasonNum !== null && seasonNum !== undefined && episodeNum !== null && episodeNum !== undefined) {
                    const season = String(seasonNum).padStart(2, '0');
                    const episode = String(episodeNum).padStart(2, '0');
                    return `${seriesName} S${season}E${episode} - ${episodeTitle}`;
                } else if (seasonNum !== null && seasonNum !== undefined) {
                    return `${seriesName} Season ${seasonNum} - ${episodeTitle}`;
                } else {
                    return `${seriesName} - ${episodeTitle}`;
                }
            }
            
            // For series or seasons, show the title as is
            return title;
        }
        
        
        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            autoRefresh();
        });