import httpx
import logging
from typing import Optional, Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings

logger = logging.getLogger(__name__)


class RadarrClient:
    """Client for interacting with Radarr API."""
    
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
        """Make HTTP request to Radarr API with retry logic."""
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
        """Check if Radarr is accessible."""
        try:
            response = await self._make_request("GET", "/health")
            return response is not None
        except Exception as e:
            logger.error(f"Radarr health check failed: {e}")
            return False
    
    async def get_system_status(self) -> Optional[Dict[str, Any]]:
        """Get Radarr system status."""
        return await self._make_request("GET", "/system/status")
    
    async def get_all_movies(self) -> List[Dict[str, Any]]:
        """Get all movies from Radarr."""
        result = await self._make_request("GET", "/movie")
        return result if result else []
    
    async def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get specific movie by ID."""
        return await self._make_request("GET", f"/movie/{movie_id}")
    
    async def search_movies_by_title(self, title: str) -> List[Dict[str, Any]]:
        """Search for movies by title."""
        movies_list = await self.get_all_movies()
        if not movies_list:
            return []
        
        # Simple title matching - could be improved with fuzzy matching
        matches = []
        title_lower = title.lower()
        
        for movie in movies_list:
            movie_title = movie.get("title", "").lower()
            # Also check original title and alternative titles
            original_title = movie.get("originalTitle", "").lower()
            alternative_titles = [alt.get("title", "").lower() for alt in movie.get("alternativeTitles", [])]
            
            all_titles = [movie_title, original_title] + alternative_titles
            
            if any(title_lower in t or t in title_lower for t in all_titles if t):
                matches.append(movie)
        
        return matches
    
    async def update_movie_monitoring(self, movie_id: int, monitored: bool) -> bool:
        """Update monitoring status for a movie."""
        try:
            movie = await self.get_movie_by_id(movie_id)
            if not movie:
                logger.error(f"Movie {movie_id} not found")
                return False
            
            # Update monitoring status
            movie["monitored"] = monitored
            
            result = await self._make_request("PUT", f"/movie/{movie_id}", json_data=movie)
            
            if result:
                logger.info(f"Movie {movie_id} ({movie.get('title')}) monitoring updated to {monitored}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update movie {movie_id} monitoring: {e}")
            return False
    
    async def monitor_movie(self, movie_id: int) -> bool:
        """Monitor a specific movie."""
        return await self.update_movie_monitoring(movie_id, True)
    
    async def unmonitor_movie(self, movie_id: int) -> bool:
        """Unmonitor a specific movie."""
        return await self.update_movie_monitoring(movie_id, False)
    
    async def find_movie_by_jellyfin_metadata(
        self, 
        title: str, 
        year: Optional[int] = None,
        tmdb_id: Optional[str] = None,
        imdb_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Find movie in Radarr using Jellyfin metadata with improved matching."""
        logger.info(f"🔍 MATCHING - Searching for movie: '{title}' (year: {year}, tmdb: {tmdb_id}, imdb: {imdb_id})")
        
        # PRIORITY 1: External ID matching (most reliable)
        if tmdb_id or imdb_id:
            logger.info(f"🎯 PRIORITY 1: Searching by external IDs in existing movies")
            movies_list = await self.get_all_movies()
            logger.info(f"📊 Found {len(movies_list)} movies in Radarr to check")
            
            for movie in movies_list:
                movie_tmdb = str(movie.get("tmdbId", "")) if movie.get("tmdbId") else None
                movie_imdb = movie.get("imdbId", "") if movie.get("imdbId") else None
                
                if tmdb_id and movie_tmdb and str(tmdb_id) == movie_tmdb:
                    logger.info(f"✅ EXACT MATCH by TMDB ID {tmdb_id}: '{movie.get('title')}' ({movie.get('year')})")
                    return movie
                if imdb_id and movie_imdb and str(imdb_id) == movie_imdb:
                    logger.info(f"✅ EXACT MATCH by IMDB ID {imdb_id}: '{movie.get('title')}' ({movie.get('year')})")
                    return movie
            
            logger.warning(f"❌ No external ID matches found for TMDB:{tmdb_id} IMDB:{imdb_id}")
            # Log first few movies for debugging external IDs
            for i, movie in enumerate(movies_list[:3]):
                logger.info(f"🔬 Sample movie {i+1}: '{movie.get('title')}' TMDB:{movie.get('tmdbId')} IMDB:{movie.get('imdbId')}")
        else:
            logger.info("⚠️ No external IDs provided - falling back to title matching")
        
        # PRIORITY 2: Title-based matching in existing movies
        logger.info("🎯 PRIORITY 2: Searching by title in existing Radarr movies")
        matches = await self.search_movies_by_title(title)
        
        if matches:
            logger.info(f"📊 Found {len(matches)} title matches in existing movies")
            # Apply year filtering if available
            if year and len(matches) > 1:
                year_matches = [m for m in matches if m.get("year") and abs(m.get("year") - year) <= 1]
                if year_matches:
                    logger.info(f"🗓️ Filtered to {len(year_matches)} matches by year ({year})")
                    matches = year_matches
            
            best_match = matches[0]
            logger.info(f"✅ TITLE MATCH: '{best_match.get('title')}' ({best_match.get('year')}) - TMDB:{best_match.get('tmdbId')}")
            return best_match
        
        # If not found in existing movies, try lookup from external databases
        logger.info("Movie not found in Radarr, searching external databases")
        lookup_results = await self.search_movie_lookup(title)
        
        if lookup_results:
            logger.info(f"Found {len(lookup_results)} results from external lookup")
            # Filter by year if provided
            if year:
                year_matches = [m for m in lookup_results if m.get("year") and abs(m.get("year") - year) <= 1]
                if year_matches:
                    lookup_results = year_matches
            
            # Check if any lookup results match existing movies by TMDB ID
            for lookup_movie in lookup_results:
                lookup_tmdb = lookup_movie.get("tmdbId")
                if lookup_tmdb:
                    movies_list = await self.get_all_movies()
                    for existing_movie in movies_list:
                        if str(existing_movie.get("tmdbId")) == str(lookup_tmdb):
                            logger.info(f"Lookup result matches existing movie: {existing_movie.get('title')}")
                            return existing_movie
            
            # If no existing match found, return None since movie isn't in Radarr yet
            best_lookup = lookup_results[0]
            logger.info(f"Best external lookup result: {best_lookup.get('title')} (not in Radarr)")
            return None  # Return None since movie isn't in Radarr yet
        
        logger.warning(f"No movie found for '{title}'")
        return None
    
    async def get_movie_statistics(self, movie_id: int) -> Dict[str, Any]:
        """Get statistics for a movie."""
        movie = await self.get_movie_by_id(movie_id)
        if not movie:
            return {}
        
        return {
            "title": movie.get("title"),
            "year": movie.get("year"),
            "monitored": movie.get("monitored", False),
            "has_file": movie.get("hasFile", False),
            "downloaded": movie.get("downloaded", False),
            "size_on_disk": movie.get("sizeOnDisk", 0),
            "quality_profile": movie.get("qualityProfileId"),
            "tags": movie.get("tags", [])
        }
    
    async def add_movie(
        self, 
        title: str, 
        year: int,
        tmdb_id: int,
        quality_profile_id: int = 1,
        root_folder_path: str = "/movies",
        monitored: bool = True,
        search_for_movie: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Add a new movie to Radarr."""
        movie_data = {
            "title": title,
            "year": year,
            "tmdbId": tmdb_id,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {
                "searchForMovie": search_for_movie
            }
        }
        
        try:
            result = await self._make_request("POST", "/movie", json_data=movie_data)
            if result:
                logger.info(f"Successfully added movie: {title} ({year})")
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to add movie {title} ({year}): {e}")
            return None
    
    async def delete_movie(self, movie_id: int, delete_files: bool = False) -> bool:
        """Delete a movie from Radarr."""
        try:
            params = {}
            if delete_files:
                params["deleteFiles"] = "true"
            
            await self._make_request("DELETE", f"/movie/{movie_id}", params=params)
            logger.info(f"Successfully deleted movie {movie_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete movie {movie_id}: {e}")
            return False
    
    async def get_quality_profiles(self) -> List[Dict[str, Any]]:
        """Get available quality profiles."""
        result = await self._make_request("GET", "/qualityProfile")
        return result if result else []
    
    async def get_root_folders(self) -> List[Dict[str, Any]]:
        """Get configured root folders."""
        result = await self._make_request("GET", "/rootFolder")
        return result if result else []
    
    async def get_tags(self) -> List[Dict[str, Any]]:
        """Get available tags."""
        result = await self._make_request("GET", "/tag")
        return result if result else []
    
    async def search_movie_lookup(self, term: str) -> List[Dict[str, Any]]:
        """Search for movies using Radarr's lookup endpoint."""
        params = {"term": term}
        result = await self._make_request("GET", "/movie/lookup", params=params)
        return result if result else []
    
    async def trigger_movie_search(self, movie_id: int) -> bool:
        """Trigger a search for a specific movie."""
        try:
            search_data = {
                "name": "MoviesSearch",
                "movieIds": [movie_id]
            }
            
            await self._make_request("POST", "/command", json_data=search_data)
            logger.info(f"Triggered search for movie {movie_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger search for movie {movie_id}: {e}")
            return False
    
    async def get_movie_files(self, movie_id: int) -> List[Dict[str, Any]]:
        """Get files for a specific movie."""
        params = {"movieId": movie_id}
        result = await self._make_request("GET", "/moviefile", params=params)
        return result if result else []
    
    async def rename_movie_files(self, movie_id: int) -> bool:
        """Trigger rename for movie files."""
        try:
            rename_data = {
                "name": "RenameMovie",
                "movieIds": [movie_id]
            }
            
            await self._make_request("POST", "/command", json_data=rename_data)
            logger.info(f"Triggered rename for movie {movie_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger rename for movie {movie_id}: {e}")
            return False