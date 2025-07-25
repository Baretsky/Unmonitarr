import httpx
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings

logger = logging.getLogger(__name__)


class SonarrClient:
    """Client for interacting with Sonarr API."""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json"
            }
        )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(settings.retry_attempts),
        wait=wait_exponential(multiplier=settings.retry_delay, min=1, max=10)
    )
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Make HTTP request to Sonarr API with retry logic."""
        url = f"{self.base_url}/api/v3{endpoint}"
        
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data
            )
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            raise
    
    async def check_health(self) -> bool:
        """Check if Sonarr is accessible."""
        try:
            response = await self._make_request("GET", "/health")
            return response is not None
        except Exception as e:
            logger.error(f"Sonarr health check failed: {e}")
            return False
    
    async def get_system_status(self) -> Optional[Dict[str, Any]]:
        """Get Sonarr system status."""
        return await self._make_request("GET", "/system/status")
    
    async def get_all_series(self) -> List[Dict[str, Any]]:
        """Get all series from Sonarr."""
        result = await self._make_request("GET", "/series")
        return result if result else []
    
    async def get_series_by_id(self, series_id: int) -> Optional[Dict[str, Any]]:
        """Get specific series by ID."""
        return await self._make_request("GET", f"/series/{series_id}")
    
    async def search_series_by_title(self, title: str) -> List[Dict[str, Any]]:
        """Search for series by title with multiple matching strategies."""
        series_list = await self.get_all_series()
        if not series_list:
            logger.warning("No series found in Sonarr")
            return []
        
        logger.info(f"Searching through {len(series_list)} series in Sonarr")
        matches = []
        title_clean = self._clean_title(title)
        
        # Strategy 1: Exact match
        for series in series_list:
            series_title_clean = self._clean_title(series.get("title", ""))
            if title_clean == series_title_clean:
                logger.info(f"EXACT MATCH: '{title}' -> '{series.get('title')}'")
                matches.append(series)
        
        if matches:
            return matches
        
        # Strategy 2: Contains match (bidirectional)
        for series in series_list:
            series_title = series.get("title", "")
            series_title_clean = self._clean_title(series_title)
            
            if (title_clean in series_title_clean or series_title_clean in title_clean) and len(title_clean) > 3:
                logger.info(f"CONTAINS MATCH: '{title}' -> '{series_title}'")
                matches.append(series)
        
        if matches:
            return matches
        
        # Strategy 3: Check alternative titles
        for series in series_list:
            alt_titles = series.get("alternateTitles", [])
            for alt_title in alt_titles:
                alt_title_clean = self._clean_title(alt_title.get("title", ""))
                if title_clean == alt_title_clean or (title_clean in alt_title_clean and len(title_clean) > 3):
                    logger.info(f"ALT TITLE MATCH: '{title}' -> '{series.get('title')}' (via '{alt_title.get('title')}')")
                    matches.append(series)
                    break
        
        if not matches:
            logger.warning(f"NO MATCHES found for '{title}' in {len(series_list)} series")
            # Log first few series for debugging
            for i, series in enumerate(series_list[:5]):
                logger.debug(f"Series {i+1}: '{series.get('title')}' (year: {series.get('year')})")
        
        return matches
    
    def _clean_title(self, title: str) -> str:
        """Clean title for better matching."""
        import re
        if not title:
            return ""
        
        # Convert to lowercase
        cleaned = title.lower()
        
        # Remove common punctuation and special characters
        cleaned = re.sub(r'[^\w\s]', '', cleaned)
        
        # Remove extra whitespace
        cleaned = ' '.join(cleaned.split())
        
        # Remove common words that might cause issues
        common_words = ['the', 'a', 'an']
        words = cleaned.split()
        cleaned_words = [w for w in words if w not in common_words]
        
        return ' '.join(cleaned_words) if cleaned_words else cleaned
    
    async def get_episodes_for_series(self, series_id: int, include_specials: bool = True) -> List[Dict[str, Any]]:
        """Get all episodes for a specific series.
        
        Args:
            series_id: The Sonarr series ID
            include_specials: If False, excludes season 0 (special episodes)
        """
        result = await self._make_request("GET", f"/episode", params={"seriesId": series_id})
        episodes = result if result else []
        
        if not include_specials:
            # Filter out special episodes (season 0)
            episodes = [ep for ep in episodes if ep.get("seasonNumber", 0) != 0]
            logger.debug(f"Filtered out special episodes for series {series_id}, {len(episodes)} episodes remaining")
        
        return episodes
    
    async def get_episode_by_id(self, episode_id: int) -> Optional[Dict[str, Any]]:
        """Get specific episode by ID."""
        return await self._make_request("GET", f"/episode/{episode_id}")
    
    async def search_episode(self, series_id: int, season_number: int, episode_number: int) -> Optional[Dict[str, Any]]:
        """Search for a specific episode by series, season, and episode number."""
        # Always include specials for individual episode searches, let the caller decide what to do
        episodes = await self.get_episodes_for_series(series_id, include_specials=True)
        
        for episode in episodes:
            if (episode.get("seasonNumber") == season_number and 
                episode.get("episodeNumber") == episode_number):
                return episode
        
        return None
    
    async def update_series_monitoring(self, series_id: int, monitored: bool) -> bool:
        """Update monitoring status for an entire series."""
        try:
            series = await self.get_series_by_id(series_id)
            if not series:
                logger.error(f"Series {series_id} not found")
                return False
            
            # Update monitoring status
            series["monitored"] = monitored
            
            result = await self._make_request("PUT", f"/series/{series_id}", json_data=series)
            
            if result:
                logger.info(f"Series {series_id} monitoring updated to {monitored}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update series {series_id} monitoring: {e}")
            return False
    
    async def update_episode_monitoring(self, episode_id: int, monitored: bool) -> bool:
        """Update monitoring status for a specific episode."""
        try:
            episode = await self.get_episode_by_id(episode_id)
            if not episode:
                logger.error(f"Episode {episode_id} not found")
                return False
            
            # Check if this is a special episode and if specials should be ignored
            from .config import settings
            if episode.get("seasonNumber") == 0 and settings.ignore_special_episodes:
                logger.info(f"Ignoring special episode {episode_id} (season 0) due to configuration")
                return True  # Return success to avoid error handling, but don't actually update
            
            # Update monitoring status
            episode["monitored"] = monitored
            
            result = await self._make_request("PUT", f"/episode/{episode_id}", json_data=episode)
            
            if result:
                logger.info(f"Episode {episode_id} monitoring updated to {monitored}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update episode {episode_id} monitoring: {e}")
            return False
    
    async def update_season_monitoring(self, series_id: int, season_number: int, monitored: bool) -> bool:
        """Update monitoring status for all episodes in a season using bulk endpoint."""
        try:
            # Check if this is a special season and if specials should be ignored
            from .config import settings
            if season_number == 0 and settings.ignore_special_episodes:
                logger.info(f"Ignoring special episodes (season 0) for series {series_id} due to configuration")
                return True  # Return success to avoid error handling, but don't actually update
            
            episodes = await self.get_episodes_for_series(series_id, include_specials=True)
            season_episodes = [ep for ep in episodes if ep.get("seasonNumber") == season_number]
            
            if not season_episodes:
                logger.warning(f"No episodes found for series {series_id} season {season_number}")
                return False
            
            # Use bulk monitoring endpoint for better performance
            episode_ids = [ep["id"] for ep in season_episodes]
            success = await self.bulk_update_episode_monitoring(episode_ids, monitored)
            
            if success:
                logger.info(f"Successfully updated monitoring for {len(season_episodes)} episodes in series {series_id} season {season_number}")
                return True
            else:
                # Fallback to individual updates if bulk fails
                logger.warning("Bulk update failed, falling back to individual episode updates")
                return await self._fallback_season_monitoring(season_episodes, monitored)
            
        except Exception as e:
            logger.error(f"Failed to update season {season_number} monitoring for series {series_id}: {e}")
            return False
    
    async def bulk_update_episode_monitoring(self, episode_ids: List[int], monitored: bool) -> bool:
        """Update monitoring status for multiple episodes using bulk endpoint."""
        try:
            bulk_data = {
                "episodeIds": episode_ids,
                "monitored": monitored
            }
            
            result = await self._make_request("PUT", "/episode/monitor", json_data=bulk_data)
            
            if result is not None:  # API returns the updated episodes or empty response
                logger.info(f"Bulk updated monitoring for {len(episode_ids)} episodes to {monitored}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to bulk update episode monitoring: {e}")
            return False
    
    async def _fallback_season_monitoring(self, season_episodes: List[Dict], monitored: bool) -> bool:
        """Fallback method for individual episode monitoring updates."""
        success_count = 0
        for episode in season_episodes:
            if await self.update_episode_monitoring(episode["id"], monitored):
                success_count += 1
        
        logger.info(f"Updated {success_count}/{len(season_episodes)} episodes using fallback method")
        return success_count > 0
    
    async def monitor_episode(self, episode_id: int) -> bool:
        """Monitor a specific episode."""
        return await self.update_episode_monitoring(episode_id, True)
    
    async def unmonitor_episode(self, episode_id: int) -> bool:
        """Unmonitor a specific episode."""
        return await self.update_episode_monitoring(episode_id, False)
    
    async def monitor_series(self, series_id: int) -> bool:
        """Monitor an entire series."""
        return await self.update_series_monitoring(series_id, True)
    
    async def unmonitor_series(self, series_id: int) -> bool:
        """Unmonitor an entire series."""
        return await self.update_series_monitoring(series_id, False)
    
    async def monitor_season(self, series_id: int, season_number: int) -> bool:
        """Monitor all episodes in a season."""
        return await self.update_season_monitoring(series_id, season_number, True)
    
    async def unmonitor_season(self, series_id: int, season_number: int) -> bool:
        """Unmonitor all episodes in a season."""
        return await self.update_season_monitoring(series_id, season_number, False)
    
    async def search_series_lookup(self, term: str) -> List[Dict[str, Any]]:
        """Search for series using Sonarr's lookup endpoint (searches external databases)."""
        try:
            params = {"term": term}
            result = await self._make_request("GET", "/series/lookup", params=params)
            return result if result else []
        except Exception as e:
            logger.error(f"Failed to lookup series '{term}': {e}")
            return []
    
    async def find_series_by_jellyfin_metadata(
        self, 
        title: str, 
        year: Optional[int] = None,
        tvdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Find series in Sonarr using Jellyfin metadata with improved matching."""
        logger.info(f"🔍 MATCHING - Searching for series: '{title}' (year: {year}, tvdb: {tvdb_id}, imdb: {imdb_id})")
        
        # PRIORITY 1: External ID matching (most reliable)
        if tvdb_id or imdb_id:
            logger.info(f"🎯 PRIORITY 1: Searching by external IDs in existing series")
            series_list = await self.get_all_series()
            logger.info(f"📊 Found {len(series_list)} series in Sonarr to check")
            
            # Try TVDB first (most common for TV series)
            if tvdb_id:
                for series in series_list:
                    series_tvdb = str(series.get("tvdbId", "")) if series.get("tvdbId") else None
                    if series_tvdb and str(tvdb_id) == series_tvdb:
                        logger.info(f"✅ EXACT MATCH by TVDB ID {tvdb_id}: '{series.get('title')}' ({series.get('year')})")
                        return series
            
            # Try IMDB if no TVDB match (some series only have IMDB)
            if imdb_id:
                for series in series_list:
                    series_imdb = series.get("imdbId", "") if series.get("imdbId") else None
                    if series_imdb and str(imdb_id) == series_imdb:
                        logger.info(f"✅ EXACT MATCH by IMDB ID {imdb_id}: '{series.get('title')}' ({series.get('year')})")
                        return series
            
            # Only warn if we had IDs but found no matches
            available_ids = []
            if tvdb_id:
                available_ids.append(f"TVDB:{tvdb_id}")
            if imdb_id:
                available_ids.append(f"IMDB:{imdb_id}")
            logger.warning(f"⚠️ No external ID matches found for {', '.join(available_ids)}")
            
            # Log sample series for debugging
            for i, series in enumerate(series_list[:3]):
                logger.debug(f"🔬 Sample series {i+1}: '{series.get('title')}' TVDB:{series.get('tvdbId')} IMDB:{series.get('imdbId')}")
        else:
            logger.info("⚠️ No external IDs provided - falling back to title matching")
        
        # PRIORITY 2: Title-based matching in existing series
        logger.info("🎯 PRIORITY 2: Searching by title in existing Sonarr series")
        matches = await self.search_series_by_title(title)
        
        if matches:
            logger.info(f"📊 Found {len(matches)} title matches in existing series")
            # Apply year filtering if available
            if year and len(matches) > 1:
                year_matches = [s for s in matches if s.get("year") and abs(s.get("year") - year) <= 1]
                if year_matches:
                    logger.info(f"🗓️ Filtered to {len(year_matches)} matches by year ({year})")
                    matches = year_matches
            
            best_match = matches[0]
            logger.info(f"✅ TITLE MATCH: '{best_match.get('title')}' ({best_match.get('year')}) - TVDB:{best_match.get('tvdbId')}")
            return best_match
        
        # If not found in existing series, try lookup from external databases
        logger.info("Series not found in Sonarr, searching external databases")
        lookup_results = await self.search_series_lookup(title)
        
        if lookup_results:
            logger.info(f"Found {len(lookup_results)} results from external lookup")
            # Filter by year if provided
            if year:
                year_matches = [s for s in lookup_results if s.get("year") and abs(s.get("year") - year) <= 1]
                if year_matches:
                    lookup_results = year_matches
            
            # Check if any lookup results match existing series by TVDB ID
            for lookup_series in lookup_results:
                lookup_tvdb = lookup_series.get("tvdbId")
                if lookup_tvdb:
                    series_list = await self.get_all_series()
                    for existing_series in series_list:
                        if str(existing_series.get("tvdbId")) == str(lookup_tvdb):
                            logger.info(f"Lookup result matches existing series: {existing_series.get('title')}")
                            return existing_series
            
            # If no existing match found, return the best lookup result for potential adding
            best_lookup = lookup_results[0]
            logger.info(f"Best external lookup result: {best_lookup.get('title')} (not in Sonarr)")
            return None  # Return None since series isn't in Sonarr yet
        
        logger.warning(f"No series found for '{title}'")
        return None
    
    async def get_series_statistics(self, series_id: int) -> Dict[str, Any]:
        """Get statistics for a series."""
        series = await self.get_series_by_id(series_id)
        if not series:
            return {}
        
        from .config import settings
        include_specials = not settings.ignore_special_episodes
        episodes = await self.get_episodes_for_series(series_id, include_specials=include_specials)
        
        total_episodes = len(episodes)
        monitored_episodes = len([ep for ep in episodes if ep.get("monitored", False)])
        downloaded_episodes = len([ep for ep in episodes if ep.get("hasFile", False)])
        
        return {
            "total_episodes": total_episodes,
            "monitored_episodes": monitored_episodes,
            "downloaded_episodes": downloaded_episodes,
            "monitoring_percentage": (monitored_episodes / total_episodes * 100) if total_episodes > 0 else 0
        }